"""Safety net around the `PUBLIC_TOOLS` allow-list.

Every tool name in ``mcp_manager.PUBLIC_TOOLS`` is callable before the
caller has authenticated, so shipping a new entry expands the unauth
attack surface. These tests lock the catalogue down:

1. The retired ``mock_fintech_knowledge_base`` entry does NOT creep
   back in. A revert that re-adds the legacy KB wrapper fails CI here
   rather than silently doubling the KB tool count on the LLM's
   function list.
2. The canonical ``search_knowledge_base`` MCP tool IS in the set so
   guest-mode KB queries still succeed end-to-end.
3. The set stays exactly the four pre-auth tools we've reviewed.
"""

from __future__ import annotations

from src.agent_service.tools.mcp_manager import PUBLIC_TOOLS


def test_legacy_kb_tool_is_retired_from_public_tools() -> None:
    assert "mock_fintech_knowledge_base" not in PUBLIC_TOOLS, (
        "Legacy KB tool leaked back into PUBLIC_TOOLS. The MCP-side "
        "`search_knowledge_base` is the canonical KB tool; reviving "
        "the agent-side wrapper doubles the LLM's tool-descriptor "
        "payload and makes both tools hit the same Milvus collection."
    )


def test_canonical_kb_tool_is_registered_public() -> None:
    assert "search_knowledge_base" in PUBLIC_TOOLS, (
        "Pre-auth visitors need the KB tool to answer product questions "
        "before they've logged in — removing `search_knowledge_base` "
        "from PUBLIC_TOOLS breaks the guest-mode UX."
    )


def test_public_tools_catalogue_is_pinned() -> None:
    assert PUBLIC_TOOLS == {
        "generate_otp",
        "validate_otp",
        "is_logged_in",
        "search_knowledge_base",
    }, (
        "PUBLIC_TOOLS changed. Review the new entry for unauth-surface "
        "risk (the LLM can invoke it before the caller has a session) "
        "and update this pin set in the same PR."
    )
