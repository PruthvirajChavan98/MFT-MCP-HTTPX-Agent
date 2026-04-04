import logging
from pathlib import Path

import yaml

log = logging.getLogger(name="tool_descriptions")


def _load_tool_descriptions() -> dict[str, str]:
    """
    Loads tool descriptions from a YAML file placed next to this module.

    Expected YAML format:
      <tool_name>: |
        multiline description
    """
    path = Path(__file__).with_name("tool_descriptions.yaml")
    if not path.exists():
        log.warning(
            "tool_descriptions.yaml not found at %s; tool descriptions will be empty.", path
        )
        return {}

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            log.warning("tool_descriptions.yaml: root is not a mapping; ignoring.")
            return {}

        # ensure all values are strings
        out: dict[str, str] = {}
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v
        return out
    except Exception as e:
        log.warning("Failed to load tool_descriptions.yaml: %s", e)
        return {}


TOOL_DESCRIPTIONS: dict[str, str] = _load_tool_descriptions()


def _d(tool_name: str) -> str:
    """Get description for a tool name (safe fallback)."""
    return TOOL_DESCRIPTIONS.get(tool_name, "")
