import json
import redis
from typing import Any
from langchain_core.messages import RemoveMessage
from .config import KEEP_LAST, REDIS_URL

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

def is_user_authenticated(session_id: str) -> bool:
    """
    Directly checks Redis to see if the user has an active access_token.
    This avoids passing sensitive tool definitions to unauthenticated users.
    """
    try:
        # Use a localized client to ensure thread safety in async contexts if needed,
        # or rely on the fact that we are just reading a key.
        client = redis.from_url(REDIS_URL, decode_responses=True)
        # MCP Session Store saves data directly against the session_id key
        data_str = client.get(session_id)
        if not data_str:
            return False
        
        data = json.loads(str(data_str))
        # Check for the presence of the token set by auth_api.py
        return bool(data.get("access_token"))
    except Exception:
        return False


# --- add this helper ---
def _extract_tool_output(output: Any) -> str:
    """
    LangGraph/LangChain tool_end output is often a ToolMessage.
    DO NOT str() it (that produces content="..." name=... tool_call_id=...).
    We want the actual content string.
    """
    if output is None:
        return ""

    # ToolMessage / BaseMessage-like
    if hasattr(output, "content"):
        c = getattr(output, "content", "")
        return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)

    # Sometimes it's a dict wrapper
    if isinstance(output, dict):
        if "content" in output:
            c = output.get("content")
            return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)

        # Sometimes messages list
        msgs = output.get("messages")
        if isinstance(msgs, list):
            for m in reversed(msgs):
                if hasattr(m, "content"):
                    c = getattr(m, "content", "")
                    return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
                if isinstance(m, str):
                    return m

        # fallback
        return json.dumps(output, ensure_ascii=False)

    # Sometimes it's a list
    if isinstance(output, list):
        for m in reversed(output):
            if hasattr(m, "content"):
                c = getattr(m, "content", "")
                return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
            if isinstance(m, str):
                return m
        return json.dumps(output, ensure_ascii=False)

    # final fallback
    return str(output)