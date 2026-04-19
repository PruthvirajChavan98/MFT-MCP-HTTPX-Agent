"""FAQ semantic search for MCP tools.

Thin async wrapper over the shared ``milvus_mgr.kb_faqs`` store from
``src.common.milvus_mgr``. mcp_service runs as a separate process from
agent_service, so it has its OWN ``milvus_mgr`` module-level singleton
with its own connection pool — sharing the implementation code, not the
runtime state.

Public API:
- ``semantic_search(query, limit)`` — async, returns list of {question, answer, score}
- ``format_results(results)``       — sync, formats the list as LLM-friendly plaintext

Design notes (Phase M1 plan 2026-04-11):
- Lazy connection: if ``milvus_mgr.kb_faqs`` is None on first call, we trigger
  ``milvus_mgr.aconnect()`` to initialize all three collections. mcp_service
  only uses ``kb_faqs`` but paying for the other two's initialization is
  cheaper than maintaining a separate init path.
- Graceful degradation: every failure path (empty query, connection failure,
  search exception) returns an empty list. The tool caller sees "no matching
  FAQs found" via ``format_results([])`` rather than a stack trace.
- Fixed ``k=limit`` (default 5) per plan decision D24-A. The MCP tool signature
  exposes ``query`` only, not ``limit``.
"""

from __future__ import annotations

import logging
from typing import Any

from src.common.milvus_mgr import milvus_mgr

log = logging.getLogger(__name__)


async def _ensure_kb_store_ready() -> bool:
    """Lazy-connect ``milvus_mgr`` if ``kb_faqs`` is not yet initialized.

    Returns True when ``milvus_mgr.kb_faqs`` is populated and ready for queries.
    Returns False on any connection failure; the caller should bail out cleanly.
    """
    if milvus_mgr.kb_faqs is not None:
        return True
    try:
        await milvus_mgr.aconnect()
    except Exception as e:
        log.warning("kb_search: milvus_mgr.aconnect() failed: %s", e)
        return False
    return milvus_mgr.kb_faqs is not None


async def semantic_search(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return top-k FAQ matches by cosine similarity.

    Args:
        query: The natural-language user query. Whitespace is stripped before
            searching. Empty or whitespace-only queries short-circuit to [].
        limit: Maximum number of results to return (default 5).

    Returns:
        List of dicts with ``question`` / ``answer`` / ``score`` keys. Score is
        a float in [0, 1] where higher = more relevant. Returns ``[]`` on any
        error (empty query, Milvus unreachable, search exception).
    """
    stripped = query.strip() if query else ""
    if not stripped:
        return []
    # Phase F2 (2026-04-18): swapped from langchain-milvus async wrapper to
    # raw pymilvus + executor. The langchain-milvus 0.3.3 +
    # asimilarity_search_with_score hangs indefinitely on our setup; the raw
    # helper composes OpenRouter embed + pymilvus Collection.search (both
    # proven to work in isolation) for the same return shape.
    try:
        results = await milvus_mgr.semantic_search_raw(
            collection="kb_faqs", query=stripped, limit=limit
        )
    except Exception as e:
        log.warning("kb_search: search failed for query=%r: %s", stripped[:80], e)
        return []
    return [
        {
            "question": doc.metadata.get("question", ""),
            "answer": doc.metadata.get("answer", ""),
            "score": float(score),
        }
        for doc, score in results
    ]


def format_results(results: list[dict[str, Any]]) -> str:
    """Format ``semantic_search`` output as LLM-friendly plaintext.

    Empty list → a one-line "no matches" message so the agent knows to fall
    back. Non-empty → numbered list with Q / A / score per entry.
    """
    if not results:
        return "No matching FAQs found."

    lines: list[str] = [f"Found {len(results)} matching FAQ(s):"]
    for i, r in enumerate(results, start=1):
        question = (r.get("question") or "").strip() or "(no question)"
        answer = (r.get("answer") or "").strip() or "(no answer)"
        score = float(r.get("score") or 0.0)
        lines.append("")
        lines.append(f"{i}. Q: {question}")
        lines.append(f"   A: {answer}")
        lines.append(f"   Relevance: {score:.2f}")
    return "\n".join(lines)
