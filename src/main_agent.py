import json
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langchain_core.messages import SystemMessage, HumanMessage

from src.common.logger import StdoutLogger
from src.agent_service.prompts import SYSTEM_PROMPT
from src.agent_service.config import REDIS_URL, PORT, MODEL_NAME
from src.agent_service.schemas import AgentRequest, SessionConfig
from src.agent_service.utils import valid_session_id
from src.agent_service.llm import llm, get_llm, get_available_models
from src.agent_service.mcp import mcp_manager
from src.agent_service.config_manager import config_manager

log = StdoutLogger(name="langchain_server")
CHECKPOINTER: Optional[BaseCheckpointSaver] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global CHECKPOINTER
    log.info(f"STARTUP: Redis Checkpointer at {REDIS_URL}")
    try:
        async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
            CHECKPOINTER = checkpointer
            await mcp_manager.initialize()
            yield
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

@app.get("/health")
async def health_check():
    """Health check endpoint for orchestrators."""
    if not CHECKPOINTER:
        raise HTTPException(status_code=503, detail="Redis Checkpointer not initialized")
    return {"status": "healthy", "service": "agent"}

@app.get("/agent/models")
async def list_models():
    """Returns a list of available LLM models from Groq."""
    try:
        return await get_available_models()
    except Exception as e:
        log.error(f"Model Fetch Error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

# --- Session Management Endpoints ---

@app.get("/agent/sessions")
async def list_active_sessions():
    """List all session IDs that have custom configurations stored."""
    try:
        sessions = await config_manager.list_sessions()
        return {"count": len(sessions), "sessions": sessions}
    except Exception as e:
        log.error(f"List Sessions Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent/verify/{session_id}")
async def verify_session(session_id: str):
    """Check if a session configuration exists."""
    sid = valid_session_id(session_id)
    exists = await config_manager.session_exists(sid)
    if not exists:
        raise HTTPException(status_code=404, detail=f"Session {sid} not found in configuration store.")
    return {"session_id": sid, "exists": True}

@app.post("/agent/config")
async def update_session_config(config: SessionConfig):
    """Set custom system prompt or model for a session."""
    try:
        sid = valid_session_id(config.session_id)
        await config_manager.set_config(
            sid, 
            system_prompt=config.system_prompt,  # type: ignore
            model_name=config.model_name # type: ignore
        )
        return {"status": "updated", "session_id": sid}
    except Exception as e:
        log.error(f"Config Update Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent/config/{session_id}")
async def get_session_config(session_id: str):
    """Get the current effective configuration for a session."""
    try:
        sid = valid_session_id(session_id)
        stored_config = await config_manager.get_config(sid)
        
        # Merge stored config with system defaults
        return {
            "session_id": sid,
            "system_prompt": stored_config.get("system_prompt") or SYSTEM_PROMPT.strip(),
            "model_name": stored_config.get("model_name") or MODEL_NAME,
            "is_customized": bool(stored_config)
        }
    except Exception as e:
        log.error(f"Config Fetch Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Agent Endpoints ---

async def _get_agent_context(sid: str, request: AgentRequest):
    """Helper to resolve final config (Request > Redis > Default)."""
    saved_config = await config_manager.get_config(sid)
    
    model_name = request.model_name or saved_config.get("model_name")
    sys_prompt = request.system_prompt or saved_config.get("system_prompt") or SYSTEM_PROMPT.strip()
    
    return model_name, sys_prompt

@app.post("/agent/query")
async def query_agent(request: AgentRequest):
    try:
        sid = valid_session_id(request.session_id)
        tools = mcp_manager.rebuild_tools_for_user(sid)
        if not tools: raise HTTPException(status_code=500, detail="No tools loaded")
        
        model_name, sys_prompt = await _get_agent_context(sid, request)
        model = get_llm(model_name) # type: ignore
        
        agent = create_react_agent(model=model, tools=tools, checkpointer=CHECKPOINTER)
        inputs = {"messages": [SystemMessage(sys_prompt), HumanMessage(request.question)]}
        
        resp = await agent.ainvoke(inputs, {"configurable": {"thread_id": sid}})
        return {"response": resp}
    except Exception as e:
        log.error(f"Query Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/stream")
async def stream_agent(request: AgentRequest):
    sid = valid_session_id(request.session_id)
    tools = mcp_manager.rebuild_tools_for_user(sid)
    
    model_name, sys_prompt = await _get_agent_context(sid, request)
    model = get_llm(model_name) # type: ignore
    
    agent = create_react_agent(model=model, tools=tools, checkpointer=CHECKPOINTER)
    inputs = {"messages": [SystemMessage(sys_prompt), HumanMessage(request.question)]}
    
    async def event_generator():
        try:
            async for event in agent.astream_events(inputs, {"configurable": {"thread_id": sid}}, version="v2"):
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"] # type: ignore
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
