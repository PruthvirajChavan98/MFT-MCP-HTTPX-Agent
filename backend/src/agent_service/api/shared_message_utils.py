"""Shared helpers for LangChain message handling across admin + public APIs.

Both ``sessions.py`` (public chat widget hydration) and
``admin_analytics/traces.py`` (admin Conversations transcript) need to filter
out LangGraph's intermediate tool-call-only AIMessages whose ``content`` is
empty. Having one implementation prevents the two filters from drifting.
"""

from __future__ import annotations


def _is_empty_content(content: object) -> bool:
    """True if a LangChain AIMessage has no user-visible text.

    Handles string content (OpenAI/Groq) and list-of-blocks content (Anthropic).
    """
    if content is None:
        return True
    if isinstance(content, str):
        return not content.strip()
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                text = block.get("text", "")
                if isinstance(text, str) and text.strip():
                    return False
            elif isinstance(block, str) and block.strip():
                return False
        return True
    return False
