import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from pydantic import create_model

from src.agent_service.core.config import SERVER_NAME, SERVER_URL
from src.agent_service.core.utils import is_user_authenticated, normalize_result, valid_session_id

# Local Imports (Updated paths)
from .graph_rag import create_graph_tool

log = logging.getLogger("mcp_manager")

# [CONFIG] Tools allowed for users who HAVE NOT logged in yet
PUBLIC_TOOLS = {
    "generate_otp",
    "validate_otp",
    "is_logged_in",
    "mock_fintech_knowledge_base",  # The FAQ RAG tool
}


class MCPManager:
    def __init__(self):
        self.client: Optional[MultiServerMCPClient] = None
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.call_lock = asyncio.Lock()
        self.tool_blueprints: List[Dict[str, Any]] = []

    async def initialize(self):
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
            self.session = await self.exit_stack.enter_async_context(
                self.client.session(SERVER_NAME)  # type: ignore
            )
            raw_tools = await load_mcp_tools(self.session)

            self.tool_blueprints = []
            for t in raw_tools:
                name = getattr(t, "name", "").strip()
                if not name:
                    continue
                self.tool_blueprints.append(
                    {
                        "name": name,
                        "description": getattr(t, "description", ""),
                        "safe_schema": self._safe_schema_from_args_schema(
                            name, getattr(t, "args_schema", None)
                        ),
                        "raw_tool": t,
                    }
                )
            log.info(f"MCP Loaded {len(self.tool_blueprints)} tools.")
        except Exception as e:
            log.error(f"MCP Init Failed: {e}")
            await self.shutdown()
            raise e

    async def shutdown(self):
        await self.exit_stack.aclose()
        self.tool_blueprints = []
        log.info("MCP Session closed.")

    def _safe_schema_from_args_schema(self, tool_name: str, args_schema: Any):
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

    def rebuild_tools_for_user(
        self, session_id: str, openrouter_api_key: Optional[str] = None
    ) -> List[StructuredTool]:
        """
        Dynamically constructs the list of tools for a specific user session.
        If the user is NOT authenticated, complex tools (loan details, SOA, etc.) are hidden.
        """
        sid = valid_session_id(session_id)

        # 1. Fast Auth Check (Redis)
        is_auth = is_user_authenticated(sid)

        tools: List[StructuredTool] = []

        # 2. Iterate Blueprints (Remote MCP Tools)
        if self.tool_blueprints:
            for bp in self.tool_blueprints:
                tool_name = bp["name"]

                # --- FILTERING LOGIC ---
                # If unauthenticated, SKIP tools that are not in the public list.
                if not is_auth and tool_name not in PUBLIC_TOOLS:
                    continue

                description = bp["description"] or f"Tool: {tool_name}"
                safe_schema = bp["safe_schema"]
                raw_tool = bp["raw_tool"]

                # Wrapper to inject session_id into remote calls
                async def tool_wrapper(_tool=raw_tool, _sid=sid, **kwargs):
                    full_args = dict(kwargs)
                    full_args["session_id"] = _sid
                    async with self.call_lock:
                        res = await _tool.ainvoke(full_args)
                    if isinstance(res, str):
                        return {"text": res}
                    return normalize_result(res)

                try:
                    tool_instance = StructuredTool.from_function(
                        func=None,
                        coroutine=tool_wrapper,
                        name=tool_name,
                        description=description[:1000],
                        args_schema=safe_schema,
                    )
                    tools.append(tool_instance)
                except Exception as e:
                    log.error(f"Failed to create MCP tool '{tool_name}': {e}")
                    continue

        # 3. Add Local Graph Tool (FAQ)
        # This is generally considered "Public"
        if is_auth or "mock_fintech_knowledge_base" in PUBLIC_TOOLS:
            try:
                # Pass the key here (it might be None, which is fine if env var is set)
                graph_tool = create_graph_tool(openrouter_api_key=openrouter_api_key)  # type: ignore
                tools.append(graph_tool)
            except Exception as e:
                log.error(f"Failed to attach Graph Tool: {e}")

        return tools


mcp_manager = MCPManager()
