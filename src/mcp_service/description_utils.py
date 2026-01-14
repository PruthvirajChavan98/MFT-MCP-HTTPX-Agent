import json
from pathlib import Path
import logging

log = logging.getLogger(name="tool_descriptions")

def _load_tool_descriptions() -> dict[str, str]:
    """
    Loads tool descriptions from a JSON file placed next to this python module.

    Expected JSON format:
      { "tool_descriptions": { "<tool_name>": "<description string>", ... } }
    """
    path = Path(__file__).with_name("tool_descriptions.json")
    if not path.exists():
        log.warning(f"tool_descriptions.json not found at {path}; tool descriptions will be empty.")
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        tool_desc = data.get("tool_descriptions", {})
        if not isinstance(tool_desc, dict):
            log.warning("tool_descriptions.json: 'tool_descriptions' is not a dict; ignoring.")
            return {}
        # ensure all values are strings
        out: dict[str, str] = {}
        for k, v in tool_desc.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v
        return out
    except Exception as e:
        log.warning(f"Failed to load tool_descriptions.json: {e}")
        return {}


TOOL_DESCRIPTIONS: dict[str, str] = _load_tool_descriptions()


def _d(tool_name: str) -> str:
    """Get description for a tool name (safe fallback)."""
    return TOOL_DESCRIPTIONS.get(tool_name, "")