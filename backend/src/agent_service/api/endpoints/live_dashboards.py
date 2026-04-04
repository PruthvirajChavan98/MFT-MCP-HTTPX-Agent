"""Real-time SSE endpoints for frontend dashboards."""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from src.agent_service.api.admin_auth import require_admin_key
from src.agent_service.core.event_bus import event_bus

log = logging.getLogger("live_dashboards")

router = APIRouter(prefix="/live", tags=["live-updates"])

HEARTBEAT_INTERVAL_SECONDS = 15.0
PUBSUB_POLL_TIMEOUT_SECONDS = 1.0
SSE_SEND_TIMEOUT_SECONDS = 30.0


@router.get("/global", dependencies=[Depends(require_admin_key)])
async def global_dashboard_feed(request: Request):
    """
    Multiplexed global stream for admin dashboards.
    Requires X-Admin-Key header.
    Streams security alerts, global cost upticks, and rate limit spikes.
    """

    async def event_generator():
        # Yield a connection ping to establish SSE
        yield {"event": "connected", "data": "global_feed_established"}

        # Subscribe to multiple channels using the event bus
        client = await event_bus._get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe("live:global:metrics", "live:global:security", "eval:live")

        try:
            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=PUBSUB_POLL_TIMEOUT_SECONDS
                )
                if message and message["type"] == "message":
                    try:
                        parsed = json.loads(message["data"])
                        yield {
                            "event": parsed.get("event", "update"),
                            "data": json.dumps(parsed.get("data", {})),
                        }
                    except Exception as exc:
                        log.debug("Global feed: failed to parse pubsub message: %s", exc)

                await asyncio.sleep(0.05)
        finally:
            await pubsub.close()

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Crucial for Nginx SSE bypass
        },
        ping=HEARTBEAT_INTERVAL_SECONDS,
        send_timeout=SSE_SEND_TIMEOUT_SECONDS,
    )


@router.get("/session/{session_id}")
async def session_specific_feed(session_id: str, request: Request):
    """Real-time feed scoped strictly to one user/session."""

    async def event_generator():
        channel = f"live:session:{session_id}"
        client = await event_bus._get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)

        try:
            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=PUBSUB_POLL_TIMEOUT_SECONDS
                )
                if message and message["type"] == "message":
                    try:
                        event = json.loads(message["data"])
                        yield {
                            "event": event.get("event", "update"),
                            "data": json.dumps(event.get("data", {})),
                        }
                    except Exception as exc:
                        log.debug("Session feed: failed to parse pubsub message: %s", exc)

                await asyncio.sleep(0.05)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return EventSourceResponse(
        event_generator(),
        headers={"X-Accel-Buffering": "no"},
        ping=HEARTBEAT_INTERVAL_SECONDS,
        send_timeout=SSE_SEND_TIMEOUT_SECONDS,
    )
