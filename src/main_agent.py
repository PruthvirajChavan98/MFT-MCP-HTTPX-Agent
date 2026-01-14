# ===== src/main_agent.py =====
import json
import asyncio
import logging
from typing import Optional, Annotated, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from strawberry.fastapi import GraphQLRouter

# Logger & Config
from src.common.logger import StdoutLogger
from src.agent_service.prompts import SYSTEM_PROMPT
from src.agent_service.config import REDIS_URL, PORT, MODEL_NAME

# Schemas
from src.agent_service.schemas import AgentRequest, GroqConfig, OpenRouterConfig, FAQBatchRequest, NvidiaConfig # Added FAQBatchRequest

# Services
from src.agent_service.utils import valid_session_id
from src.agent_service.llm import get_llm
from src.agent_service.mcp import mcp_manager
from src.agent_service.config_manager import config_manager
from src.agent_service.model_service import model_service
from src.agent_service.graphql_schema import schema
from src.agent_service.knowledge_base import kb_service # [NEW]
from src.utils import _extract_tool_output
from src.agent_service.follow_up_generator import follow_up_service

log = logging.getLogger("agent_main")
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
    
    # Check if keys exist (return boolean flags for security)
    has_or_key = bool(stored.get("openrouter_api_key"))
    has_nv_key = bool(stored.get("nvidia_api_key"))
    
    return {
        "session_id": sid,
        "system_prompt": stored.get("system_prompt") or SYSTEM_PROMPT.strip(),
        "model_name": stored.get("model_name") or MODEL_NAME,
        "reasoning_effort": stored.get("reasoning_effort"),
        "has_custom_key": has_or_key,
        "has_openrouter_key": has_or_key,
        "has_nvidia_key": has_nv_key,
        "is_customized": bool(stored)
    }

@app.post("/agent/config/groq")
async def config_groq_session(config: GroqConfig):
    sid = valid_session_id(config.session_id)
    await config_manager.set_config(
        sid, 
        system_prompt=config.system_prompt, # type: ignore
        model_name=config.model_name,
        reasoning_effort=config.reasoning_effort # type: ignore
        # REMOVED: openrouter_api_key, nvidia_api_key
    ) 
    return {"status": "updated", "provider": "groq", "session_id": sid}

@app.post("/agent/config/openrouter")
async def config_openrouter_session(config: OpenRouterConfig):
    sid = valid_session_id(config.session_id)
    await config_manager.set_config(
        sid, 
        system_prompt=config.system_prompt, # type: ignore
        model_name=config.model_name,
        reasoning_effort=config.reasoning_effort # type: ignore
        # REMOVED keys
    )
    return {"status": "updated", "provider": "openrouter", "session_id": sid}

# --- NEW ENDPOINT ---
@app.post("/agent/config/nvidia")
async def config_nvidia_session(config: NvidiaConfig):
    sid = valid_session_id(config.session_id)
    await config_manager.set_config(
        sid, 
        system_prompt=config.system_prompt, # type: ignore
        model_name=config.model_name,
        reasoning_effort=config.reasoning_effort # type: ignore
        # REMOVED keys
    )
    return {"status": "updated", "provider": "nvidia", "session_id": sid}

# --- Agent Execution ---

# --- UPDATE RESOURCE RESOLVER ---
async def _resolve_agent_resources(sid: str, request: AgentRequest):
    saved_config = await config_manager.get_config(sid)
    
    model_name = request.model_name or saved_config.get("model_name")
    sys_prompt = request.system_prompt or saved_config.get("system_prompt") or SYSTEM_PROMPT.strip()
    reasoning_effort = request.reasoning_effort or saved_config.get("reasoning_effort")
    
    # Resolve Keys (Request Override > Session Storage > Server Env [Handled in LLM])
    or_key = request.openrouter_api_key or saved_config.get("openrouter_api_key")
    nv_key = request.nvidia_api_key or saved_config.get("nvidia_api_key") # <--- Resolve
    
    model = get_llm(
        model_name, # type: ignore
        openrouter_api_key=or_key, # type: ignore
        nvidia_api_key=nv_key, # <--- Pass it # type: ignore
        reasoning_effort=reasoning_effort # type: ignore
    )
    
    # --- CHANGED: Pass openrouter_api_key to tool builder ---
    tools = mcp_manager.rebuild_tools_for_user(sid, openrouter_api_key=or_key) # type: ignore
    # -------------------------------------------------------
    
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
                async for event in agent.astream_events(
                    inputs,
                    {"configurable": {"thread_id": sid}},
                    version="v2",
                ):
                    kind = event["event"]

                    # --- 1. Chat Stream (Content & Reasoning) ---
                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]  # type: ignore

                        # Reasoning Extraction
                        reasoning = chunk.additional_kwargs.get("reasoning_content")
                        if not reasoning:
                            reasoning = chunk.additional_kwargs.get("reasoning")
                        if not reasoning:
                            reasoning = chunk.response_metadata.get("reasoning")

                        if reasoning:
                            yield {"event": "reasoning_token", "data": reasoning}
                            # DeepSeek R1 on NVIDIA sends reasoning tokens separately from content
                            # so we often continue here, but some providers mix them.
                            # The check below ensures we don't duplicate if content is empty.

                        if chunk.content:
                            yield {"event": "token", "data": chunk.content}

                    # --- 2. Token Usage Metrics (NEW) ---
                    # Captures usage from the final message generation event
                    # elif kind == "on_chat_model_end":
                    #     output = event["data"].get("output")
                    #     if output:
                    #         # Standard LangChain Usage Metadata (V3 standard)
                    #         usage = getattr(output, "usage_metadata", None)

                    #         # Fallback: Check response_metadata (NVIDIA/OpenAI legacy)
                    #         if not usage:
                    #             usage = output.response_metadata.get("token_usage")

                    #         if usage:
                    #             # Format: {"input_tokens": 15, "output_tokens": 1024, "total_tokens": 1039}
                    #             yield {"event": "usage", "data": json.dumps(usage)}

                    # --- 3. Tool Start ---
                    elif kind == "on_tool_start":
                        if event["name"] not in ["_Exception"]:
                            tool_info = {
                                "tool": event["name"],
                                "input": event["data"].get("input"),
                            }
                            yield {"event": "tool_start", "data": json.dumps(tool_info, ensure_ascii=False)}

                    # --- 4. Tool End ---
                    elif kind == "on_tool_end":
                        if event.get("name") not in ["_Exception"]:
                            raw_output = event["data"].get("output")
                            # Assuming _extract_tool_output is defined in your utils or scope
                            clean_output = _extract_tool_output(raw_output)

                            payload = {
                                "tool": event.get("name") or "unknown",
                                "tool_call_id": event.get("run_id") or event["data"].get("tool_call_id"),
                                "output": clean_output,
                            }
                            yield {"event": "tool_end", "data": json.dumps(payload, ensure_ascii=False)}

                yield {"event": "done", "data": "[DONE]"}
                
                # generated_questions = await follow_up_service.generate_questions(
                #      messages=inputs["messages"], 
                #      llm=model, 
                #      tools=tools
                # )
                
                # if generated_questions:
                #     yield {"event": "follow_up", "data": json.dumps(generated_questions)}

            except Exception as e:
                log.error(f"Stream Error: {e}")
                yield {"event": "error", "data": str(e)}

        return EventSourceResponse(
            event_generator(),
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    except Exception as e:
        log.error(f"Stream Setup Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/agent/follow-up")
async def generate_follow_up(request: AgentRequest):
    """
    Generates follow-up questions based on the current session state.
    This should be called AFTER the stream is complete.
    """
    try:
        sid = valid_session_id(request.session_id)
        
        # 1. Re-resolve Resources
        # We need to recreate the agent object to access the state correctly
        model, tools, _ = await _resolve_agent_resources(sid, request)
        agent = create_react_agent(model=model, tools=tools, checkpointer=CHECKPOINTER)

        # 2. Fetch Latest State via AGENT API (Not raw checkpointer)
        config = {"configurable": {"thread_id": sid}}
        
        # --- FIX: Use agent.aget_state() ---
        # This returns a StateSnapshot object where .values is a dictionary property.
        state_snapshot = await agent.aget_state(config) # type: ignore

        if not state_snapshot or not state_snapshot.values or "messages" not in state_snapshot.values:
            log.warning(f"No message history found for session {sid}")
            return {"questions": []}

        # 3. Get Message History
        messages: List[BaseMessage] = state_snapshot.values["messages"]

        # 4. Generate Questions
        questions = await follow_up_service.generate_questions(
            messages=messages,
            llm=model,
            tools=tools,
            openrouter_key=request.openrouter_api_key,
            nvidia_key=request.nvidia_api_key
        )
        
        return {"questions": questions}

    except Exception as e:
        log.error(f"Follow-up Generation Error: {e}")
        return {"questions": []}
    
@app.post("/agent/follow-up-stream")
async def generate_follow_up_stream(request: AgentRequest):
    """
    Streams follow-up generation via SSE.

    Events emitted by follow_up_service:
      - status: plain text status updates
      - reasoning: optional provider-exposed reasoning tokens
      - candidate: {"id": <int>, "question": "<str>"}
      - candidate_why_token: {"id": <int>, "token": "<str>"}   (token-by-token)
      - candidate_why_done:  {"id": <int>, "why": "<str>"}     (final why string)
      - result: ["Q1?","Q2?","Q3?"]  (FINAL judged list only)
      - done: [DONE]
    """
    try:
        sid = valid_session_id(request.session_id)

        # Resolve model/tools and load persisted conversation state
        model, tools, _ = await _resolve_agent_resources(sid, request)
        agent = create_react_agent(model=model, tools=tools, checkpointer=CHECKPOINTER)

        config = {"configurable": {"thread_id": sid}}
        state_snapshot = await agent.aget_state(config)  # type: ignore

        if not state_snapshot or not state_snapshot.values or "messages" not in state_snapshot.values:
            log.warning(f"No message history found for session {sid}")

            async def empty_stream():
                yield {"event": "error", "data": "No conversation history found"}
                yield {"event": "done", "data": "[DONE]"}

            return EventSourceResponse(
                empty_stream(),
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        messages: List[BaseMessage] = state_snapshot.values["messages"]

        async def event_generator():
            try:
                async for event in follow_up_service.generate_questions_stream(
                    messages=messages,
                    llm=model,
                    tools=tools,
                    openrouter_key=request.openrouter_api_key,
                    nvidia_key=request.nvidia_api_key,
                ):
                    # Pass-through as-is: {"event": "...", "data": "..."}
                    yield event
            except Exception as stream_err:
                log.error(f"Follow-up streaming error: {stream_err}")
                yield {"event": "error", "data": str(stream_err)}
                yield {"event": "done", "data": "[DONE]"}

        return EventSourceResponse(
            event_generator(),
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        log.error(f"Follow-up Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent/all-follow-ups")
async def get_stored_followups():
    """
    Admin endpoint to view all cached follow-up questions stored in Neo4j.
    """
    try:
        results = await follow_up_service.get_all_cached_questions()
        return {"count": len(results), "data": results}
    except Exception as e:
        log.error(f"Admin Fetch Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/agent/logout/{session_id}")
async def logout_session(session_id: str):
    try:
        sid = valid_session_id(session_id)
        
        # Check if it exists first (optional, but good for 404s)
        exists = await config_manager.session_exists(sid)
        # Note: We also check the auth session, but session_exists only checks config
        # We will proceed with deletion regardless to ensure a clean slate.
        
        await config_manager.delete_session(sid)
        
        log.info(f"LOGOUT: Session {sid} cleared")
        return {"status": "logged_out", "session_id": sid, "message": "Session configuration and authentication data cleared."}
    except Exception as e:
        log.error(f"Logout Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/admin/faqs")
async def update_faqs(
    request: FAQBatchRequest, 
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    x_groq_key: Optional[str] = Header(None, alias="X-Groq-Key"),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key")
):
    """
    Update or Add FAQs.
    - Uses server-side keys (Round-Robin) by default.
    - Accepts 'X-Groq-Key' and 'X-OpenRouter-Key' headers to override.
    """
    if not request.items:
        return {"status": "ignored", "message": "No items provided"}

    data = [item.model_dump() for item in request.items]
    
    # Pass the headers to the service
    result = await kb_service.ingest_faq_batch(
        data, 
        groq_key=x_groq_key,  # type: ignore
        openrouter_key=x_openrouter_key # type: ignore
    )
    
    return {
        "status": "completed", 
        "details": result
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)