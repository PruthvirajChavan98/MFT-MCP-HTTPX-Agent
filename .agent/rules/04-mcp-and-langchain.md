# MCP & LangChain/LangGraph Conventions

> Applies to all MCP tool definitions and LangGraph agent orchestration code.

## MCP Tool Registration

Tools are registered in `backend/src/mcp_service/server.py`:

```python
@mcp.tool(name="generate_otp", description=_d("generate_otp"))
def generate_otp(user_input: str, session_id: str) -> str:
    _touch(session_id, "generate_otp")
    return get_auth(session_id).generate_otp(user_input)
```

### Rules

- **Descriptions**: Centralized in `description_utils.py` via `_d()`. Never hardcode long descriptions.
- **`session_id` parameter**: Every tool must accept `session_id: str`. The agent injects it automatically, but the schema must declare it.
- **`_touch()` call**: Every tool must call `_touch(session_id, "tool_name")` for session activity tracking.
- **Naming**: Use `snake_case` for tool names. Names must be stable — changing them breaks cached tool schemas.

## MCP Tool Lifecycle (Agent Side)

- `MCPManager` in `backend/src/agent_service/tools/mcp_manager.py` manages connection lifecycle.
- Tools are **rebuilt dynamically per-user** based on auth state via `rebuild_tools_for_user()`.
- Public/unauthenticated tools are listed in `PUBLIC_TOOLS` constant.
- The `session_id` parameter is **automatically omitted** from LLM-facing schemas via Pydantic `create_model()`.

## LangGraph Agent Patterns

### Checkpointing
- Uses `AsyncRedisSaver` for persistence.
- Thread ID === user session ID. No exceptions.

### Streaming
```python
event_stream = graph.astream_events(
    stream_input,
    {"configurable": {"thread_id": sid}},
    version="v2",
)
async for event in event_stream:
    # Filter events → emit via sse_formatter
```

### State
- Primary state key: `messages` (list of LLM message objects).
- Do not add arbitrary keys to the LangGraph state without updating the graph definition.

### Multi-Provider Considerations
- Reasoning fields (`reasoning_content`, `reasoning`) must be explicitly extracted from streaming chunks for models like DeepSeek.
- Provider-specific parameters (e.g., `OPENROUTER_SITE_URL`) are set via config, never hardcoded.
- BYOK (Bring Your Own Key) support per-session — keys are stored in session config, not global state.

## NBFC Router Integration

- The NBFC semantic router sits between user input and the LangGraph agent.
- Router modes: `hybrid`, `embedding`, `llm` — controlled via `NBFC_ROUTER_MODE` env var.
- Answerability scoring determines routing: KB path vs MCP tool path.
- Router worker runs as a separate container (`router_worker` service).
- Cache directory: `.cache_nbfc_router` — do not commit cache files.
