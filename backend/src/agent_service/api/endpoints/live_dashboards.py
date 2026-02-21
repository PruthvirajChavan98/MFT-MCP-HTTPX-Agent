"""Real-time SSE endpoints for frontend dashboards."""

import asyncio
import json
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse

from src.agent_service.core.event_bus import event_bus
from src.agent_service.api.admin_auth import require_admin_key

router = APIRouter(prefix="/live", tags=["live-updates"])

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
                
                # Non-blocking get_message
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    try:
                        parsed = json.loads(message["data"])
                        yield {"event": parsed.get("event", "update"), "data": json.dumps(parsed.get("data", {}))}
                    except Exception:
                        pass
                else:
                    await asyncio.sleep(0.1) # Yield to event loop
        finally:
            await pubsub.close()

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # Crucial for Nginx SSE bypass
        }
    )

@router.get("/session/{session_id}")
async def session_specific_feed(session_id: str, request: Request):
    """Real-time feed scoped strictly to one user/session."""
    async def event_generator():
        async for event in event_bus.subscribe(f"live:session:{session_id}"):
            if await request.is_disconnected():
                break
            yield {"event": event.get("event", "update"), "data": json.dumps(event.get("data", {}))}
            
    return EventSourceResponse(event_generator(), headers={"X-Accel-Buffering": "no"})
