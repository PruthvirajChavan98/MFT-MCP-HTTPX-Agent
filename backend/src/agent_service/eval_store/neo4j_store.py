from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from src.common.neo4j_mgr import neo4j_mgr

log = logging.getLogger("eval_store_neo4j")


def _json(x: Any) -> str:
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return json.dumps({"_str": str(x)}, ensure_ascii=False)


class EvalNeo4jStore:
    """
    Neo4j Community safe:
      - no MAP properties
      - use event_key (trace_id:seq) unique
      - store blobs as *_json strings
    """

    _schema_ready: bool = False

    async def ensure_schema(self) -> None:
        if self.__class__._schema_ready:
            return

        async with neo4j_mgr._driver.session() as session:
            # constraints (all single-field -> Community safe)
            await session.run(
                "CREATE CONSTRAINT evaltrace_uniq IF NOT EXISTS FOR (t:EvalTrace) REQUIRE t.trace_id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT evalresult_uniq IF NOT EXISTS FOR (r:EvalResult) REQUIRE r.eval_id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT evalevent_key_uniq IF NOT EXISTS FOR (e:EvalEvent) REQUIRE e.event_key IS UNIQUE"
            )

            # indexes for dashboard filters
            await session.run(
                "CREATE INDEX evaltrace_session IF NOT EXISTS FOR (t:EvalTrace) ON (t.session_id)"
            )
            await session.run(
                "CREATE INDEX evaltrace_status IF NOT EXISTS FOR (t:EvalTrace) ON (t.status)"
            )
            await session.run(
                "CREATE INDEX evaltrace_model IF NOT EXISTS FOR (t:EvalTrace) ON (t.model)"
            )
            await session.run(
                "CREATE INDEX evaltrace_question_category IF NOT EXISTS FOR (t:EvalTrace) ON (t.question_category)"
            )
            await session.run(
                "CREATE INDEX evaltrace_inline_guard_decision IF NOT EXISTS FOR (t:EvalTrace) ON (t.inline_guard_decision)"
            )
            await session.run(
                "CREATE INDEX evaltrace_inline_guard_risk_score IF NOT EXISTS FOR (t:EvalTrace) ON (t.inline_guard_risk_score)"
            )
            await session.run(
                "CREATE INDEX evaltrace_router_reason IF NOT EXISTS FOR (t:EvalTrace) ON (t.router_reason)"
            )
            await session.run(
                "CREATE INDEX evalevent_trace_id IF NOT EXISTS FOR (e:EvalEvent) ON (e.trace_id)"
            )
            await session.run(
                "CREATE INDEX evalevent_seq IF NOT EXISTS FOR (e:EvalEvent) ON (e.seq)"
            )
            await session.run(
                "CREATE INDEX evalresult_metric IF NOT EXISTS FOR (r:EvalResult) ON (r.metric_name)"
            )

            # --- ADDED: Composite index for faster metric filtering/sorting ---
            await session.run("""
                CREATE INDEX evalresult_metric_passed_updated_at_idx IF NOT EXISTS
                FOR (r:EvalResult) ON (r.metric_name, r.passed, r.updated_at)
            """)

            # fulltext search over event text
            await session.run(
                "CREATE FULLTEXT INDEX evalevent_text IF NOT EXISTS FOR (e:EvalEvent) ON EACH [e.text]"
            )

            # vector indexes (safe even if embedding missing for now)
            await session.run("""
                CREATE VECTOR INDEX evaltrace_embeddings IF NOT EXISTS
                FOR (t:EvalTrace) ON (t.embedding)
                OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
            """)
            await session.run("""
                CREATE VECTOR INDEX evalresult_embeddings IF NOT EXISTS
                FOR (r:EvalResult) ON (r.embedding)
                OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
            """)

        self.__class__._schema_ready = True
        log.info("[eval_store] Neo4j schema ready")

    async def upsert_trace(self, trace: Dict[str, Any]) -> None:
        await self.ensure_schema()
        trace_id = str(trace.get("trace_id") or "").strip()
        if not trace_id:
            raise ValueError("trace.trace_id missing")

        props = {
            "trace_id": trace_id,
            "case_id": trace.get("case_id"),
            "session_id": trace.get("session_id"),
            "provider": trace.get("provider"),
            "model": trace.get("model"),
            "endpoint": trace.get("endpoint"),
            "started_at": trace.get("started_at"),
            "ended_at": trace.get("ended_at"),
            "latency_ms": trace.get("latency_ms"),
            "status": trace.get("status"),
            "error": trace.get("error"),
            "inputs_json": _json(trace.get("inputs") or {}),
            "final_output": trace.get("final_output"),
            "tags_json": _json(trace.get("tags") or {}),
            "meta_json": _json(trace.get("meta") or {}),
            "question_category": trace.get("question_category"),
            "question_category_confidence": trace.get("question_category_confidence"),
            "question_category_source": trace.get("question_category_source"),
            "inline_guard_decision": trace.get("inline_guard_decision"),
            "inline_guard_reason_code": trace.get("inline_guard_reason_code"),
            "inline_guard_risk_score": trace.get("inline_guard_risk_score"),
            "router_backend": trace.get("router_backend"),
            "router_sentiment": trace.get("router_sentiment"),
            "router_sentiment_score": trace.get("router_sentiment_score"),
            "router_override": trace.get("router_override"),
            "router_reason": trace.get("router_reason"),
            "router_reason_score": trace.get("router_reason_score"),
        }

        q = """
        MERGE (t:EvalTrace {trace_id: $trace_id})
        SET
          t.case_id = $case_id,
          t.session_id = $session_id,
          t.provider = $provider,
          t.model = $model,
          t.endpoint = $endpoint,
          t.started_at = $started_at,
          t.ended_at = $ended_at,
          t.latency_ms = $latency_ms,
          t.status = $status,
          t.error = $error,
          t.inputs_json = $inputs_json,
          t.final_output = $final_output,
          t.tags_json = $tags_json,
          t.meta_json = $meta_json,
          t.question_category = $question_category,
          t.question_category_confidence = $question_category_confidence,
          t.question_category_source = $question_category_source,
          t.inline_guard_decision = $inline_guard_decision,
          t.inline_guard_reason_code = $inline_guard_reason_code,
          t.inline_guard_risk_score = $inline_guard_risk_score,
          t.router_backend = $router_backend,
          t.router_sentiment = $router_sentiment,
          t.router_sentiment_score = $router_sentiment_score,
          t.router_override = $router_override,
          t.router_reason = $router_reason,
          t.router_reason_score = $router_reason_score,
          t.updated_at = datetime()
        """
        async with neo4j_mgr._driver.session() as session:
            await session.run(q, props)

    async def upsert_events(self, trace_id: str, events: List[Dict[str, Any]]) -> None:
        await self.ensure_schema()
        if not events:
            return

        # Ensure each event has event_key + json strings
        norm = []
        for e in events:
            seq = int(e.get("seq") or 0)
            ek = str(e.get("event_key") or f"{trace_id}:{seq}")
            norm.append(
                {
                    "event_key": ek,
                    "seq": seq,
                    "ts": e.get("ts"),
                    "event_type": e.get("event_type"),
                    "name": e.get("name"),
                    "text": e.get("text"),
                    "payload_json": _json(e.get("payload") or {}),
                    "meta_json": _json(e.get("meta") or {}),
                }
            )

        q = """
        MATCH (t:EvalTrace {trace_id: $trace_id})
        UNWIND $events AS e
          MERGE (ev:EvalEvent {event_key: e.event_key})
          SET
            ev.trace_id = $trace_id,
            ev.seq = e.seq,
            ev.ts = e.ts,
            ev.event_type = e.event_type,
            ev.name = e.name,
            ev.text = e.text,
            ev.payload_json = e.payload_json,
            ev.meta_json = e.meta_json
          MERGE (t)-[:HAS_EVENT]->(ev)
        """
        async with neo4j_mgr._driver.session() as session:
            await session.run(q, {"trace_id": trace_id, "events": norm})

    async def upsert_evals(self, trace_id: str, evals: List[Dict[str, Any]]) -> None:
        await self.ensure_schema()
        if not evals:
            return

        norm = []
        for r in evals:
            evid_keys = r.get("evidence_event_keys") or []
            norm.append(
                {
                    "eval_id": r.get("eval_id"),
                    "metric_name": r.get("metric_name"),
                    "score": r.get("score"),
                    "passed": r.get("passed"),
                    "reasoning": r.get("reasoning"),
                    "evaluator_id": r.get("evaluator_id"),
                    "meta_json": _json(r.get("meta") or {}),
                    "evidence_json": _json(r.get("evidence") or []),
                    "evidence_event_keys": evid_keys,
                }
            )

        q = """
        MATCH (t:EvalTrace {trace_id: $trace_id})
        UNWIND $evals AS r
          MERGE (er:EvalResult {eval_id: r.eval_id})
          SET
            er.trace_id = $trace_id,
            er.metric_name = r.metric_name,
            er.score = r.score,
            er.passed = r.passed,
            er.reasoning = r.reasoning,
            er.evaluator_id = r.evaluator_id,
            er.meta_json = r.meta_json,
            er.evidence_json = r.evidence_json,
            er.updated_at = datetime()
          MERGE (t)-[:HAS_EVAL]->(er)

          WITH er, r
          UNWIND (CASE WHEN r.evidence_event_keys IS NULL THEN [] ELSE r.evidence_event_keys END) AS ek
            MATCH (ev:EvalEvent {event_key: ek})
            MERGE (er)-[:EVIDENCE]->(ev)
        """
        async with neo4j_mgr._driver.session() as session:
            await session.run(q, {"trace_id": trace_id, "evals": norm})
