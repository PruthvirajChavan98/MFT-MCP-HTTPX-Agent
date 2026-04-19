"""Session management and cost tracking endpoints."""

import logging

import uuid_utils  # Added dependency
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.agent_service.api.admin_auth import require_admin
from src.agent_service.api.shared_message_utils import _is_empty_content
from src.agent_service.core.config import DEFAULT_CHAT_MODEL, DEFAULT_CHAT_PROVIDER
from src.agent_service.core.prompts import prompt_manager
from src.agent_service.core.resource_resolver import ResourceResolver
from src.agent_service.core.schemas import SessionConfig, SessionInitResponse
from src.agent_service.core.session_cost import get_session_cost_tracker
from src.agent_service.core.session_utils import session_utils
from src.agent_service.data.config_manager import config_manager

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["sessions"])


@router.post("/sessions/init", response_model=SessionInitResponse)
async def initialize_session():
    """
    Initialize a new backend-managed session with UUIDv7.
    Sets up the default BYOK (Bring Your Own Key) configuration in Redis.
    """
    try:
        # Generate time-ordered UUIDv7
        sid = str(uuid_utils.uuid7())

        default_prompt = prompt_manager.get_default_system_prompt()
        default_model = DEFAULT_CHAT_MODEL
        default_provider = DEFAULT_CHAT_PROVIDER

        # Persist default configuration explicitly (BYOK - no keys set yet)
        await config_manager.set_config(
            session_id=sid,
            system_prompt=default_prompt,
            model_name=default_model,
            provider=default_provider,
        )

        log.info("Initialized new session %s with default BYOK config.", sid)

        return SessionInitResponse(
            session_id=sid,
            system_prompt=default_prompt,
            model_name=default_model,
            provider=default_provider,
        )
    except Exception as e:
        log.error("Session initialization error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to initialize session") from e


@router.get("/sessions")
async def list_active_sessions(_admin: None = Depends(require_admin)):
    """List all active sessions (admin only)."""
    try:
        sessions = await config_manager.list_sessions()
        return {"count": len(sessions), "sessions": sessions}
    except Exception as e:
        log.error("List sessions error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    request: Request,
    limit: int = Query(default=120, ge=1, le=500),
):
    """Retrieve chat messages from the LangGraph checkpointer.

    Returns messages in the frontend ChatMessage shape, hydrated from the
    server-side checkpoint rather than client-side localStorage.
    """
    try:
        sid = session_utils.validate_session_id(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    checkpointer = getattr(request.app.state, "checkpointer", None)
    if not checkpointer:
        raise HTTPException(status_code=503, detail="Checkpointer unavailable")

    config = {"configurable": {"thread_id": sid}}
    checkpoint_tuple = await checkpointer.aget_tuple(config)

    if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
        return {"session_id": sid, "messages": []}

    state = checkpoint_tuple.checkpoint.get("channel_values", {})
    raw_messages = state.get("messages", [])

    messages = []
    for i, msg in enumerate(raw_messages[-limit:]):
        msg_type = getattr(msg, "type", "")
        if msg_type not in ("human", "ai"):
            continue

        content = getattr(msg, "content", "")
        # LangGraph emits tool-call-only AIMessages (content="") between the human turn
        # and the final answer. Rendering each as a bubble produces blank cards in the UI.
        if msg_type == "ai" and _is_empty_content(content):
            continue

        kwargs = getattr(msg, "additional_kwargs", {}) or {}
        resp_meta = getattr(msg, "response_metadata", {}) or {}

        created = resp_meta.get("created")
        timestamp = int(created * 1000) if created else 0

        messages.append(
            {
                "id": kwargs.get("msg_id") or f"{sid}~{i}",
                "role": "user" if msg_type == "human" else "assistant",
                "content": content,
                "reasoning": str(kwargs.get("reasoning") or ""),
                "timestamp": timestamp,
                "status": "done",
                "traceId": kwargs.get("trace_id"),
                "provider": kwargs.get("provider") or resp_meta.get("model_provider"),
                "model": kwargs.get("model") or resp_meta.get("model_name"),
                "totalTokens": kwargs.get("total_tokens"),
                "cost": kwargs.get("cost"),
                "followUps": kwargs.get("follow_ups"),
            }
        )

    return {"session_id": sid, "messages": messages}


@router.get("/verify/{session_id}")
async def verify_session(session_id: str):
    """Verify if a session exists."""
    try:
        sid = session_utils.validate_session_id(session_id)
        exists = await config_manager.session_exists(sid)

        if not exists:
            raise HTTPException(status_code=404, detail="Session not found")

        return {"session_id": sid, "exists": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/config/{session_id}")
async def get_session_config(session_id: str):
    """Retrieve session configuration."""
    try:
        sid = session_utils.validate_session_id(session_id)
        stored = await config_manager.get_config(sid)
        stored_model_name = stored.get("model_name") or None
        stored_provider = stored.get("provider") or None

        return {
            "session_id": sid,
            "system_prompt": stored.get("system_prompt")
            or prompt_manager.get_default_system_prompt(),
            "model_name": stored_model_name or DEFAULT_CHAT_MODEL,
            "reasoning_effort": stored.get("reasoning_effort"),
            "has_openrouter_key": bool(stored.get("openrouter_api_key")),
            "has_nvidia_key": bool(stored.get("nvidia_api_key")),
            "has_groq_key": bool(stored.get("groq_api_key")),
            "provider": stored_provider
            or (
                ResourceResolver.infer_provider_from_model_name(stored_model_name)
                if stored_model_name
                else DEFAULT_CHAT_PROVIDER
            ),
            "is_customized": bool(stored),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/config")
async def config_session(config: SessionConfig):
    """Update session configuration."""
    try:
        sid = session_utils.validate_session_id(config.session_id)

        await config_manager.set_config(
            sid,
            system_prompt=config.system_prompt,
            model_name=config.model_name,
            reasoning_effort=config.reasoning_effort,
            openrouter_api_key=config.openrouter_api_key,
            nvidia_api_key=config.nvidia_api_key,
            groq_api_key=config.groq_api_key,
            provider=config.provider,
        )

        return {
            "status": "updated",
            "session_id": sid,
            "model": config.model_name,
            "provider": config.provider or "auto-detected",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/logout/{session_id}")
async def logout_session(session_id: str):
    """Clear session data and logout."""
    try:
        sid = session_utils.validate_session_id(session_id)
        await config_manager.delete_session(sid)

        log.info("Session %s logged out", sid)
        return {"status": "logged_out", "session_id": sid, "message": "Session cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# Cost tracking endpoints


@router.get("/sessions/{session_id}/cost")
async def get_session_cost(session_id: str):
    """
    Get detailed cost tracking for a session.

    Returns:
        - total_cost: Total USD spent
        - total_requests: Number of API calls
        - total_tokens: All token usage
        - by_model: Cost breakdown per model
        - by_provider: Cost breakdown per provider
        - average_cost_per_request: Mean cost
    """
    try:
        sid = session_utils.validate_session_id(session_id)
        tracker = get_session_cost_tracker()
        cost_data = await tracker.get_cost(sid)

        if not cost_data:
            return {
                "session_id": sid,
                "total_cost": 0.0,
                "total_requests": 0,
                "total_tokens": 0,
                "message": "No cost data tracked for this session",
            }

        return cost_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sessions/{session_id}/cost/history")
async def get_session_cost_history(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Max entries to return"),
):
    """
    Get recent cost history for session (chronological log).

    Args:
        limit: Max number of entries (1-1000, default 100)

    Returns:
        List of cost entries with timestamps, most recent first
    """
    try:
        sid = session_utils.validate_session_id(session_id)
        tracker = get_session_cost_tracker()
        history = await tracker.get_history(sid, limit=limit)

        return {"session_id": sid, "history": history, "count": len(history)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/sessions/{session_id}/cost")
async def reset_session_cost(session_id: str):
    """
    Reset cost tracking for a session.

    Note: This does NOT delete the session itself, only cost data.
    """
    try:
        sid = session_utils.validate_session_id(session_id)
        tracker = get_session_cost_tracker()
        success = await tracker.reset_cost(sid)

        if not success:
            raise HTTPException(status_code=404, detail=f"No cost data found for session {sid}")

        return {"session_id": sid, "status": "reset", "message": "Cost tracking reset successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sessions/summary")
async def get_all_sessions_cost_summary(_admin: None = Depends(require_admin)):
    """
    Get cost summary across all active sessions (admin only).

    Returns:
        - active_sessions: Count of sessions with cost data
        - total_cost: Sum across all sessions
        - total_requests: Total API calls
        - sessions: List of sessions sorted by cost (highest first)
    """
    tracker = get_session_cost_tracker()
    summary = await tracker.get_all_sessions_summary()
    return summary


@router.delete("/sessions/cleanup")
async def cleanup_corrupted_cost_keys(_admin: None = Depends(require_admin)):
    """
    Admin endpoint: Clean up corrupted cost tracking keys (admin only).

    This removes keys with wrong Redis types (from old implementations).
    """
    try:
        from src.agent_service.core.session_cost import SessionCostTracker
        from src.agent_service.core.session_utils import get_redis

        redis = await get_redis()
        pattern = f"{SessionCostTracker.COST_KEY_PREFIX}:*"

        deleted_keys = []

        async for key in redis.scan_iter(match=pattern, count=100):
            try:
                key_type = await redis.type(key)

                # Delete non-string keys (corrupted from old implementations)
                if key_type != "string":
                    await redis.delete(key)
                    deleted_keys.append({"key": key, "type": key_type})
                    log.info("Deleted corrupted key %s (type: %s)", key, key_type)
            except Exception as e:
                log.error("Failed to process key %s: %s", key, e)

        return {
            "status": "cleanup_complete",
            "deleted_keys": len(deleted_keys),
            "keys": deleted_keys[:20],  # Show first 20
        }
    except Exception as e:
        log.error("Cleanup failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
