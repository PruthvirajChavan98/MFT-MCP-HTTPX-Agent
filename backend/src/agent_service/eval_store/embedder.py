from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from langchain_core.documents import Document

from src.agent_service.core.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from src.agent_service.llm.client import get_owner_embeddings
from src.common.milvus_mgr import milvus_mgr

log = logging.getLogger("eval_embedder")

EMBED_MODEL = "openai/text-embedding-3-small"
EMBED_DIM = 1536


def _sha256(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _truncate(s: str, n: int = 8000) -> str:
    s = s or ""
    return s if len(s) <= n else (s[:n] + "\n...[TRUNCATED]")


def _build_trace_doc(trace: dict[str, Any], events: list[dict[str, Any]]) -> str:
    lines: list[str] = []

    inputs = trace.get("inputs") or {}
    q = inputs.get("question") or inputs.get("input") or inputs.get("query")
    if q:
        lines.append(f"User Question: {q}")

    fo = trace.get("final_output")
    if fo:
        lines.append(f"Assistant Response: {fo}")

    lines.append("")
    lines.append(f"Trace ID: {trace.get('trace_id')}")
    if trace.get("session_id"):
        lines.append(f"Session ID: {trace.get('session_id')}")
    if trace.get("case_id"):
        lines.append(f"App/Case ID: {trace.get('case_id')}")
    if trace.get("error"):
        lines.append(f"Error: {trace.get('error')}")

    lines.append("")

    tool_ends = [e for e in events if e.get("event_type") == "tool_end"]
    if tool_ends:
        lines.append("Tools Used:")
        for e in tool_ends[:15]:
            name = e.get("name") or (e.get("payload") or {}).get("tool") or "tool"
            out = (e.get("payload") or {}).get("output") or e.get("text")
            out_s = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
            lines.append(f"- {name}: {str(out_s)[:500]}")

    return "\n".join(lines).strip()


def _build_eval_doc(ev: dict[str, Any], evidence_events: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append(f"Metric: {ev.get('metric_name')}")
    lines.append(f"Status: {'PASSED' if ev.get('passed') else 'FAILED'}")
    lines.append(f"Score: {ev.get('score')}")
    lines.append("")
    lines.append(f"Reasoning: {ev.get('reasoning') or ''}")
    lines.append("")
    if evidence_events:
        lines.append("Evidence:")
        for e in evidence_events[:5]:
            lines.append(f"- {e.get('event_type')}: {str(e.get('text'))[:200]}")
    return "\n".join(lines).strip()


class EvalEmbedder:
    def __init__(self, openrouter_api_key: str | None = None) -> None:
        if openrouter_api_key:
            log.debug(
                "[eval_embedder] Ignoring session OpenRouter key; embeddings are owner-managed"
            )
        self.key = OPENROUTER_API_KEY
        self.enabled = bool(self.key)
        self.emb = None

        if self.enabled:
            self.emb = get_owner_embeddings(model=EMBED_MODEL, base_url=OPENROUTER_BASE_URL)
            log.debug("[eval_embedder] Using environment OpenRouter key")
        else:
            log.warning("[eval_embedder] No OpenRouter API key available — embeddings disabled")

    async def embed_trace_if_needed(
        self, pool: Any, trace: dict[str, Any], events: list[dict[str, Any]]
    ) -> None:
        if not self.enabled or not self.emb:
            return

        trace_id = str(trace.get("trace_id") or "").strip()
        if not trace_id:
            return

        doc = _build_trace_doc(trace, events)
        doc2 = _truncate(doc)
        h = _sha256(doc2)

        # Skip re-embedding if content hash unchanged
        row = await pool.fetchrow("SELECT doc_hash FROM eval_traces WHERE trace_id = $1", trace_id)
        if row and row["doc_hash"] == h:
            log.debug("[eval_embedder] Trace %s already embedded (hash match)", trace_id)
            return

        try:
            # Milvus varchar fields reject None (raises MilvusException code=1100).
            # dict.get(k, default) returns None when the key exists with a None
            # value — collector.py always inserts `case_id=None` on non-eval
            # sessions, so the "" default never applies. Use `or ""` to coerce
            # every field defensively.
            milvus_doc = Document(
                page_content=doc2,
                metadata={
                    "trace_id": trace_id,
                    "provider": trace.get("provider") or "",
                    "model": trace.get("model") or "",
                    "status": trace.get("status") or "",
                    "session_id": trace.get("session_id") or "",
                    "case_id": trace.get("case_id") or "",
                },
            )
            await milvus_mgr.eval_traces.aadd_documents(  # type: ignore[union-attr]
                [milvus_doc], ids=[trace_id]
            )
            await pool.execute(
                """
                UPDATE eval_traces
                SET doc = $1, doc_hash = $2, embedding_model = $3, embedding_updated_at = NOW()
                WHERE trace_id = $4
                """,
                doc2,
                h,
                EMBED_MODEL,
                trace_id,
            )
            log.info("[eval_embedder] Embedded trace %s", trace_id)
        except Exception as exc:
            log.error("[eval_embedder] Failed to embed trace %s: %s", trace_id, exc)

    async def embed_eval_if_needed(self, pool: Any, trace_id: str, ev: dict[str, Any]) -> None:
        if not self.enabled or not self.emb:
            return

        eval_id = str(ev.get("eval_id") or "").strip()
        if not eval_id or not trace_id:
            return

        # Fetch evidence events from PostgreSQL
        evidence = ev.get("evidence") or []
        seqs = [x.get("seq") for x in evidence if isinstance(x, dict) and x.get("seq") is not None]
        ev_events: list[dict[str, Any]] = []
        if seqs:
            rows = await pool.fetch(
                """
                SELECT seq, event_type, name, text
                FROM eval_events
                WHERE trace_id = $1 AND seq = ANY($2)
                ORDER BY seq ASC
                """,
                trace_id,
                seqs,
            )
            ev_events = [dict(r) for r in rows]

        doc = _build_eval_doc(ev, ev_events)
        doc2 = _truncate(doc)
        h = _sha256(doc2)

        row = await pool.fetchrow("SELECT doc_hash FROM eval_results WHERE eval_id = $1", eval_id)
        if row and row["doc_hash"] == h:
            log.debug("[eval_embedder] Eval %s already embedded (hash match)", eval_id)
            return

        try:
            milvus_doc = Document(
                page_content=doc2,
                metadata={
                    "eval_id": eval_id,
                    "trace_id": trace_id,
                    "metric_name": ev.get("metric_name") or "",
                    "passed": str(ev.get("passed") if ev.get("passed") is not None else ""),
                    "score": str(ev.get("score") if ev.get("score") is not None else ""),
                },
            )
            await milvus_mgr.eval_results.aadd_documents(  # type: ignore[union-attr]
                [milvus_doc], ids=[eval_id]
            )
            await pool.execute(
                """
                UPDATE eval_results
                SET doc = $1, doc_hash = $2, embedding_model = $3, embedding_updated_at = NOW()
                WHERE eval_id = $4
                """,
                doc2,
                h,
                EMBED_MODEL,
                eval_id,
            )
            log.debug("[eval_embedder] Embedded eval %s", eval_id)
        except Exception as exc:
            log.error("[eval_embedder] Failed to embed eval %s: %s", eval_id, exc)
