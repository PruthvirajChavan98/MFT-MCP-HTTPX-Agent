from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

log = logging.getLogger("eval_store_pg")


def _json(x: Any) -> str:
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return json.dumps({"_str": str(x)}, ensure_ascii=False)


def _coerce_timestamptz(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise TypeError(f"Unsupported timestamptz value: {type(value).__name__}")


class EvalSchemaUnavailableError(RuntimeError):
    """Raised when the PostgreSQL eval schema is not present."""


class EvalPgStore:
    """Relational eval store backed by PostgreSQL (asyncpg pool).

    Replaces EvalNeo4jStore — all Cypher MERGE/SET → INSERT ... ON CONFLICT DO UPDATE.
    Schema is created by ``backend/infra/sql/02_eval_schema.sql`` which is mounted as
    a Docker init script. ``ensure_schema()`` now verifies the required tables exist
    before the agent starts serving traffic.
    """

    _schema_ready: bool = False

    async def ensure_schema(self, pool: Any) -> None:
        """Verify required eval tables exist before serving traffic."""
        if self.__class__._schema_ready:
            return
        if pool is None:
            raise EvalSchemaUnavailableError(
                "PostgreSQL pool unavailable while verifying eval schema."
            )
        # Verify tables exist; if not, schema SQL was not applied
        row = await pool.fetchrow("SELECT to_regclass('public.eval_traces') AS tbl")
        if row and row["tbl"] is not None:
            self.__class__._schema_ready = True
            log.info("eval_store: PostgreSQL schema verified")
            return
        raise EvalSchemaUnavailableError(
            "eval_traces table not found; ensure 02_eval_schema.sql ran before agent startup."
        )

    async def upsert_trace(self, pool: Any, trace: dict[str, Any]) -> None:
        trace_id = str(trace.get("trace_id") or "").strip()
        if not trace_id:
            raise ValueError("trace.trace_id missing")
        started_at = _coerce_timestamptz(trace.get("started_at"))
        ended_at = _coerce_timestamptz(trace.get("ended_at"))

        await pool.execute(
            """
            INSERT INTO eval_traces (
                trace_id, case_id, session_id, provider, model, endpoint,
                started_at, ended_at, latency_ms, status, error,
                inputs_json, final_output, tags_json, meta_json,
                question_category, question_category_confidence, question_category_source,
                inline_guard_decision, inline_guard_reason_code, inline_guard_risk_score,
                router_backend, router_sentiment, router_sentiment_score,
                router_override, router_reason, router_reason_score,
                updated_at
            ) VALUES (
                $1,$2,$3,$4,$5,$6,
                $7,$8,$9,$10,$11,
                $12,$13,$14,$15,
                $16,$17,$18,
                $19,$20,$21,
                $22,$23,$24,
                $25,$26,$27,
                NOW()
            )
            ON CONFLICT (trace_id) DO UPDATE SET
                case_id                       = EXCLUDED.case_id,
                session_id                    = EXCLUDED.session_id,
                provider                      = EXCLUDED.provider,
                model                         = EXCLUDED.model,
                endpoint                      = EXCLUDED.endpoint,
                started_at                    = EXCLUDED.started_at,
                ended_at                      = EXCLUDED.ended_at,
                latency_ms                    = EXCLUDED.latency_ms,
                status                        = EXCLUDED.status,
                error                         = EXCLUDED.error,
                inputs_json                   = EXCLUDED.inputs_json,
                final_output                  = EXCLUDED.final_output,
                tags_json                     = EXCLUDED.tags_json,
                meta_json                     = EXCLUDED.meta_json,
                question_category             = EXCLUDED.question_category,
                question_category_confidence  = EXCLUDED.question_category_confidence,
                question_category_source      = EXCLUDED.question_category_source,
                inline_guard_decision         = EXCLUDED.inline_guard_decision,
                inline_guard_reason_code      = EXCLUDED.inline_guard_reason_code,
                inline_guard_risk_score       = EXCLUDED.inline_guard_risk_score,
                router_backend                = EXCLUDED.router_backend,
                router_sentiment              = EXCLUDED.router_sentiment,
                router_sentiment_score        = EXCLUDED.router_sentiment_score,
                router_override               = EXCLUDED.router_override,
                router_reason                 = EXCLUDED.router_reason,
                router_reason_score           = EXCLUDED.router_reason_score,
                updated_at                    = NOW()
            """,
            trace_id,
            trace.get("case_id"),
            trace.get("session_id"),
            trace.get("provider"),
            trace.get("model"),
            trace.get("endpoint"),
            started_at,
            ended_at,
            trace.get("latency_ms"),
            trace.get("status"),
            trace.get("error"),
            _json(trace.get("inputs") or {}),
            trace.get("final_output"),
            _json(trace.get("tags") or {}),
            _json(trace.get("meta") or {}),
            trace.get("question_category"),
            trace.get("question_category_confidence"),
            trace.get("question_category_source"),
            trace.get("inline_guard_decision"),
            trace.get("inline_guard_reason_code"),
            trace.get("inline_guard_risk_score"),
            trace.get("router_backend"),
            trace.get("router_sentiment"),
            trace.get("router_sentiment_score"),
            trace.get("router_override"),
            trace.get("router_reason"),
            trace.get("router_reason_score"),
        )

    async def upsert_events(self, pool: Any, trace_id: str, events: list[dict[str, Any]]) -> None:
        if not events:
            return

        rows = []
        for e in events:
            seq = int(e.get("seq") or 0)
            event_key = str(e.get("event_key") or f"{trace_id}:{seq}")
            rows.append(
                (
                    event_key,
                    trace_id,
                    seq,
                    _coerce_timestamptz(e.get("ts")),
                    e.get("event_type"),
                    e.get("name"),
                    e.get("text"),
                    _json(e.get("payload") or {}),
                    _json(e.get("meta") or {}),
                )
            )

        await pool.executemany(
            """
            INSERT INTO eval_events (
                event_key, trace_id, seq, ts, event_type, name, text, payload_json, meta_json
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT (event_key) DO UPDATE SET
                seq          = EXCLUDED.seq,
                ts           = EXCLUDED.ts,
                event_type   = EXCLUDED.event_type,
                name         = EXCLUDED.name,
                text         = EXCLUDED.text,
                payload_json = EXCLUDED.payload_json,
                meta_json    = EXCLUDED.meta_json
            """,
            rows,
        )

    async def upsert_evals(self, pool: Any, trace_id: str, evals: list[dict[str, Any]]) -> None:
        if not evals:
            return

        for r in evals:
            eval_id = str(r.get("eval_id") or "").strip()
            if not eval_id:
                continue

            await pool.execute(
                """
                INSERT INTO eval_results (
                    eval_id, trace_id, metric_name, score, passed,
                    reasoning, evaluator_id, meta_json, evidence_json, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,NOW())
                ON CONFLICT (eval_id) DO UPDATE SET
                    metric_name  = EXCLUDED.metric_name,
                    score        = EXCLUDED.score,
                    passed       = EXCLUDED.passed,
                    reasoning    = EXCLUDED.reasoning,
                    evaluator_id = EXCLUDED.evaluator_id,
                    meta_json    = EXCLUDED.meta_json,
                    evidence_json= EXCLUDED.evidence_json,
                    updated_at   = NOW()
                """,
                eval_id,
                trace_id,
                r.get("metric_name"),
                r.get("score"),
                r.get("passed"),
                r.get("reasoning"),
                r.get("evaluator_id"),
                _json(r.get("meta") or {}),
                _json(r.get("evidence") or []),
            )

            # evidence links: eval_result_evidence junction table
            evidence_keys: list[str] = r.get("evidence_event_keys") or []
            if evidence_keys:
                evidence_rows = [(eval_id, ek) for ek in evidence_keys]
                await pool.executemany(
                    """
                    INSERT INTO eval_result_evidence (eval_id, event_key)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                    """,
                    evidence_rows,
                )


eval_pg_store = EvalPgStore()

# ---------------------------------------------------------------------------
# Shared pool registry — set by app lifespan for modules without request context
# (runtime_trace_store, shadow_eval, standalone workers)
# ---------------------------------------------------------------------------
_shared_pool: object = None


def configure_shared_pool(pool: object) -> None:
    """Wire the asyncpg pool at startup so non-request modules can upsert traces."""
    global _shared_pool
    _shared_pool = pool


def get_shared_pool() -> object:
    """Return the shared asyncpg pool, or None if not yet configured."""
    return _shared_pool
