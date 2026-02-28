# Python Backend Standards

> Applies to all files under `backend/**/*.py`.

## Async-First Architecture

- All I/O operations **must** be async (`async def` + `await`).
- Use `asyncio.Lock()` for shared-resource protection (e.g., MCP connection pool).
- Never block the event loop with synchronous I/O — use `asyncio.to_thread()` if wrapping sync code.
- Long-running background work should be dispatched to workers, not inline in request handlers.

## File Header (Mandatory)

Every Python file starts with:

```python
from __future__ import annotations
```

## Type Hints (Mandatory)

- Use Python 3.11+ native syntax:
  - `dict[str, Any]` not `Dict[str, Any]`
  - `list[str]` not `List[str]`
  - `T | None` preferred over `Optional[T]`
- All function signatures must have return type annotations.
- Use Pydantic models for request/response payloads — never ad-hoc dicts.

## Import Order

```python
from __future__ import annotations          # 1. Future

import asyncio                               # 2. Stdlib
import logging

from fastapi import APIRouter                # 3. Third-party

from src.agent_service.core.config import X  # 4. First-party (src.*)
from .local_module import MyClass            # 5. Local relative
```

## Logging

```python
import logging
log = logging.getLogger(__name__)
```

- **Never** use `print()`. Always use `logging`.
- Prefer context-rich messages: `log.info(f"Processing session {sid}, tool={tool_name}")`
- Use `log.exception()` for caught exceptions (auto-attaches traceback).

## Error Handling

```python
try:
    await execute_query()
except ValueError as e:
    log.warning(f"Invalid input: {e}")
    raise HTTPException(status_code=400, detail=str(e)) from e
except Exception as e:
    log.error(f"Execution failed: {e}")
    raise HTTPException(status_code=500, detail="Internal server error") from e
```

- **Never** use bare `except:`.
- Always chain exceptions with `from e`.
- Log before re-raising.
- API errors → `fastapi.HTTPException`.

## Configuration & Secrets

- All env vars centralized in `src.agent_service.core.config`.
- Never call `os.getenv()` in business logic.
- Never hardcode secrets, URLs, or connection strings.

## Pydantic Models

- Define all API schemas in `src.agent_service.core.schemas.py` or co-located `models.py`.
- Use `model_validator` for cross-field validation.
- Keep models strict: avoid `model_config = ConfigDict(extra="allow")` unless justified.
