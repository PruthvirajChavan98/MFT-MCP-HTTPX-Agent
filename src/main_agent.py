# ===== src/main_agent.py =====
import sys
import json
import asyncio
import os
import shutil
import tempfile
import logging
from typing import Optional, Annotated, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, File, UploadFile, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from strawberry.fastapi import GraphQLRouter

# Logger & Config
from src.agent_service.core.prompts import SYSTEM_PROMPT
from src.agent_service.core.config import REDIS_URL, PORT, MODEL_NAME

# Schemas
from src.agent_service.core.schemas import AgentRequest, GroqConfig, OpenRouterConfig, FAQBatchRequest, NvidiaConfig, FAQEditRequest

# Services
from src.agent_service.core.utils import valid_session_id
from src.agent_service.llm.client import get_llm
from src.agent_service.tools.mcp_manager import mcp_manager
from src.agent_service.data.config_manager import config_manager
from src.agent_service.llm.catalog import model_service
from src.agent_service.api.graphql import schema
from src.agent_service.api.eval_ingest import router as eval_router
from src.agent_service.api.eval_read import router as eval_read_router
from src.agent_service.tools.knowledge import kb_service
from src.agent_service.features.follow_up import follow_up_service
from src.agent_service.features.kb_first import kb_first_payload
from src.agent_service.features.shadow_eval import ShadowEvalCollector, maybe_shadow_eval_commit

# Utils
from src.agent_service.core.utils import _extract_tool_output
from src.agent_service.faqs.pdf_parser import PDFQAParser

logging.basicConfig(
    format="%(levelname)s [%(name)s] %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)

logging.getLogger("httpx").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.INFO)

log = logging.getLogger("agent_main")
CHECKPOINTER: Optional[BaseCheckpointSaver] = None

# --- Helper to fetch App ID from Auth Store ---
async def _get_app_id_for_session(session_id: str) -> Optional[str]:
    """Retrieves the app_id (case_id) associated with an authenticated session."""
    try:
        from redis.asyncio import Redis
        # Create a ephemeral client to avoid concurrency issues with the global checkpointer
        client = Redis.from_url(REDIS_URL, decode_responses=True)
        data_str = await client.get(session_id)
        await client.close()
        
        if data_str:
            data = json.loads(str(data_str))
            return data.get("app_id")
    except Exception:
        pass
    return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global CHECKPOINTER
    log.info(f"STARTUP: Redis Checkpointer at {REDIS_URL}")
    
    cache_task = asyncio.create_task(model_service.start_background_loop())
    
    try:
        async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
            CHECKPOINTER = checkpointer
            await mcp_manager.initialize()
            yield
            
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

graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")

app.include_router(eval_router, prefix="/eval")
app.include_router(eval_read_router, prefix="/eval")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agent"}

@app.get("/agent/models")
async def list_models():
    try:
        data = await model_service.get_cached_data()
        total_models = sum(len(cat["models"]) for cat in data)
        return {"count": total_models, "categories": data}
    except Exception as e:
        log.error(f"Model Fetch Error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

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
    )
    return {"status": "updated", "provider": "openrouter", "session_id": sid}

@app.post("/agent/config/nvidia")
async def config_nvidia_session(config: NvidiaConfig):
    sid = valid_session_id(config.session_id)
    await config_manager.set_config(
        sid, 
        system_prompt=config.system_prompt, # type: ignore
        model_name=config.model_name,
        reasoning_effort=config.reasoning_effort # type: ignore
    )
    return {"status": "updated", "provider": "nvidia", "session_id": sid}

async def _resolve_agent_resources(sid: str, request: AgentRequest):
    saved_config = await config_manager.get_config(sid)

    model_name = request.model_name or saved_config.get("model_name") or MODEL_NAME
    sys_prompt = request.system_prompt or saved_config.get("system_prompt") or SYSTEM_PROMPT.strip()
    reasoning_effort = request.reasoning_effort or saved_config.get("reasoning_effort")

    or_key = request.openrouter_api_key or saved_config.get("openrouter_api_key")
    nv_key = request.nvidia_api_key or saved_config.get("nvidia_api_key")

    model = get_llm(
        model_name, 
        openrouter_api_key=or_key,  # type: ignore
        nvidia_api_key=nv_key,      # type: ignore
        reasoning_effort=reasoning_effort  # type: ignore
    )

    tools = mcp_manager.rebuild_tools_for_user(sid, openrouter_api_key=or_key)  # type: ignore
    return model, tools, sys_prompt

def _infer_provider_from_model_name(model_name: str) -> str:
    mn = (model_name or "").strip().lower()
    if mn.startswith("nvidia/"): return "nvidia"
    if mn.startswith("groq/"): return "groq"
    if "/" in mn: return "openrouter"
    return "groq"

@app.post("/agent/query")
async def query_agent(request: AgentRequest):
    try:
        sid = valid_session_id(request.session_id)
        model, tools, sys_prompt = await _resolve_agent_resources(sid, request)
        kb_payload = await kb_first_payload(request.question, tools)
        if kb_payload:
            return {"response": kb_payload["output"], "kb_first": True}
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

        saved_config = await config_manager.get_config(sid)
        model_name = (
            (request.model_name or "").strip()
            or str(saved_config.get("model_name") or "").strip()
            or (MODEL_NAME or "").strip()
        )
        provider = _infer_provider_from_model_name(model_name)

        model, tools, sys_prompt = await _resolve_agent_resources(sid, request)

        # --- CONTEXT CAPTURE FOR JUDGE ---
        
        # 1. Fetch Chat History
        temp_agent = create_react_agent(model=model, tools=tools, checkpointer=CHECKPOINTER)
        state_snapshot = await temp_agent.aget_state({"configurable": {"thread_id": sid}})
        chat_history = state_snapshot.values.get("messages", []) if state_snapshot else []

        # 2. Fetch App ID (Case ID) from Auth Store
        app_id = await _get_app_id_for_session(sid)

        # 3. Serialize Tools
        tool_defs = "\n".join([f"- {t.name}: {t.description}" for t in tools])

        # 4. Initialize Collector
        collector = ShadowEvalCollector(
            session_id=sid,
            question=request.question,
            provider=provider,
            model=(model_name or None),
            endpoint="/agent/stream",
            system_prompt=sys_prompt,
            chat_history=chat_history,
            tool_definitions=tool_defs
        )
        
        # ✅ Inject Case ID
        collector.case_id = app_id # type: ignore

        # KB-first guardrail
        kb_payload = await kb_first_payload(request.question, tools)
        if kb_payload:
            log.info(f"[kb-first] sid={sid} tool={kb_payload.get('tool')}")
            async def kb_event_generator():
                try:
                    tool_name = kb_payload.get("tool", "hero_fincorp_knowledge_base")
                    tool_input = kb_payload.get("input", {"query": request.question})
                    output = str(kb_payload.get("output", "") or "").replace("\r", "")

                    collector.on_tool_start(tool_name, tool_input)
                    collector.on_tool_end(tool_name, output, tool_call_id="kb_first")

                    yield {"event": "tool_start", "data": json.dumps({"tool": tool_name, "input": tool_input}, ensure_ascii=False)}
                    yield {"event": "tool_end", "data": json.dumps({"tool": tool_name, "tool_call_id": "kb_first", "output": output}, ensure_ascii=False)}

                    for i in range(0, len(output), 160):
                        chunk = output[i : i + 160]
                        collector.on_token(chunk)
                        yield {"event": "token", "data": chunk}

                    collector.on_done(final_output=output, error=None)
                    yield {"event": "done", "data": "[DONE]"}
                except Exception as e:
                    collector.on_done(final_output="", error=str(e))
                    yield {"event": "error", "data": str(e)}
                finally:
                    asyncio.create_task(maybe_shadow_eval_commit(collector))

            return EventSourceResponse(kb_event_generator(), headers={"Cache-Control": "no-cache"})

        # Normal streaming
        if not tools: raise HTTPException(status_code=500, detail="No tools loaded")

        agent = create_react_agent(model=model, tools=tools, checkpointer=CHECKPOINTER)
        inputs = {"messages": [SystemMessage(sys_prompt), HumanMessage(request.question)]}

        async def event_generator():
            final_parts: List[str] = []
            try:
                async for event in agent.astream_events(inputs, {"configurable": {"thread_id": sid}}, version="v2"):
                    kind = event["event"]
                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"] # type: ignore
                        reasoning = (chunk.additional_kwargs.get("reasoning_content") or chunk.additional_kwargs.get("reasoning") or chunk.response_metadata.get("reasoning"))
                        if reasoning:
                            collector.on_reasoning(str(reasoning))
                            yield {"event": "reasoning_token", "data": reasoning}
                        if chunk.content:
                            txt = str(chunk.content)
                            final_parts.append(txt)
                            collector.on_token(txt)
                            yield {"event": "token", "data": txt}
                    elif kind == "on_tool_start":
                        if event.get("name") not in ["_Exception"]:
                            tool_name = event.get("name") or "unknown"
                            tool_input = event["data"].get("input")
                            collector.on_tool_start(tool_name, tool_input)
                            yield {"event": "tool_start", "data": json.dumps({"tool": tool_name, "input": tool_input}, ensure_ascii=False)}
                    elif kind == "on_tool_end":
                        if event.get("name") not in ["_Exception"]:
                            tool_name = event.get("name") or "unknown"
                            raw_output = event["data"].get("output")
                            clean_output = _extract_tool_output(raw_output)
                            tool_call_id = event.get("run_id") or event["data"].get("tool_call_id")
                            collector.on_tool_end(tool_name, clean_output, tool_call_id=tool_call_id)
                            yield {"event": "tool_end", "data": json.dumps({"tool": tool_name, "tool_call_id": tool_call_id, "output": clean_output}, ensure_ascii=False)}

                final_output = "".join(final_parts) if final_parts else ""
                collector.on_done(final_output=final_output, error=None)
                yield {"event": "done", "data": "[DONE]"}

            except Exception as e:
                err = str(e)
                log.error(f"Stream Error: {err}")
                collector.on_done(final_output="".join(final_parts), error=err)
                yield {"event": "error", "data": err}
            finally:
                asyncio.create_task(maybe_shadow_eval_commit(collector))

        return EventSourceResponse(event_generator(), headers={"Cache-Control": "no-cache"})

    except Exception as e:
        log.error(f"Stream Setup Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/follow-up")
async def generate_follow_up(request: AgentRequest):
    try:
        sid = valid_session_id(request.session_id)
        model, tools, _ = await _resolve_agent_resources(sid, request)
        agent = create_react_agent(model=model, tools=tools, checkpointer=CHECKPOINTER)
        config = {"configurable": {"thread_id": sid}}
        state_snapshot = await agent.aget_state(config) # type: ignore

        if not state_snapshot or not state_snapshot.values or "messages" not in state_snapshot.values:
            return {"questions": []}

        messages: List[BaseMessage] = state_snapshot.values["messages"]
        questions = await follow_up_service.generate_questions(
            messages=messages, llm=model, tools=tools,
            openrouter_key=request.openrouter_api_key, nvidia_key=request.nvidia_api_key
        )
        return {"questions": questions}
    except Exception as e:
        log.error(f"Follow-up Generation Error: {e}")
        return {"questions": []}
    
@app.post("/agent/follow-up-stream")
async def generate_follow_up_stream(request: AgentRequest):
    try:
        sid = valid_session_id(request.session_id)
        model, tools, _ = await _resolve_agent_resources(sid, request)
        agent = create_react_agent(model=model, tools=tools, checkpointer=CHECKPOINTER)
        config = {"configurable": {"thread_id": sid}}
        state_snapshot = await agent.aget_state(config)  # type: ignore

        if not state_snapshot or not state_snapshot.values or "messages" not in state_snapshot.values:
            async def empty_stream():
                yield {"event": "error", "data": "No conversation history found"}
                yield {"event": "done", "data": "[DONE]"}
            return EventSourceResponse(empty_stream())

        messages: List[BaseMessage] = state_snapshot.values["messages"]

        async def event_generator():
            try:
                async for event in follow_up_service.generate_questions_stream(
                    messages=messages, llm=model, tools=tools,
                    openrouter_key=request.openrouter_api_key, nvidia_key=request.nvidia_api_key,
                ):
                    yield event
            except Exception as stream_err:
                log.error(f"Follow-up streaming error: {stream_err}")
                yield {"event": "error", "data": str(stream_err)}
                yield {"event": "done", "data": "[DONE]"}

        return EventSourceResponse(event_generator())

    except Exception as e:
        log.error(f"Follow-up Endpoint Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent/all-follow-ups")
async def get_stored_followups():
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
        exists = await config_manager.session_exists(sid)
        await config_manager.delete_session(sid)
        log.info(f"LOGOUT: Session {sid} cleared")
        return {"status": "logged_out", "session_id": sid, "message": "Session cleared."}
    except Exception as e:
        log.error(f"Logout Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# --- STREAMING JSON Batch ---
@app.post("/agent/admin/faqs/batch-json")
async def update_faqs_json_stream(
    request: Request, # Need raw request to parse body manually or use Pydantic in a specific way
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"), 
    x_groq_key: Optional[str] = Header(None, alias="X-Groq-Key"), 
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key")
):
    """
    Real-time streaming ingestion for JSON batches.
    """
    try:
        body = await request.json()
        items = body.get("items", [])
        
        if not items:
            async def empty_gen():
                yield {"event": "error", "data": "No items provided"}
            return EventSourceResponse(empty_gen())

        # Use the generator from service
        return EventSourceResponse(
            kb_service.ingest_faq_batch_gen(items, groq_key=x_groq_key, openrouter_key=x_openrouter_key),
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        log.error(f"Ingest Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- STREAMING PDF Upload ---
@app.post("/agent/admin/faqs/upload-pdf")
async def update_faqs_pdf_stream(
    file: UploadFile = File(...),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    x_groq_key: Optional[str] = Header(None, alias="X-Groq-Key"),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key")
):
    """
    Real-time streaming ingestion for PDF.
    Step 1: Parse PDF (Sync, might take 1-2s).
    Step 2: Stream ingestion of parsed items.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # 1. Save Temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    async def pdf_ingestion_generator():
        try:
            # Emit Parsing Status
            yield {"event": "progress", "data": json.dumps({"percent": 2, "message": "Parsing PDF Structure..."})}
            
            # Parse (Blocking operation, usually fast for standard PDFs)
            parser = PDFQAParser(tmp_path)
            parsed_data = parser.parse()

            if not parsed_data:
                yield {"event": "error", "data": "No Q&A pairs found in PDF."}
                return

            yield {"event": "progress", "data": json.dumps({"percent": 5, "message": f"Found {len(parsed_data)} pairs. Starting ingestion..."})}

            # Delegate to the common ingestion generator
            async for event in kb_service.ingest_faq_batch_gen(parsed_data, groq_key=x_groq_key, openrouter_key=x_openrouter_key):
                yield event

        except Exception as e:
            yield {"event": "error", "data": str(e)}
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    return EventSourceResponse(pdf_ingestion_generator(), headers={"Cache-Control": "no-cache"})

@app.get("/agent/admin/faqs")
async def get_faqs(
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0)
):
    """
    Retrieve stored FAQs with pagination.
    """
    try:
        data = await kb_service.get_all_faqs(limit=limit, skip=skip)
        return {
            "status": "success",
            "count": len(data),
            "limit": limit,
            "skip": skip,
            "items": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/agent/admin/faqs")
async def edit_faq(
    request: FAQEditRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key")
):
    """
    Edit a specific FAQ. 
    - `original_question`: The exact text of the question to find.
    - `new_question`: (Optional) New text for the question (updates embedding).
    - `new_answer`: (Optional) New text for the answer.
    """
    result = await kb_service.edit_faq(
        original_question=request.original_question,
        new_question=request.new_question,
        new_answer=request.new_answer,
        openrouter_key=x_openrouter_key
    )
    
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result

@app.delete("/agent/admin/faqs")
async def delete_faq_endpoint(
    question: str = Query(..., description="The exact question text to delete"),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    """
    Delete an FAQ by providing the exact question string.
    """
    result = await kb_service.delete_faq(question)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    
    return result

@app.delete("/agent/admin/faqs/all")
async def clear_all_faqs_endpoint(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    """
    DANGER: Wipes all FAQs from the database.
    """
    result = await kb_service.clear_all_faqs()
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)