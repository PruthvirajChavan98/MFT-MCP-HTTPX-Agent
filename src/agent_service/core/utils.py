"""
Generic Utility Functions
Contains truly generic helpers that don't fit into specialized modules.
Keep this module lean - domain-specific utils belong in dedicated modules.
"""
import json
import logging
from typing import Any

log = logging.getLogger(__name__)


def normalize_result(result: Any) -> Any:
    """
    Sanitize output for logging and LLM context.
    Truncates massive JSONs to prevent context overflow.
    
    Args:
        result: Raw result from tool/LLM (list, dict, str, etc.)
        
    Returns:
        Normalized result, truncated if exceeds 8000 chars
        
    Examples:
        >>> normalize_result([ToolMessage(text='{"key": "value"}')])
        '{"key": "value"}'
        
        >>> normalize_result({"large": "data" * 2000})
        '{"large": "data..."}... [TRUNCATED]'
    """
    # Handle LangChain message lists
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
    
    # Handle dict results
    if isinstance(result, dict):
        dump = json.dumps(result, ensure_ascii=False)
        
        if len(dump) > 8000:
            return dump[:8000] + "... [TRUNCATED]"
        return dump
    
    # Return as-is for other types
    return result


def safe_json_loads(data: str, default: Any = None) -> Any:
    """
    Safely parse JSON with fallback value.
    
    Args:
        data: JSON string to parse
        default: Fallback value if parsing fails (default: None)
        
    Returns:
        Parsed JSON object or default value
        
    Examples:
        >>> safe_json_loads('{"key": "value"}')
        {'key': 'value'}
        
        >>> safe_json_loads('invalid json', default={})
        {}
    """
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        log.debug(f"JSON parsing failed: {e}")
        return default


def safe_json_dumps(data: Any, default: str = "{}") -> str:
    """
    Safely serialize to JSON with fallback.
    
    Args:
        data: Data to serialize
        default: Fallback string if serialization fails
        
    Returns:
        JSON string or default value
    """
    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        log.debug(f"JSON serialization failed: {e}")
        return default


def truncate_string(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """
    Truncate string to maximum length with suffix.
    
    Args:
        text: String to truncate
        max_length: Maximum length before truncation
        suffix: Suffix to append if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


# ============================================================================
# BACKWARD COMPATIBILITY ALIASES
# Import from specialized modules for legacy code support
# ============================================================================

from src.agent_service.core.session_utils import (
    valid_session_id,
    is_user_authenticated
)

from src.agent_service.core.streaming_utils import (
    _extract_tool_output
)

from src.agent_service.core.graph_utils import (
    keep_only_last_n_messages
)

# Mark as deprecated for IDE warnings
__deprecated__ = [
    "valid_session_id",
    "is_user_authenticated", 
    "_extract_tool_output",
    "keep_only_last_n_messages"
]
