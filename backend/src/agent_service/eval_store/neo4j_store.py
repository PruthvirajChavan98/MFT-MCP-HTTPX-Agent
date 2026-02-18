from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from src.common.neo4j_mgr import Neo4jManager

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

    def ensure_schema(self) -> None:
        if self.__class__._schema_ready:
            return

        driver = Neo4jManager.get_driver()
        with driver.session() as session:
            # constraints (all single-field -> Community safe)
            session.run(
                "CREATE CONSTRAINT evaltrace_uniq IF NOT EXISTS FOR (t:EvalTrace) REQUIRE t.trace_id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT evalresult_uniq IF NOT EXISTS FOR (r:EvalResult) REQUIRE r.eval_id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT evalevent_key_uniq IF NOT EXISTS FOR (e:EvalEvent) REQUIRE e.event_key IS UNIQUE"
            )

            # indexes for dashboard filters
            session.run(
                "CREATE INDEX evaltrace_session IF NOT EXISTS FOR (t:EvalTrace) ON (t.session_id)"
            )
            session.run(
                "CREATE INDEX evaltrace_status IF NOT EXISTS FOR (t:EvalTrace) ON (t.status)"
            )
            session.run("CREATE INDEX evaltrace_model IF NOT EXISTS FOR (t:EvalTrace) ON (t.model)")
            session.run(
                "CREATE INDEX evalevent_trace_id IF NOT EXISTS FOR (e:EvalEvent) ON (e.trace_id)"
            )
            session.run("CREATE INDEX evalevent_seq IF NOT EXISTS FOR (e:EvalEvent) ON (e.seq)")
            session.run(
                "CREATE INDEX evalresult_metric IF NOT EXISTS FOR (r:EvalResult) ON (r.metric_name)"
            )

            # --- ADDED: Composite index for faster metric filtering/sorting ---
            session.run("""
                CREATE INDEX evalresult_metric_passed_updated_at_idx IF NOT EXISTS
                FOR (r:EvalResult) ON (r.metric_name, r.passed, r.updated_at)
            """)

            # fulltext search over event text
            session.run(
                "CREATE FULLTEXT INDEX evalevent_text IF NOT EXISTS FOR (e:EvalEvent) ON EACH [e.text]"
            )

            # vector indexes (safe even if embedding missing for now)
            session.run("""
                CREATE VECTOR INDEX evaltrace_embeddings IF NOT EXISTS
                FOR (t:EvalTrace) ON (t.embedding)
                OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
            """)
            session.run("""
                CREATE VECTOR INDEX evalresult_embeddings IF NOT EXISTS
                FOR (r:EvalResult) ON (r.embedding)
                OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
            """)

        self.__class__._schema_ready = True
        log.info("[eval_store] Neo4j schema ready")

    def upsert_trace(self, trace: Dict[str, Any]) -> None:
        self.ensure_schema()
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
          t.updated_at = datetime()
        """
        driver = Neo4jManager.get_driver()
        with driver.session() as session:
            session.run(q, **props)

    def upsert_events(self, trace_id: str, events: List[Dict[str, Any]]) -> None:
        self.ensure_schema()
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
        driver = Neo4jManager.get_driver()
        with driver.session() as session:
            session.run(q, trace_id=trace_id, events=norm)

    def upsert_evals(self, trace_id: str, evals: List[Dict[str, Any]]) -> None:
        self.ensure_schema()
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
        driver = Neo4jManager.get_driver()
        with driver.session() as session:
            session.run(q, trace_id=trace_id, evals=norm)
