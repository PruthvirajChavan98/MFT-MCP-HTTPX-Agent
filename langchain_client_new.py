import os
import json
import asyncio
from contextlib import asynccontextmanager
import inspect
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, create_model

from langchain_mcp_adapters.client import MultiServerMCPClient
try:
    from langchain_mcp_adapters.tools import load_mcp_tools
except Exception:
    from langchain_mcp_adapters.tool import load_mcp_tools

from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import MessagesState
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain_core.tools import StructuredTool
from langchain_core.messages import RemoveMessage, SystemMessage, HumanMessage

from prompts import SYSTEM_PROMPT

# Import Redis Checkpointer
try:
    from langgraph.checkpoint.redis.aio import AsyncRedisSaver
except ImportError:
    try:
        from langgraph.checkpoint.redis.aio import RedisSaver as AsyncRedisSaver
    except ImportError:
         raise ImportError("Could not import AsyncRedisSaver.")

from Loggers.StdOutLogger import StdoutLogger

log = StdoutLogger(name="langchain_agent")

SERVER_NAME = "hero_fincorp"
SERVER_URL = os.getenv("MCP_SERVER_URL", "http://0.0.0.0:8050/sse")
KEEP_LAST = int(os.getenv("KEEP_LAST_MESSAGES", "20"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Globals
_CHECKPOINTER_CM = None  
CHECKPOINTER: Optional[BaseCheckpointSaver] = None
_SHARED_CLIENT: Optional[MultiServerMCPClient] = None
_SHARED_SESSION = None
_SHARED_CALL_LOCK = asyncio.Lock()
TOOL_BLUEPRINTS: List[Dict[str, Any]] = []
DEBUG_MODE = False  # global or per-session in Redis

# -------------------------------
# Helpers
# -------------------------------
def _valid_session_id(session_id: object) -> str:
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid

def _safe_schema_from_args_schema(tool_name: str, args_schema: Any):
    """
    Creates a Pydantic model for the LLM that EXCLUDES session_id.
    """
    fields: Dict[str, Any] = {}
    if isinstance(args_schema, dict):
        props = args_schema.get("properties", {}) or {}
        required = set(args_schema.get("required", []) or [])
        for fname, fdef in props.items():
            # --- CRITICAL: HIDE SESSION_ID FROM LLM ---
            if fname == "session_id":
                continue
            
            jtype = str(fdef.get("type", "string"))
            py_type = {
                "string": str, "integer": int, "number": float, 
                "boolean": bool, "array": list, "object": dict,
            }.get(jtype, Any)
            
            default = ... if fname in required else None
            fields[fname] = (py_type, default)
            
    elif hasattr(args_schema, "model_fields"):
        for fname, finfo in args_schema.model_fields.items():
            # --- CRITICAL: HIDE SESSION_ID FROM LLM ---
            if fname == "session_id":
                continue
            fields[fname] = (getattr(finfo, "annotation", Any), finfo)
            
    return create_model(f"{tool_name}Input", **fields)

def _normalize_result(result: Any) -> Any:
    """Sanitizes output (truncates massive JSONs) for logging/LLM context."""
    if isinstance(result, list) and result:
        # If result is a list of objects (like ToolMessages)
        first = result[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            try:
                # Pretty print JSON but truncated if needed
                parsed = json.loads(text)
                dump = json.dumps(parsed, ensure_ascii=False, indent=2)
                if len(dump) > 8000: 
                    return dump[:8000] + "... [TRUNCATED]"
                return dump
            except Exception:
                return text
    
    # If it's a direct dictionary
    if isinstance(result, dict):
        dump = json.dumps(result, ensure_ascii=False)
        if len(dump) > 8000:
            return dump[:8000] + "... [TRUNCATED]"
            
    return result

def _is_system_message(m: Any) -> bool:
    return getattr(m, "type", None) == "system" or m.__class__.__name__ == "SystemMessage"

def keep_only_last_n_messages(state: MessagesState, config: dict):
    msgs = list(state.get("messages", []))
    if len(msgs) <= KEEP_LAST:
        return {}
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *msgs[-KEEP_LAST:]]}

def rebuild_tools_for_user(session_id: str) -> List[StructuredTool]:
    """
    Rebuilds tools for a specific request.
    Wraps the raw MCP tool to INJECT session_id automatically.
    Ensures tool outputs are dict-compatible for structured_content.
    """
    sid = _valid_session_id(session_id)
    if not TOOL_BLUEPRINTS:
        return []

    tools: List[StructuredTool] = []
    for bp in TOOL_BLUEPRINTS:
        tool_name = bp.get("name", "").strip()
        if not tool_name:
            continue

        raw_desc = bp.get("description", "").strip()
        description = raw_desc[:1000] if len(raw_desc) > 1000 else raw_desc
        if not description:
            description = f"Tool: {tool_name}"

        safe_schema = bp["safe_schema"]
        raw_tool = bp["raw_tool"]

        async def tool_wrapper(_tool=raw_tool, _sid=sid, **kwargs):
            full_args = dict(kwargs)
            full_args["session_id"] = _sid

            async with _SHARED_CALL_LOCK:
                res = await _tool.ainvoke(full_args)

            # IMPORTANT: MCP tools like generate_otp return VSC strings.
            # LangGraph wants structured_content as dict or None.
            if isinstance(res, str):
                return {"text": res}

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

    return tools

# -------------------------------
# LLM
# -------------------------------
# llm = ChatOpenAI(
#     api_key="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",
#     base_url=os.getenv("BASE_URL", "https://api.groq.com/openai/v1"),
#     model=os.getenv("MODEL", "openai/gpt-oss-120b"),
#     streaming=True,
#     reasoning_effort="high",
#     extra_body={"reasoning": {"enabled": True}}
# )

llm = ChatGroq(
    api_key="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",
    base_url="https://api.groq.com",
    model=os.getenv("MODEL", "openai/gpt-oss-120b"),
    streaming=True,
    temperature=0.0,
    reasoning_format="parsed"
)

# llm_with_reasoning = llm.bind(extra_body={"reasoning": {"enabled": True}})

# llm = llm_with_reasoning

# llm = ChatOpenAI(
#     api_key="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",
#     base_url="https://openrouter.ai/api/v1",
#     model="openai/gpt-5-mini",
#     streaming=True,
#     reasoning_effort="high",
#     model_kwargs={
#         "extra_body": {
#             "include_reasoning": True 
#         }
#     }
# )

class AgentRequest(BaseModel):
    session_id: str
    question: str

# -------------------------------
# Lifespan
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _SHARED_CLIENT, _SHARED_SESSION, TOOL_BLUEPRINTS, CHECKPOINTER

    log.info(f"STARTUP: Redis Checkpointer at {REDIS_URL}")
    
    # 1. Initialize Checkpointer
    async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
        CHECKPOINTER = checkpointer
        
        # 2. Initialize MCP Client
        connections = {
            SERVER_NAME: {
                "url": SERVER_URL,
                "transport": "sse",
                "headers": {},
            }
        }
        client = MultiServerMCPClient(connections)
        _SHARED_CLIENT = client

        # 3. Load Tools Once
        log.info("STARTUP: connecting to MCP...")
        async with client.session(SERVER_NAME) as session:
            _SHARED_SESSION = session
            raw_tools = await load_mcp_tools(_SHARED_SESSION)
            
            TOOL_BLUEPRINTS = []
            for t in raw_tools:
                name = getattr(t, "name", "").strip()
                if not name: continue
                
                TOOL_BLUEPRINTS.append({
                    "name": name,
                    "description": getattr(t, "description", ""),
                    "safe_schema": _safe_schema_from_args_schema(
                        name, getattr(t, "args_schema", None)
                    ),
                    "raw_tool": t,
                })
            log.info(f"STARTUP: Loaded {len(TOOL_BLUEPRINTS)} tools.")
            
            yield
            
        log.info("SHUTDOWN: Clearing globals")
        TOOL_BLUEPRINTS = []
        _SHARED_SESSION = None
        _SHARED_CLIENT = None
        CHECKPOINTER = None

app = FastAPI(lifespan=lifespan)

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # List of allowed origins
    allow_credentials=True,     # Allow cookies and authentication headers
    allow_methods=["*"],        # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],        # Allow all headers
)

@app.post("/agent/query")
async def query_agent(request: AgentRequest):
    try:
        sid = _valid_session_id(request.session_id)
        tools = rebuild_tools_for_user(sid)
        if not tools:
            raise HTTPException(status_code=500, detail="No tools loaded")
        
        agent = create_react_agent(
            model=llm,
            tools=tools,
            checkpointer=CHECKPOINTER,          
        )

        system_text = SYSTEM_PROMPT.strip()
        inputs = {
            "messages": [
                SystemMessage(system_text),
                HumanMessage(request.question),
            ]
        }
        
        resp = await agent.ainvoke(
            inputs,
            {
                "configurable": {"thread_id": sid}
                },
            )
        return {"response": resp}
    except Exception as e:
        log.error(f"Query Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
                    

@app.post("/agent/stream")
async def stream_agent(request: AgentRequest):
    sid = _valid_session_id(request.session_id)
    tools = rebuild_tools_for_user(sid)
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        checkpointer=CHECKPOINTER
    )

    system_text = SYSTEM_PROMPT.strip()
    inputs = {
        "messages": [
            SystemMessage(system_text),
            HumanMessage(request.question),
        ]
    }
    
    config = {"configurable": {"thread_id": sid}}

    async def event_generator():
        try:
            async for event in agent.astream_events(inputs, config, version="v2"):
                kind = event["event"]

                # --- 1. Stream Tokens (Reasoning & Content) ---
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    
                    # A. Reasoning Token (from your logs: additional_kwargs['reasoning_content'])
                    reasoning = chunk.additional_kwargs.get("reasoning_content")
                    if reasoning:
                        yield {"event": "reasoning_token", "data": reasoning}
                        # Continue to next iteration to avoid double-processing if content is empty
                        continue 

                    # B. Standard Content Token (from your logs: content='  ')
                    # Only yield if content is not empty/None
                    if chunk.content:
                        yield {"event": "token", "data": chunk.content}

                # --- 2. Detect Tool Calls ---
                elif kind == "on_tool_start":
                    if event["name"] not in ["_Exception"]: 
                        tool_info = {
                            "tool": event["name"],
                            "input": event["data"].get("input")
                        }
                        yield {"event": "tool_start", "data": json.dumps(tool_info)}

                # --- 3. Tool Output ---
                elif kind == "on_tool_end":
                     yield {"event": "tool_end", "data": str(event["data"].get("output"))}

            yield {"event": "done", "data": "[DONE]"}

        except Exception as e:
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(
        event_generator(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))