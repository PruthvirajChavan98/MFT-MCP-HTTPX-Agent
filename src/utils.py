import json
from typing import Any

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