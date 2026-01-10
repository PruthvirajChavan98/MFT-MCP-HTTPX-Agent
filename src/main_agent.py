import json
import asyncio
from typing import Optional, Annotated
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langchain_core.messages import SystemMessage, HumanMessage
from strawberry.fastapi import GraphQLRouter

# Logger & Config
from src.common.logger import StdoutLogger
from src.agent_service.prompts import SYSTEM_PROMPT
from src.agent_service.config import REDIS_URL, PORT, MODEL_NAME

# Schemas
from src.agent_service.schemas import AgentRequest, GroqConfig, OpenRouterConfig

# Services
from src.agent_service.utils import valid_session_id
from src.agent_service.llm import get_llm
from src.agent_service.mcp import mcp_manager
from src.agent_service.config_manager import config_manager
from src.agent_service.model_service import model_service
from src.agent_service.graphql_schema import schema

log = StdoutLogger(name="langchain_server")
CHECKPOINTER: Optional[BaseCheckpointSaver] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global CHECKPOINTER
    log.info(f"STARTUP: Redis Checkpointer at {REDIS_URL}")
    
    # 1. Start Background Cache Job (Model Fetcher)
    cache_task = asyncio.create_task(model_service.start_background_loop())
    
    try:
        # 2. Initialize Redis Checkpointer
        async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
            CHECKPOINTER = checkpointer
            # 3. Initialize MCP Tools
            await mcp_manager.initialize()
            yield
            
            # --- SHUTDOWN SEQUENCE ---
            cache_task.cancel()
            await mcp_manager.shutdown()
            await config_manager.close()
            log.info("SHUTDOWN: Resources cleared")
    except Exception as e:
        log.critical(f"CRITICAL STARTUP FAILURE: {e}")
        raise e

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GraphQL Endpoint ---
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agent"}

# --- REST Model Listing (Legacy/Fallback) ---
@app.get("/agent/models")
async def list_models():
    """
    List available models using the Redis cache populated by the background service.
    Returns the same data as GraphQL but in standard JSON format.
    """
    try:
        data = await model_service.get_cached_data()
        total_models = sum(len(cat["models"]) for cat in data)
        return {"count": total_models, "categories": data}
    except Exception as e:
        log.error(f"Model Fetch Error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

# --- Session Config ---

@app.get("/agent/sessions")
async def list_active_sessions():
    try:
        sessions = await config_manager.list_sessions()
        return {"count": len(sessions), "sessions": sessions}
    except Exception as e:
        log.error(f"List Sessions Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent/verify/{session_id}")
async def verify_session(session_id: str):
    sid = valid_session_id(session_id)
    exists = await config_manager.session_exists(sid)
    if not exists: raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": sid, "exists": True}

@app.get("/agent/config/{session_id}")
async def get_session_config(session_id: str):
    sid = valid_session_id(session_id)
    stored = await config_manager.get_config(sid)
    return {
        "session_id": sid,
        "system_prompt": stored.get("system_prompt") or SYSTEM_PROMPT.strip(),
        "model_name": stored.get("model_name") or MODEL_NAME,
        "reasoning_effort": stored.get("reasoning_effort"),
        "has_custom_key": bool(stored.get("openrouter_api_key")),
        "is_customized": bool(stored)
    }

@app.post("/agent/config/groq")
async def config_groq_session(config: GroqConfig):
    sid = valid_session_id(config.session_id)
    await config_manager.set_config(sid, system_prompt=config.system_prompt, model_name=config.model_name) # type: ignore
    return {"status": "updated", "provider": "groq", "session_id": sid}

@app.post("/agent/config/openrouter")
async def config_openrouter_session(config: OpenRouterConfig):
    sid = valid_session_id(config.session_id)
    await config_manager.set_config(
        sid, 
        system_prompt=config.system_prompt, # type: ignore
        model_name=config.model_name,
        openrouter_api_key=config.openrouter_api_key, # type: ignore
        reasoning_effort=config.reasoning_effort # type: ignore
    )
    return {"status": "updated", "provider": "openrouter", "session_id": sid}

# --- Agent Execution ---

async def _resolve_agent_resources(sid: str, request: AgentRequest):
    saved_config = await config_manager.get_config(sid)
    
    # Resolve Model & Prompt
    model_name = request.model_name or saved_config.get("model_name")
    sys_prompt = request.system_prompt or saved_config.get("system_prompt") or SYSTEM_PROMPT.strip()
    
    # Resolve OpenRouter Params
    or_key = request.openrouter_api_key or saved_config.get("openrouter_api_key")
    reasoning_effort = request.reasoning_effort or saved_config.get("reasoning_effort")
    
    model = get_llm(model_name, openrouter_api_key=or_key, reasoning_effort=reasoning_effort) # type: ignore
    tools = mcp_manager.rebuild_tools_for_user(sid)
    
    return model, tools, sys_prompt

@app.post("/agent/query")
async def query_agent(request: AgentRequest):
    try:
        sid = valid_session_id(request.session_id)
        model, tools, sys_prompt = await _resolve_agent_resources(sid, request)
        if not tools: raise HTTPException(status_code=500, detail="No tools loaded")
        
        agent = create_react_agent(model=model, tools=tools, checkpointer=CHECKPOINTER)
        inputs = {"messages": [SystemMessage(sys_prompt), HumanMessage(request.question)]}
        
        resp = await agent.ainvoke(inputs, {"configurable": {"thread_id": sid}})
        return {"response": resp}
    except Exception as e:
        log.error(f"Query Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/stream")
async def stream_agent(request: AgentRequest):
    try:
        sid = valid_session_id(request.session_id)
        model, tools, sys_prompt = await _resolve_agent_resources(sid, request)
        agent = create_react_agent(model=model, tools=tools, checkpointer=CHECKPOINTER)
        inputs = {"messages": [SystemMessage(sys_prompt), HumanMessage(request.question)]}
        
        async def event_generator():
            try:
                async for event in agent.astream_events(inputs, {"configurable": {"thread_id": sid}}, version="v2"):
                    kind = event["event"]
                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]  # type: ignore
                        reasoning = chunk.additional_kwargs.get("reasoning_content")
                        if reasoning: yield {"event": "reasoning_token", "data": reasoning}; continue
                        if chunk.content: yield {"event": "token", "data": chunk.content}
                    elif kind == "on_tool_start":
                        if event["name"] not in ["_Exception"]: 
                            tool_info = {"tool": event["name"], "input": event["data"].get("input")}
                            yield {"event": "tool_start", "data": json.dumps(tool_info)}
                    elif kind == "on_tool_end":
                         yield {"event": "tool_end", "data": str(event["data"].get("output"))}
                yield {"event": "done", "data": "[DONE]"}
            except Exception as e:
                yield {"event": "error", "data": str(e)}

        return EventSourceResponse(event_generator(), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    except Exception as e:
        log.error(f"Stream Setup Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)