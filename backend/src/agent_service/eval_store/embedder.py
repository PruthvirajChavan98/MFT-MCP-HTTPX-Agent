# ===== src/agent_service/eval_store/embedder.py =====
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from langchain_openai import OpenAIEmbeddings

from src.agent_service.core.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from src.common.neo4j_mgr import Neo4jManager

log = logging.getLogger("eval_embedder")

EMBED_MODEL = "openai/text-embedding-3-small"
EMBED_DIM = 1536


def _sha256(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _truncate(s: str, n: int = 8000) -> str:
    s = s or ""
    return s if len(s) <= n else (s[:n] + "\n...[TRUNCATED]")


def _build_trace_doc(trace: Dict[str, Any], events: List[Dict[str, Any]]) -> str:
    """
    Constructs a semantic document representing the entire trace.
    Order matters: We put the most semantically relevant parts (User Input, Final Output) first.
    """
    lines: List[str] = []

    # 1. High-Value Semantic Content (Top Priority)
    inputs = trace.get("inputs") or {}
    q = inputs.get("question") or inputs.get("input") or inputs.get("query")
    if q:
        lines.append(f"User Question: {q}")

    fo = trace.get("final_output")
    if fo:
        lines.append(f"Assistant Response: {fo}")

    lines.append("")  # Separator

    # 2. Key Metadata (for hybrid search context)
    lines.append(f"Trace ID: {trace.get('trace_id')}")
    if trace.get("session_id"):
        lines.append(f"Session ID: {trace.get('session_id')}")
    if trace.get("case_id"):
        lines.append(f"App/Case ID: {trace.get('case_id')}")
    if trace.get("error"):
        lines.append(f"Error: {trace.get('error')}")

    lines.append("")

    # 3. Tool Execution History (What actually happened)
    # We only capture tool names and their outputs to give context on *what* the agent did.
    tool_ends = [e for e in events if (e.get("event_type") == "tool_end")]
    if tool_ends:
        lines.append("Tools Used:")
        for e in tool_ends[:15]:  # Limit to first 15 tool calls to keep embedding focused
            name = e.get("name") or e.get("payload", {}).get("tool") or "tool"

            # Extract output safely
            out = (e.get("payload") or {}).get("output")
            if isinstance(e.get("payload"), dict) and "output" in e.get("payload"):  # type: ignore
                out = e.get("payload")["output"]  # type: ignore
            else:
                out = e.get("text")

            # Flatten JSON outputs if they are dicts
            out_s = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)

            # Truncate individual tool outputs so one huge payload doesn't dominate
            lines.append(f"- {name}: {str(out_s)[:500]}")

    return "\n".join(lines).strip()


def _build_eval_doc(ev: Dict[str, Any], evidence_events: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
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
    def __init__(self, openrouter_api_key: Optional[str] = None):
        """
        Initialize embedder with BYOK support.

        Args:
            openrouter_api_key: Session's OpenRouter key (BYOK). Falls back to env if None.
        """
        # Priority: Session key > Environment key
        self.key = openrouter_api_key or OPENROUTER_API_KEY
        self.enabled = bool(self.key)
        self.emb: Optional[OpenAIEmbeddings] = None

        if self.enabled:
            self.emb = OpenAIEmbeddings(
                model=EMBED_MODEL,
                api_key=self.key,  # type: ignore
                base_url=OPENROUTER_BASE_URL,
                check_embedding_ctx_length=False,
            )
            if openrouter_api_key:
                log.debug("[eval_embedder] Using session's OpenRouter key (BYOK)")
            else:
                log.debug("[eval_embedder] Using environment OpenRouter key (fallback)")
        else:
            log.warning("[eval_embedder] No OpenRouter API key available -> embeddings disabled")

    async def embed_trace_if_needed(
        self, trace: Dict[str, Any], events: List[Dict[str, Any]]
    ) -> None:
        if not self.enabled or not self.emb:
            log.debug("[eval_embedder] Skipping trace embedding - no API key")
            return

        trace_id = str(trace.get("trace_id") or "")
        if not trace_id:
            return

        doc = _build_trace_doc(trace, events)
        doc2 = _truncate(doc)

        # Hash to prevent re-embedding identical content
        h = _sha256(doc2)

        driver = Neo4jManager.get_driver()
        with driver.session() as session:
            existing = session.run(
                "MATCH (t:EvalTrace {trace_id:$trace_id}) RETURN t.doc_hash as h", trace_id=trace_id
            ).single()
            if existing and existing.get("h") == h:
                log.debug(f"[eval_embedder] Trace {trace_id} already embedded (hash match)")
                return

        # Generate Embedding
        try:
            vec = await self.emb.aembed_query(doc2)
        except Exception as e:
            log.error(f"[eval_embedder] Failed to embed trace {trace_id}: {e}")
            return

        # Save to Neo4j
        with driver.session() as session:
            session.run(
                """
                MATCH (t:EvalTrace {trace_id:$trace_id})
                SET t.doc = $doc,
                    t.doc_hash = $h,
                    t.embedding = $vec,
                    t.embedding_model = $m,
                    t.embedding_updated_at = datetime()
                """,
                trace_id=trace_id,
                doc=doc2,
                h=h,
                vec=vec,
                m=EMBED_MODEL,
            )
            log.info(f"[eval_embedder] Embedded trace {trace_id}")

    async def embed_eval_if_needed(self, trace_id: str, ev: Dict[str, Any]) -> None:
        if not self.enabled or not self.emb:
            log.debug("[eval_embedder] Skipping eval embedding - no API key")
            return

        eval_id = str(ev.get("eval_id") or "")
        if not eval_id or not trace_id:
            return

        # fetch evidence events
        evidence = ev.get("evidence") or []
        seqs = [x.get("seq") for x in evidence if isinstance(x, dict) and x.get("seq") is not None]
        ev_events: List[Dict[str, Any]] = []

        if seqs:
            driver = Neo4jManager.get_driver()
            with driver.session() as session:
                rows = session.run(
                    """
                    MATCH (e:EvalEvent {trace_id:$trace_id})
                    WHERE e.seq IN $seqs
                    RETURN e.seq as seq, e.event_type as event_type, e.name as name, e.text as text
                    ORDER BY e.seq ASC
                    """,
                    trace_id=trace_id,
                    seqs=seqs,
                )
                ev_events = [dict(r) for r in rows]

        doc = _build_eval_doc(ev, ev_events)
        doc2 = _truncate(doc)
        h = _sha256(doc2)

        driver = Neo4jManager.get_driver()
        with driver.session() as session:
            existing = session.run(
                "MATCH (r:EvalResult {eval_id:$eval_id}) RETURN r.doc_hash as h", eval_id=eval_id
            ).single()
            if existing and existing.get("h") == h:
                log.debug(f"[eval_embedder] Eval {eval_id} already embedded (hash match)")
                return

        try:
            vec = await self.emb.aembed_query(doc2)
        except Exception as e:
            log.error(f"[eval_embedder] Failed to embed eval {eval_id}: {e}")
            return

        with driver.session() as session:
            session.run(
                """
                MATCH (r:EvalResult {eval_id:$eval_id})
                SET r.doc = $doc,
                    r.doc_hash = $h,
                    r.embedding = $vec,
                    r.embedding_model = $m,
                    r.embedding_updated_at = datetime()
                """,
                eval_id=eval_id,
                doc=doc2,
                h=h,
                vec=vec,
                m=EMBED_MODEL,
            )
            log.debug(f"[eval_embedder] Embedded eval {eval_id}")
