import sys
import json
import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

# LangChain V1 / LangGraph Imports
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from strawberry.fastapi import GraphQLRouter

# Enterprise Modules
from src.agent_service.core.prompts import SYSTEM_PROMPT
from src.agent_service.core.config import REDIS_URL, PORT, MODEL_NAME
from src.agent_service.core.schemas import (
    AgentRequest, GroqConfig, OpenRouterConfig, NvidiaConfig, RouterClassifyRequest
)
from src.agent_service.core.utils import valid_session_id, _extract_tool_output
from src.agent_service.core.cost import calculate_run_cost
from src.agent_service.llm.client import get_llm
from src.agent_service.tools.mcp_manager import mcp_manager
from src.agent_service.data.config_manager import config_manager
from src.agent_service.llm.catalog import model_service

# Routers
from src.agent_service.api.graphql import schema
from src.agent_service.api.eval_ingest import router as eval_router
from src.agent_service.api.eval_read import router as eval_read_router
from src.agent_service.api.admin import router as admin_router

from src.agent_service.features.follow_up import follow_up_service
from src.agent_service.features.kb_first import kb_first_payload
from src.agent_service.features.shadow_eval import ShadowEvalCollector, maybe_shadow_eval_commit
from src.agent_service.features.nbfc_router import nbfc_router_service

# Setup Standard Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger("main_agent")

CHECKPOINTER: Optional[AsyncRedisSaver] = None

async def _get_app_id_for_session(session_id: str) -> Optional[str]:
    try:
        from redis.asyncio import Redis
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
app.include_router(admin_router) # Includes /agent/admin/* and /agent/all-follow-ups

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
    if not exists:
        raise HTTPException(status_code=404, detail="Session not found")
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
        "is_customized": bool(stored),
    }

@app.post("/agent/config/groq")
async def config_groq_session(config: GroqConfig):
    sid = valid_session_id(config.session_id)
    await config_manager.set_config(
        sid,
        system_prompt=config.system_prompt,
        model_name=config.model_name,
        reasoning_effort=config.reasoning_effort,
        openrouter_api_key=config.openrouter_api_key,
        nvidia_api_key=config.nvidia_api_key,
    )
    return {"status": "updated", "provider": "groq", "session_id": sid}

@app.post("/agent/config/openrouter")
async def config_openrouter_session(config: OpenRouterConfig):
    sid = valid_session_id(config.session_id)
    await config_manager.set_config(
        sid,
        system_prompt=config.system_prompt,
        model_name=config.model_name,
        reasoning_effort=config.reasoning_effort,
        openrouter_api_key=config.openrouter_api_key,
        nvidia_api_key=config.nvidia_api_key,
    )
    return {"status": "updated", "provider": "openrouter", "session_id": sid}

@app.post("/agent/config/nvidia")
async def config_nvidia_session(config: NvidiaConfig):
    sid = valid_session_id(config.session_id)
    await config_manager.set_config(
        sid,
        system_prompt=config.system_prompt,
        model_name=config.model_name,
        reasoning_effort=config.reasoning_effort,
        openrouter_api_key=config.openrouter_api_key,
        nvidia_api_key=config.nvidia_api_key,
    )
    return {"status": "updated", "provider": "nvidia", "session_id": sid}

async def _resolve_agent_resources(sid: str, request: AgentRequest):
    saved_config = await config_manager.get_config(sid)
    
    model_name = request.model_name or saved_config.get("model_name") or MODEL_NAME
    sys_prompt = request.system_prompt or saved_config.get("system_prompt") or SYSTEM_PROMPT.strip()
    reasoning_effort = request.reasoning_effort or saved_config.get("reasoning_effort")
    
    or_key = request.openrouter_api_key or saved_config.get("openrouter_api_key")
    nv_key = request.nvidia_api_key or saved_config.get("nvidia_api_key")
    
    # Unified Factory Init (LangChain V1)
    model = get_llm(
        model_name=model_name,
        openrouter_api_key=or_key,
        nvidia_api_key=nv_key,
        reasoning_effort=reasoning_effort
    )
    
    tools = mcp_manager.rebuild_tools_for_user(sid, openrouter_api_key=or_key)
    
    # Return keys and model_name for downstream usage (Cost/FollowUp)
    return model, tools, sys_prompt, or_key, model_name

def _infer_provider_from_model_name(model_name: str) -> str:
    mn = (model_name or "").strip().lower()
    if mn.startswith("nvidia/"): return "nvidia"
    if mn.startswith("groq/"): return "groq"
    if "/" in mn: return "openrouter"
    return "groq"

@app.post("/agent/router/classify")
async def router_classify(req: RouterClassifyRequest):
    try:
        out = await nbfc_router_service.classify(
            req.text,
            openrouter_api_key=req.openrouter_api_key,
            mode=req.mode,
        )
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/router/compare")
async def router_compare(req: RouterClassifyRequest):
    try:
        out = await nbfc_router_service.compare(req.text, openrouter_api_key=req.openrouter_api_key)
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/query")
async def query_agent(request: AgentRequest):
    try:
        sid = valid_session_id(request.session_id)
        model, tools, sys_prompt, or_key, _ = await _resolve_agent_resources(sid, request)

        router_out = None
        try:
            router_out = await nbfc_router_service.classify(request.question, openrouter_api_key=or_key)
        except Exception:
            router_out = None

        kb_payload = await kb_first_payload(request.question, tools)
        if kb_payload:
            return {"response": kb_payload["output"], "kb_first": True, "router": router_out}

        if not tools:
            raise HTTPException(status_code=500, detail="No tools loaded")

        # LangGraph V1 Agent
        agent = create_agent(model, tools, system_prompt=sys_prompt, checkpointer=CHECKPOINTER)
        inputs = {"messages": [HumanMessage(request.question)]}
        
        resp = await agent.ainvoke(inputs, {"configurable": {"thread_id": sid}})
        return {"response": resp, "router": router_out}
    except Exception as e:
        log.error(f"Query Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/stream")
async def stream_agent(request: AgentRequest):
    try:
        sid = valid_session_id(request.session_id)
        model, tools, sys_prompt, or_key, model_id = await _resolve_agent_resources(sid, request)
        
        provider = _infer_provider_from_model_name(model_id)
        router_task = asyncio.create_task(nbfc_router_service.classify(request.question, openrouter_api_key=or_key))

        # Capture State for Eval
        app_id = await _get_app_id_for_session(sid)
        
        collector = ShadowEvalCollector(
            session_id=sid,
            question=request.question,
            provider=provider,
            model=model_id,
            endpoint="/agent/stream",
            system_prompt=sys_prompt,
            tool_definitions="" # Tools are passed to model, collector infers from events
        )
        collector.case_id = app_id

        # KB Guardrail
        kb_payload = await kb_first_payload(request.question, tools)
        if kb_payload:
            async def kb_event_generator():
                try:
                    tool_name = kb_payload.get("tool", "kb")
                    tool_input = kb_payload.get("input", {})
                    output = str(kb_payload.get("output", ""))
                    
                    collector.on_tool_start(tool_name, tool_input)
                    collector.on_tool_end(tool_name, output, tool_call_id="kb_first")
                    
                    yield {"event": "tool_start", "data": json.dumps({"tool": tool_name, "input": tool_input}, ensure_ascii=False)}
                    yield {"event": "tool_end", "data": json.dumps({"tool": tool_name, "tool_call_id": "kb_first", "output": output}, ensure_ascii=False)}
                    
                    yield {"event": "token", "data": output}
                    collector.on_token(output)
                    
                    collector.on_done(final_output=output, error=None)
                    yield {"event": "done", "data": "[DONE]"}
                except Exception as e:
                    collector.on_done(final_output="", error=str(e))
                    yield {"event": "error", "data": str(e)}
                finally:
                    try:
                        r_out = await router_task
                        if r_out: collector.set_router_outcome(r_out)
                    except Exception: pass
                    asyncio.create_task(maybe_shadow_eval_commit(collector))

            return EventSourceResponse(kb_event_generator(), headers={"Cache-Control": "no-cache"})

        if not tools:
            raise HTTPException(status_code=500, detail="No tools loaded")

        # LangGraph Agent
        agent = create_agent(model, tools, system_prompt=sys_prompt, checkpointer=CHECKPOINTER)
        
        async def event_generator():
            total_cost = 0.0
            total_tokens = 0
            
            try:
                # Resolve Router first to emit event
                try:
                    router_out = await router_task
                    if router_out:
                        collector.set_router_outcome(router_out)
                        yield {"event": "router", "data": json.dumps(router_out, ensure_ascii=False)}
                except Exception:
                    pass

                async for event in agent.astream_events(
                    {"messages": [HumanMessage(content=request.question)]},
                    {"configurable": {"thread_id": sid}},
                    version="v2"
                ):
                    kind = event["event"]
                    data = event["data"]
                    
                    if kind == "on_chat_model_stream":
                        chunk = data["chunk"]
                        # Extract reasoning if available (DeepSeek/O1)
                        if hasattr(chunk, "additional_kwargs"):
                            r_content = chunk.additional_kwargs.get("reasoning_content")
                            if r_content:
                                yield {"event": "reasoning_token", "data": str(r_content)}
                        
                        if chunk.content:
                            txt = str(chunk.content)
                            collector.on_token(txt)
                            yield {"event": "token", "data": txt}
                            
                    elif kind == "on_tool_start":
                        t_name = event["name"]
                        t_input = data.get("input")
                        collector.on_tool_start(t_name, t_input)
                        yield {"event": "tool_start", "data": json.dumps({"tool": t_name, "input": t_input}, ensure_ascii=False)}
                        
                    elif kind == "on_tool_end":
                        t_name = event["name"]
                        output = _extract_tool_output(data.get("output"))
                        run_id = event.get("run_id")
                        collector.on_tool_end(t_name, output, tool_call_id=run_id)
                        yield {"event": "tool_end", "data": json.dumps({"tool": t_name, "output": output, "tool_call_id": run_id}, ensure_ascii=False)}

                    # Enterprise Cost Tracking
                    elif kind == "on_chat_model_end":
                        out_msg = data.get("output")
                        if hasattr(out_msg, "usage_metadata") and out_msg.usage_metadata:
                            usage = out_msg.usage_metadata
                            cost = await calculate_run_cost(model_id, usage)
                            total_cost += cost
                            total_tokens += usage.get("total_tokens", 0)

                collector.on_done(final_output="", error=None)
                yield {"event": "cost", "data": json.dumps({"cost": total_cost, "tokens": total_tokens})}
                yield {"event": "done", "data": "[DONE]"}
                
                asyncio.create_task(maybe_shadow_eval_commit(collector))

            except Exception as e:
                err = str(e)
                log.error(f"Stream Error: {err}")
                collector.on_done(final_output="", error=err)
                yield {"event": "error", "data": err}
                asyncio.create_task(maybe_shadow_eval_commit(collector))

        return EventSourceResponse(event_generator(), headers={"Cache-Control": "no-cache"})

    except Exception as e:
        log.error(f"Stream Setup Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/follow-up")
async def generate_follow_up(request: AgentRequest):
    try:
        sid = valid_session_id(request.session_id)
        model, tools, _, or_key, _ = await _resolve_agent_resources(sid, request)
        
        # We need the conversation history
        # Create a temporary agent to fetch state
        temp_agent = create_agent(model, tools, checkpointer=CHECKPOINTER)
        state = await temp_agent.aget_state({"configurable": {"thread_id": sid}})
        messages = state.values.get("messages", []) if state else []
        
        questions = await follow_up_service.generate_questions(
            messages=messages,
            llm=model,
            tools=tools,
            openrouter_key=or_key
        )
        return {"questions": questions}
    except Exception as e:
        log.error(f"Follow-up Error: {e}")
        return {"questions": []}

@app.post("/agent/follow-up-stream")
async def generate_follow_up_stream(request: AgentRequest):
    try:
        sid = valid_session_id(request.session_id)
        model, tools, _, or_key, _ = await _resolve_agent_resources(sid, request)
        
        temp_agent = create_agent(model, tools, checkpointer=CHECKPOINTER)
        state = await temp_agent.aget_state({"configurable": {"thread_id": sid}})
        messages = state.values.get("messages", []) if state else []

        async def event_generator():
            try:
                async for event in follow_up_service.generate_questions_stream(
                    messages=messages,
                    llm=model,
                    tools=tools,
                    openrouter_key=or_key
                ):
                    yield event
            except Exception as e:
                yield {"event": "error", "data": str(e)}
        
        return EventSourceResponse(event_generator())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/agent/logout/{session_id}")
async def logout_session(session_id: str):
    try:
        sid = valid_session_id(session_id)
        await config_manager.delete_session(sid)
        log.info(f"LOGOUT: Session {sid} cleared")
        return {"status": "logged_out", "session_id": sid, "message": "Session cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
