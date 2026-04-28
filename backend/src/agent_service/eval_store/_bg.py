"""Shared fire-and-forget task helper for the eval pipeline.

Several code paths (trace/eval embedding, external ingest, future
async side effects) want to schedule an ``asyncio.Task`` without
awaiting it. Python silently garbage-collects tasks that have no
live reference, which means the coroutine can disappear mid-await
when the scheduler comes under GC pressure. This helper keeps the
task alive by parking it in a module-level set and dropping it once
``done`` fires.

Drop-in replacement for the ``_schedule`` pattern that was
previously duplicated inside ``api/eval_ingest.py``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

# Module-level set prevents `asyncio.Task` garbage collection mid-run.
# Callers should never touch this directly.
_BG_TASKS: set[asyncio.Task[Any]] = set()


def schedule(coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    """Fire the coroutine as a background task, strong-ref until done.

    Returns the task so callers can optionally inspect it in tests;
    production code should not await the returned task (that would
    defeat the fire-and-forget purpose).
    """
    task = asyncio.create_task(coro)
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)
    return task


def _pending_task_count() -> int:
    """Test helper — number of in-flight tasks. Not part of the
    public surface and not exported by ``__all__``."""
    return len(_BG_TASKS)


__all__ = ["schedule"]
