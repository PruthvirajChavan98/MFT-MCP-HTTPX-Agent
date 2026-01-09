import asyncio
from contextlib import AsyncExitStack
from typing import List, Dict, Any, Optional
from pydantic import create_model
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from Loggers.StdOutLogger import StdoutLogger
from agent_config import SERVER_NAME, SERVER_URL
from agent_utils import valid_session_id, normalize_result

log = StdoutLogger(name="agent_mcp")

class MCPManager:
    def __init__(self):
        self.client: Optional[MultiServerMCPClient] = None
        self.session = None
        self.exit_stack = AsyncExitStack()  # Use ExitStack for safe context management
        self.call_lock = asyncio.Lock()
        self.tool_blueprints: List[Dict[str, Any]] = []

    async def initialize(self):
        """Connects to MCP server and loads tool blueprints."""
        connections = {
            SERVER_NAME: {
                "url": SERVER_URL,
                "transport": "sse",
                "headers": {},
            }
        }
        self.client = MultiServerMCPClient(connections)
        log.info(f"Connecting to MCP at {SERVER_URL}...")
        
        try:
            # Safe way to enter context that respects anyio/trio scopes
            self.session = await self.exit_stack.enter_async_context(
                self.client.session(SERVER_NAME) # type: ignore
            )
            
            raw_tools = await load_mcp_tools(self.session)
            
            self.tool_blueprints = []
            for t in raw_tools:
                name = getattr(t, "name", "").strip()
                if not name: continue
                
                self.tool_blueprints.append({
                    "name": name,
                    "description": getattr(t, "description", ""),
                    "safe_schema": self._safe_schema_from_args_schema(
                        name, getattr(t, "args_schema", None)
                    ),
                    "raw_tool": t,
                })
            log.info(f"MCP Loaded {len(self.tool_blueprints)} tools.")
            
        except Exception as e:
            log.error(f"MCP Initialization Failed: {e}")
            await self.shutdown()
            raise e

    async def shutdown(self):
        # Safe way to exit context
        await self.exit_stack.aclose()
        self.tool_blueprints = []
        log.info("MCP Session closed.")

    def _safe_schema_from_args_schema(self, tool_name: str, args_schema: Any):
        """Creates a Pydantic model for the LLM that EXCLUDES session_id."""
        fields: Dict[str, Any] = {}
        if isinstance(args_schema, dict):
            props = args_schema.get("properties", {}) or {}
            required = set(args_schema.get("required", []) or [])
            for fname, fdef in props.items():
                if fname == "session_id": continue
                
                jtype = str(fdef.get("type", "string"))
                py_type = {
                    "string": str, "integer": int, "number": float, 
                    "boolean": bool, "array": list, "object": dict,
                }.get(jtype, Any)
                
                default = ... if fname in required else None
                fields[fname] = (py_type, default)
                
        elif hasattr(args_schema, "model_fields"):
            for fname, finfo in args_schema.model_fields.items():
                if fname == "session_id": continue
                fields[fname] = (getattr(finfo, "annotation", Any), finfo)
                
        return create_model(f"{tool_name}Input", **fields)

    def rebuild_tools_for_user(self, session_id: str) -> List[StructuredTool]:
        """Wraps raw MCP tools to INJECT session_id automatically."""
        sid = valid_session_id(session_id)
        if not self.tool_blueprints:
            return []

        tools: List[StructuredTool] = []
        for bp in self.tool_blueprints:
            tool_name = bp["name"]
            description = bp["description"] or f"Tool: {tool_name}"
            safe_schema = bp["safe_schema"]
            raw_tool = bp["raw_tool"]

            async def tool_wrapper(_tool=raw_tool, _sid=sid, **kwargs):
                full_args = dict(kwargs)
                full_args["session_id"] = _sid

                async with self.call_lock:
                    res = await _tool.ainvoke(full_args)

                # LangGraph expects dict or None, MCP returns VSC string often
                if isinstance(res, str):
                    return {"text": res}
                return normalize_result(res)

            try:
                tool_instance = StructuredTool.from_function(
                    func=None,
                    coroutine=tool_wrapper,
                    name=tool_name,
                    description=description[:1000], # Trucate desc if too long
                    args_schema=safe_schema,
                )
                tools.append(tool_instance)
            except Exception as e:
                log.error(f"Failed to create tool '{tool_name}': {e}")
                continue

        return tools

# Singleton instance
mcp_manager = MCPManager()
