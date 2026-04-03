"""
Generic Utility Functions
Contains truly generic helpers that don't fit into specialized modules.
"""

import json
import logging
from typing import Any

log = logging.getLogger(__name__)


def normalize_result(result: Any) -> Any:
    """Sanitize output for logging and LLM context. Truncates massive JSONs."""
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

        dump = json.dumps(result, ensure_ascii=False, indent=2)
        if len(dump) > 8000:
            return dump[:8000] + "... [TRUNCATED]"
        return dump

    if isinstance(result, dict):
        dump = json.dumps(result, ensure_ascii=False)
        if len(dump) > 8000:
            return dump[:8000] + "... [TRUNCATED]"
        return dump

    return result


# Backward compatibility imports
