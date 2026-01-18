from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse
from redis.asyncio import Redis

from src.agent_service.core.config import REDIS_URL

log = logging.getLogger("eval_live_api")
router = APIRouter()

STREAM_KEY = "eval:live"

def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return json.dumps({"_str": str(obj)}, ensure_ascii=False)

@router.get("/live")
async def eval_live(
    request: Request,
    cursor: str = Query("$", description="Redis stream cursor. Use '$' for only-new. Use '0-0' to replay."),
):
    """
    SSE live feed of new eval ingests.
    Backed by Redis Streams (XREAD BLOCK). 1 event = 1 ingest summary.
    Client reconnection: pass last cursor back (or use Last-Event-ID).
    Redis XREAD is blocking -> use a dedicated connection.
    """
    r = Redis.from_url(REDIS_URL, decode_responses=True)

    async def gen() -> AsyncGenerator[dict, None]:
        last_id = cursor or "$"

        # If browser reconnects with Last-Event-ID, prefer it
        try:
            lei = request.headers.get("last-event-id")
            if lei:
                last_id = lei.strip()
        except Exception:
            pass

        # Send a hello so client knows it’s connected
        yield {"event": "hello", "data": _safe_json({"stream": STREAM_KEY, "cursor": last_id})}

        try:
            while True:
                if await request.is_disconnected():
                    break

                # BLOCK waits for new messages; timeout keeps loop responsive to disconnects
                # Redis docs: XREAD BLOCK returns entries with IDs > last_id :contentReference[oaicite:4]{index=4}
                resp = await r.xread({STREAM_KEY: last_id}, block=15000, count=50)
                if not resp:
                    continue

                # resp looks like: [(stream_name, [(id, {field: val, ...}), ...])]
                for _stream, entries in resp:
                    for entry_id, fields in entries:
                        last_id = entry_id
                        payload: Dict[str, Any] = {"id": entry_id, **(fields or {})}

                        # IMPORTANT: set SSE id for automatic resume
                        yield {
                            "id": entry_id,
                            "event": "trace",
                            "data": _safe_json(payload),
                        }

        except Exception as e:
            log.error("eval_live stream error: %s", e)
            yield {"event": "error", "data": _safe_json({"error": str(e)})}
        finally:
            try:
                await r.close()
            except Exception:
                pass

    return EventSourceResponse(
        gen(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
