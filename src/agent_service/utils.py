import json
from typing import Any
from langchain_core.messages import RemoveMessage
from .config import KEEP_LAST

def valid_session_id(session_id: object) -> str:
    """Ensures session_id is a valid non-empty string."""
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid

def normalize_result(result: Any) -> Any:
    """Sanitizes output (truncates massive JSONs) for logging/LLM context."""
    if isinstance(result, list) and result:
        first = result[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            try:
                parsed = json.loads(text)
                dump = json.dumps(parsed, ensure_ascii=False, indent=2)
                if len(dump) > 8000: 
                    return dump[:8000] + "... [TRUNCATED]"
                return dump
            except Exception:
                return text
    
    if isinstance(result, dict):
        dump = json.dumps(result, ensure_ascii=False)
        if len(dump) > 8000:
            return dump[:8000] + "... [TRUNCATED]"
        return dump  # Return stringified dict even if small
            
    return result

def keep_only_last_n_messages(state: dict, config: dict):
    """LangGraph reducer to keep history short."""
    msgs = list(state.get("messages", []))
    if len(msgs) <= KEEP_LAST:
        return {}
    return {"messages": [RemoveMessage(id=msgs[i].id) for i in range(len(msgs) - KEEP_LAST)]}
