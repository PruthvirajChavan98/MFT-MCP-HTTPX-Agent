import os
import json
import asyncio
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, create_model

from langchain_mcp_adapters.client import MultiServerMCPClient
try:
    # Most common location
    from langchain_mcp_adapters.tools import load_mcp_tools
except Exception:  # pragma: no cover
    # Fallback for older/alternate layouts
    from langchain_mcp_adapters.tool import load_mcp_tools  # type: ignore

from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import StructuredTool

from Loggers.StdOutLogger import StdoutLogger

log = StdoutLogger(name="langchain_agent")

SERVER_NAME = "hero_fincorp"
SERVER_URL = os.getenv("MCP_SERVER_URL", "http://0.0.0.0:8050/sse")

# One shared MCP session across the whole process
_SHARED_CLIENT: Optional[MultiServerMCPClient] = None
_SHARED_SESSION = None
_SHARED_SESSION_CM = None
_SHARED_CALL_LOCK = asyncio.Lock()

# Cached tool blueprints (name/description/safe_schema/raw_tool)
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
    """
    Create a Pydantic model excluding 'session_id' so LLM never sees it.
    Works with:
      - Pydantic model (has model_fields)
      - JSON schema dict (properties/required)
    """
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
        # Pydantic v2 BaseModel
        for fname, finfo in args_schema.model_fields.items():
            if fname == "session_id":
                continue
            fields[fname] = (getattr(finfo, "annotation", Any), finfo)

    return create_model(f"{tool_name}Input", **fields)

def _normalize_result(result: Any) -> Any:
    # Pretty print JSON-ish TextContent for LLM
    if isinstance(result, list) and result:
        first = result[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            try:
                return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
            except Exception:
                return text
    return result

def rebuild_tools_for_user(session_id: str) -> List[StructuredTool]:
    sid = _valid_session_id(session_id)

    if not TOOL_BLUEPRINTS:
        return []

    tools: List[StructuredTool] = []
    for bp in TOOL_BLUEPRINTS:
        tool_name = bp["name"]
        description = bp["description"]
        safe_schema = bp["safe_schema"]
        raw_tool = bp["raw_tool"]

        # Bind everything to avoid late-binding closure bugs
        async def tool_wrapper(_tool=raw_tool, _tool_name=tool_name, _sid=sid, **kwargs):
            full_args = dict(kwargs)
            full_args["session_id"] = _sid

            # serialize calls on the single shared MCP session
            async with _SHARED_CALL_LOCK:
                res = await _tool.ainvoke(full_args)

            return _normalize_result(res)

        tools.append(
            StructuredTool.from_function(
                func=None,
                coroutine=tool_wrapper,
                name=tool_name,
                description=description or "",
                args_schema=safe_schema,
            )
        )

    return tools

# -------------------------------
# LLM + API Schema
# -------------------------------
llm = AzureChatOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY", "ddf"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-03-01-preview"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "GPT4"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://hfcl-genai-apim-cin-001-prod.azure-api.net"),
    streaming=True,
)

class AgentRequest(BaseModel):
    session_id: str
    question: str

# -------------------------------
# Lifespan: open ONE MCP session, load tools ONCE
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _SHARED_CLIENT, _SHARED_SESSION, _SHARED_SESSION_CM, TOOL_BLUEPRINTS

    log.info("STARTUP: Creating MCP client (non-context-manager)")
    connections = {
        SERVER_NAME: {
            "url": SERVER_URL,
            "transport": "sse",
            "headers": {},  # shared connection; session_id is a tool arg
        }
    }
    _SHARED_CLIENT = MultiServerMCPClient(connections)

    log.info("STARTUP: Opening persistent MCP session")
    _SHARED_SESSION_CM = _SHARED_CLIENT.session(SERVER_NAME)
    _SHARED_SESSION = await _SHARED_SESSION_CM.__aenter__()

    log.info("STARTUP: Loading MCP tools ONCE via load_mcp_tools(session)")
    raw_tools = await load_mcp_tools(_SHARED_SESSION)

    TOOL_BLUEPRINTS = []
    for t in raw_tools:
        TOOL_BLUEPRINTS.append({
            "name": t.name,
            "description": getattr(t, "description", "") or "",
            "safe_schema": _safe_schema_from_args_schema(t.name, getattr(t, "args_schema", None)),
            "raw_tool": t,
        })

    log.info(f"STARTUP: Cached {len(TOOL_BLUEPRINTS)} tools")
    try:
        yield
    finally:
        log.info("SHUTDOWN: Closing MCP session")
        try:
            if _SHARED_SESSION_CM is not None:
                await _SHARED_SESSION_CM.__aexit__(None, None, None)
        finally:
            _SHARED_SESSION_CM = None
            _SHARED_SESSION = None
            _SHARED_CLIENT = None

app = FastAPI(lifespan=lifespan)

# -------------------------------
# Endpoint
# -------------------------------
@app.post("/agent/query")
async def query_agent(request: AgentRequest):
    try:
        tools = rebuild_tools_for_user(request.session_id)
        if not tools:
            raise HTTPException(status_code=500, detail="No tools loaded from MCP server")

        agent = create_react_agent(model=llm, tools=tools)
        resp = await agent.ainvoke({"messages": [{"role": "user", "content": request.question}]})
        return {"response": resp}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
