"""Regression lock: the canonical KB tool is ``search_knowledge_base``.

After the pure-LLM eval refactor, ``compute_non_llm_metrics`` returns
``[]`` and there are no regex rules to assert against. The only
remaining live consumer of the constant is the NBFC router's
answerability gate (``features/routing/answerability.py::_KB_TOOL_NAME``).
"""

from __future__ import annotations

from src.agent_service.features.routing.answerability import _KB_TOOL_NAME


def test_router_kb_tool_name_is_canonical() -> None:
    """If this fails, the router will silently mis-classify KB queries."""
    assert _KB_TOOL_NAME == "search_knowledge_base"
