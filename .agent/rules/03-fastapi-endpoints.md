# FastAPI Endpoint Standards

> Applies to `backend/src/agent_service/api/**/*.py`.

## Router Setup

```python
from fastapi import APIRouter
router = APIRouter(prefix="/agent", tags=["agent-stream"])
```

- All routers mount in `AppFactory._mount_routers()` inside `core/app_factory.py`.
- Adding a new router? Register it there — orphan routers are **never** auto-discovered.

## Endpoint File Layout

```
api/
├── endpoints/
│   ├── __init__.py           # Router registration exports
│   ├── agent_stream.py       # SSE streaming endpoint
│   ├── agent_query.py        # Synchronous query endpoint
│   ├── sessions.py           # Session CRUD + BYOK config
│   ├── health.py             # Health + readiness checks
│   ├── rate_limit_metrics.py # Rate limit dashboard data
│   ├── live_dashboards.py    # Real-time analytics WebSocket
│   ├── follow_up.py          # Follow-up question generation
│   └── router_endpoints.py   # NBFC router management
├── admin.py                  # Admin panel endpoints
├── admin_analytics.py        # Analytics + trace viewer
├── admin_auth.py             # Admin authentication
├── feedback.py               # User feedback collection
├── eval_ingest.py            # Shadow eval ingestion
├── eval_live.py              # Live eval endpoints
├── eval_read.py              # Eval result retrieval
└── graphql.py                # Strawberry GraphQL schema
```

## Session Validation (Non-Negotiable)

```python
from src.agent_service.core.session_utils import session_utils
sid = session_utils.validate_session_id(request.session_id)
```

- Never trust raw session IDs from client requests.
- Validate immediately at the top of every endpoint handler.

## Rate Limiting

```python
from src.agent_service.core.rate_limiter_manager import get_rate_limiter_manager, enforce_rate_limit

manager = get_rate_limiter_manager()
limiter = await manager.get_agent_stream_limiter()
await enforce_rate_limit(http_request, limiter, f"session:{sid}")
```

- Rate limiting is **mandatory** on streaming and auth-critical endpoints.
- Per-user quotas live in FastAPI, **not** in Nginx.

## Streaming (SSE) Contract

```python
from sse_starlette.sse import EventSourceResponse
from src.agent_service.core.streaming_utils import sse_formatter

async def event_generator():
    yield sse_formatter.token_event("Hello")
    yield sse_formatter.done_event()

return EventSourceResponse(event_generator(), headers={"Cache-Control": "no-cache"})
```

**Public SSE event types** (the API contract — do not change without versioning):
- `reasoning` — LLM reasoning/thinking tokens
- `tool_call` — MCP tool invocation events
- `token` — Response content tokens
- `cost` — Token usage and cost metadata
- `done` — Stream termination signal

- Never expose internal LangGraph lifecycle events to clients unless `AGENT_STREAM_EXPOSE_INTERNAL_EVENTS=true`.
- Always set `proxy_buffering off` in Nginx for streaming routes.

## Response Standards

- Success: return Pydantic models or `JSONResponse` with explicit status codes.
- Errors: raise `HTTPException` with meaningful `detail` strings.
- Never return raw dicts for complex payloads — use typed schemas.
