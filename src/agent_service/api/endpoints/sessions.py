"""Session management and cost tracking endpoints."""
import logging
from fastapi import APIRouter, HTTPException, Query

from src.agent_service.core.schemas import SessionConfig
from src.agent_service.core.session_utils import session_utils
from src.agent_service.core.session_cost import get_session_cost_tracker
from src.agent_service.core.config import MODEL_NAME
from src.agent_service.core.prompts import SYSTEM_PROMPT
from src.agent_service.data.config_manager import config_manager

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["sessions"])


@router.get("/sessions")
async def list_active_sessions():
    """List all active sessions."""
    try:
        sessions = await config_manager.list_sessions()
        return {"count": len(sessions), "sessions": sessions}
    except Exception as e:
        log.error(f"List sessions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/config/{session_id}")
async def get_session_config(session_id: str):
    """Retrieve session configuration."""
    try:
        sid = session_utils.validate_session_id(session_id)
        stored = await config_manager.get_config(sid)
        
        return {
            "session_id": sid,
            "system_prompt": stored.get("system_prompt") or SYSTEM_PROMPT.strip(),
            "model_name": stored.get("model_name") or MODEL_NAME,
            "reasoning_effort": stored.get("reasoning_effort"),
            "has_openrouter_key": bool(stored.get("openrouter_api_key")),
            "has_nvidia_key": bool(stored.get("nvidia_api_key")),
            "has_groq_key": bool(stored.get("groq_api_key")),
            "provider": stored.get("provider"),
            "is_customized": bool(stored),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
            provider=config.provider
        )
        
        return {
            "status": "updated",
            "session_id": sid,
            "model": config.model_name,
            "provider": config.provider or "auto-detected"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/logout/{session_id}")
async def logout_session(session_id: str):
    """Clear session data and logout."""
    try:
        sid = session_utils.validate_session_id(session_id)
        await config_manager.delete_session(sid)
        
        log.info(f"Session {sid} logged out")
        return {"status": "logged_out", "session_id": sid, "message": "Session cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
                "message": "No cost data tracked for this session"
            }
        
        return cost_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/cost/history")
async def get_session_cost_history(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Max entries to return")
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
        
        return {
            "session_id": sid,
            "history": history,
            "count": len(history)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
            raise HTTPException(
                status_code=404,
                detail=f"No cost data found for session {sid}"
            )
        
        return {
            "session_id": sid,
            "status": "reset",
            "message": "Cost tracking reset successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/summary")
async def get_all_sessions_cost_summary():
    """
    Get cost summary across all active sessions.
    
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
async def cleanup_corrupted_cost_keys():
    """
    Admin endpoint: Clean up corrupted cost tracking keys.
    
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
                    log.info(f"Deleted corrupted key {key} (type: {key_type})")
            except Exception as e:
                log.error(f"Failed to process key {key}: {e}")
        
        return {
            "status": "cleanup_complete",
            "deleted_keys": len(deleted_keys),
            "keys": deleted_keys[:20]  # Show first 20
        }
    except Exception as e:
        log.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))