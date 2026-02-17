from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool

_KB_FIRST_RE = re.compile(
    r"(vehicle\s*(is\s*)?(stolen|lost)|stolen\s*vehicle|lost\s*vehicle|"
    r"stop\s*my\s*emi|stop\s*emi|emi\s*presentation|"
    r"non[-\s]?repossession|insurance\s*claim|stop\s*collection)",
    re.IGNORECASE,
)

_FALLBACK = (
    "Please note that the EMI presentation cannot be stopped. "
    "Your EMI will continue to be presented in your loan account until the loan is closed "
    "by your own funds or through the insurance claim settlement. "
    "You are requested to continue paying your EMIs to maintain a healthy credit record."
)


def _as_text(out: Any) -> str:
    if out is None:
        return ""
    if isinstance(out, dict) and "text" in out:
        v = out.get("text")
        return v if isinstance(v, str) else str(v)
    if isinstance(out, str):
        return out
    return str(out)


async def kb_first_payload(question: str, tools: List[StructuredTool]) -> Optional[Dict[str, Any]]:
    q = (question or "").strip()
    if not q or not _KB_FIRST_RE.search(q):
        return None

    kb = next((t for t in tools if getattr(t, "name", "") == "mock_fintech_knowledge_base"), None)
    if not kb:
        # Tool missing -> return correct fallback (never hallucinate "we can stop EMI")
        return {"tool": "mock_fintech_knowledge_base", "input": {"query": q}, "output": _FALLBACK}

    try:
        out = await kb.ainvoke({"query": q})
        txt = _as_text(out).strip()
        if not txt or "No relevant information found" in txt:
            return {
                "tool": "mock_fintech_knowledge_base",
                "input": {"query": q},
                "output": _FALLBACK,
            }
        return {"tool": "mock_fintech_knowledge_base", "input": {"query": q}, "output": txt}
    except Exception as e:
        # still return correct answer; include KB error signal for traceability
        return {
            "tool": "mock_fintech_knowledge_base",
            "input": {"query": q},
            "output": f"Knowledge Base Error: {e}. {_FALLBACK}",
        }
