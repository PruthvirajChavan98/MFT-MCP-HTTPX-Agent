import os
import json
import asyncio
from contextlib import asynccontextmanager
import inspect
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, create_model

from langchain_mcp_adapters.client import MultiServerMCPClient
try:
    from langchain_mcp_adapters.tools import load_mcp_tools
except Exception:  # pragma: no cover
    from langchain_mcp_adapters.tool import load_mcp_tools  # type: ignore

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# --- FIX: Correct Import for Async Redis ---
try:
    # Try importing the specific Async class name
    from langgraph.checkpoint.redis.aio import AsyncRedisSaver
except ImportError:
    # Fallback: Sometimes it is exposed as RedisSaver inside the aio module
    try:
        from langgraph.checkpoint.redis.aio import RedisSaver as AsyncRedisSaver
    except ImportError:
         raise ImportError("Could not import AsyncRedisSaver. Check your langgraph-checkpoint-redis version.")

from langgraph.checkpoint.base import BaseCheckpointSaver

from langchain_core.tools import StructuredTool
from langchain_core.messages import RemoveMessage
from langgraph.graph import MessagesState
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from Loggers.StdOutLogger import StdoutLogger

log = StdoutLogger(name="langchain_agent")

SERVER_NAME = "hero_fincorp"
SERVER_URL = os.getenv("MCP_SERVER_URL", "http://0.0.0.0:8050/sse")
KEEP_LAST = int(os.getenv("KEEP_LAST_MESSAGES", "20"))

# ---- globals we initialize in lifespan ----
_CHECKPOINTER_CM = None  
CHECKPOINTER: Optional[BaseCheckpointSaver] = None

_SHARED_CLIENT: Optional[MultiServerMCPClient] = None
_SHARED_SESSION = None
_SHARED_SESSION_CM = None
_SHARED_CALL_LOCK = asyncio.Lock()

TOOL_BLUEPRINTS: List[Dict[str, Any]] = []

# -------------------------------
# Helpers
# -------------------------------
def _valid_session_id(session_id: object) -> str:
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid

def _safe_schema_from_args_schema(tool_name: str, args_schema: Any):
    fields: Dict[str, Any] = {}
    if isinstance(args_schema, dict):
        props = args_schema.get("properties", {}) or {}
        required = set(args_schema.get("required", []) or [])
        for fname, fdef in props.items():
            if fname == "session_id":
                continue
            jtype = str(fdef.get("type", "string"))
            py_type = {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
                "array": list,
                "object": dict,
            }.get(jtype, Any)
            default = ... if fname in required else None
            fields[fname] = (py_type, default)
    elif hasattr(args_schema, "model_fields"):
        for fname, finfo in args_schema.model_fields.items():
            if fname == "session_id":
                continue
            fields[fname] = (getattr(finfo, "annotation", Any), finfo)
    return create_model(f"{tool_name}Input", **fields)

def _normalize_result(result: Any) -> Any:
    if isinstance(result, list) and result:
        first = result[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            try:
                return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
            except Exception:
                return text
    return result

def _is_system_message(m: Any) -> bool:
    return getattr(m, "type", None) == "system" or m.__class__.__name__ == "SystemMessage"

def keep_only_last_n_messages(state: MessagesState, config: dict):
    msgs = list(state.get("messages", []))
    if len(msgs) <= KEEP_LAST + 1:
        return {}

    kept: list[Any] = []
    if msgs and _is_system_message(msgs[0]):
        kept.append(msgs[0])
        msgs = msgs[1:]

    kept.extend(msgs[-KEEP_LAST:])
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *kept]}

def rebuild_tools_for_user(session_id: str) -> List[StructuredTool]:
    sid = _valid_session_id(session_id)
    if not TOOL_BLUEPRINTS:
        return []

    tools: List[StructuredTool] = []
    for bp in TOOL_BLUEPRINTS:
        tool_name = bp.get("name", "").strip()
        
        # CRITICAL: Skip invalid tool names
        if not tool_name:
            log.warning(f"Skipping tool with missing/empty name: {bp}")
            continue
        
        # CRITICAL: Enforce description requirements for Harmony
        raw_desc = bp.get("description", "").strip()
        if not raw_desc:
            description = f"Tool: {tool_name}. No description available."
        else:
            # Truncate to Groq's 1024 char limit with safety margin
            description = raw_desc[:1000] if len(raw_desc) > 1000 else raw_desc
        
        safe_schema = bp["safe_schema"]
        raw_tool = bp["raw_tool"]

        async def tool_wrapper(_tool=raw_tool, _sid=sid, **kwargs):
            full_args = dict(kwargs)
            full_args["session_id"] = _sid
            async with _SHARED_CALL_LOCK:
                res = await _tool.ainvoke(full_args)
            return _normalize_result(res)

        try:
            tool_instance = StructuredTool.from_function(
                func=None,
                coroutine=tool_wrapper,
                name=tool_name,
                description=description,
                args_schema=safe_schema,
            )
            tools.append(tool_instance)
        except Exception as e:
            log.error(f"Failed to create tool '{tool_name}': {e}")
            continue

    log.info(f"Generated {len(tools)} valid tools for session {sid}")
    return tools

# -------------------------------
# LLM
# -------------------------------
llm = ChatOpenAI(
    api_key="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",
    base_url=os.getenv("BASE_URL", "https://api.groq.com/openai/v1"),
    model=os.getenv("MODEL", "openai/gpt-oss-120b"),
    streaming=True,
)

class AgentRequest(BaseModel):
    session_id: str
    question: str

# -------------------------------
# Lifespan
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _SHARED_CLIENT, _SHARED_SESSION, _SHARED_SESSION_CM, TOOL_BLUEPRINTS
    global _CHECKPOINTER_CM, CHECKPOINTER

    # Keep these unused legacy globals explicitly reset (so other code doesn't
    # mistakenly try to close them).
    _CHECKPOINTER_CM = None
    _SHARED_SESSION_CM = None

    redis_url = "redis://localhost:6379/0"
    log.info(f"STARTUP: Opening Async LangGraph Redis checkpointer: {redis_url}")

    connections = {
        SERVER_NAME: {
            "url": SERVER_URL,
            "transport": "sse",
            "headers": {},
        }
    }

    client = MultiServerMCPClient(connections)
    _SHARED_CLIENT = client

    # NOTE: AsyncRedisSaver is designed to be used as an async context manager.
    async with AsyncRedisSaver.from_conn_string(redis_url) as checkpointer:
        CHECKPOINTER = checkpointer

        # Some versions expose setup as asetup(); be defensive.
        for setup_name in ("asetup", "setup"):
            setup_fn = getattr(CHECKPOINTER, setup_name, None)
            if setup_fn is None:
                continue
            try:
                if inspect.iscoroutinefunction(setup_fn):
                    await setup_fn()
                else:
                    setup_fn()
                log.info(f"STARTUP: Checkpointer {setup_name}() completed")
                break
            except Exception as e:
                log.warning(f"STARTUP: Checkpointer {setup_name}() failed: {e}")

        log.info("STARTUP: Opening persistent MCP session")
        async with client.session(SERVER_NAME) as session:
            _SHARED_SESSION = session

            log.info("STARTUP: Loading MCP tools ONCE via load_mcp_tools(session)")
            raw_tools = await load_mcp_tools(_SHARED_SESSION)
            log.info(f"Raw MCP tools inspection:")
            for idx, t in enumerate(raw_tools):
                log.info(f"  [{idx}] name='{getattr(t, 'name', None)}' desc_len={len(getattr(t, 'description', ''))}")

            # Build validated tool blueprints once.
            TOOL_BLUEPRINTS = []
            MAX_DESC_LEN = 1000  # keep margin for providers that enforce ~1024 chars

            for t in raw_tools:
                name = (getattr(t, "name", "") or "").strip()
                if not name:
                    log.warning(f"Skipping MCP tool with empty name: {t!r}")
                    continue

                raw_desc = getattr(t, "description", None)
                desc = (raw_desc or "").strip()
                if not desc:
                    desc = f"Tool named {name}. No description provided."

                if len(desc) > MAX_DESC_LEN:
                    log.warning(
                        f"Tool '{name}' description too long ({len(desc)} chars), truncating"
                    )
                    desc = desc[:MAX_DESC_LEN]

                TOOL_BLUEPRINTS.append(
                    {
                        "name": name,
                        "description": desc,
                        "safe_schema": _safe_schema_from_args_schema(
                            name, getattr(t, "args_schema", None)
                        ),
                        "raw_tool": t,
                    }
                )

            log.info(f"STARTUP: Cached {len(TOOL_BLUEPRINTS)} validated tools")

            try:
                yield
            finally:
                # Context managers will close session + checkpointer automatically.
                log.info("SHUTDOWN: Clearing globals")
                TOOL_BLUEPRINTS = []
                _SHARED_SESSION = None
                _SHARED_CLIENT = None
                CHECKPOINTER = None

app = FastAPI(lifespan=lifespan)

# -------------------------------
# Endpoint
# -------------------------------
@app.post("/agent/query")
async def query_agent(request: AgentRequest):
    try:
        sid = _valid_session_id(request.session_id)
        tools = rebuild_tools_for_user(sid)
        if not tools:
            raise HTTPException(status_code=500, detail="No tools loaded from MCP server")
        if CHECKPOINTER is None:
            raise HTTPException(status_code=500, detail="Checkpointer not initialized")

        agent = create_react_agent(
            model=llm,
            tools=tools,
            checkpointer=CHECKPOINTER,          
            pre_model_hook=keep_only_last_n_messages,  
        )

        resp = await agent.ainvoke(
            {"messages": [{"role": "user", "content": request.question}]},
            {"configurable": {"thread_id": sid}},
        )

        return {"response": resp}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/agent/stream")
async def stream_agent(request: AgentRequest):
    sid = _valid_session_id(request.session_id)
    tools = rebuild_tools_for_user(sid)

    if not tools:
        raise HTTPException(status_code=500, detail="No tools loaded from MCP server")
    if CHECKPOINTER is None:
        raise HTTPException(status_code=500, detail="Checkpointer not initialized")

    agent = create_react_agent(
        model=llm,
        tools=tools,
        checkpointer=CHECKPOINTER,
        pre_model_hook=keep_only_last_n_messages,
    )

    inputs = {"messages": [{"role": "user", "content": request.question}]}
    config = {"configurable": {"thread_id": sid}}

    async def event_generator():
        try:
            async for event in agent.astream_events(inputs, config, version="v2"):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        # EventSourceResponse will format SSE frames for you
                        yield {"event": "token", "data": chunk.content}

            yield {"event": "done", "data": "[DONE]"}

        except Exception as e:
            log.error(f"Streaming error: {e}")
            yield {"event": "error", "data": str(e)}

    # NOTE: Don’t use GZip middleware with SSE/streaming.
    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))