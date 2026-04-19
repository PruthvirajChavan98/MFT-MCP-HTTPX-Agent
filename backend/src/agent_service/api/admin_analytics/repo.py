"""Repository layer for admin-analytics SQL queries.

Follows the KnowledgeBaseRepo pattern: all methods accept ``pool`` as the
first parameter and carry no instance state.  SQL is co-located here so that
route handlers contain only request parsing + response shaping logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .category_map import ROUTER_REASON_TO_CATEGORY_CASE
from .utils import _pg_rows

# ---------------------------------------------------------------------------
# Overview queries
# ---------------------------------------------------------------------------


class AdminAnalyticsRepo:
    """Centralised data-access for admin analytics dashboards."""

    # -- Overview --------------------------------------------------------

    async def fetch_overview_stats(self, pool: Any) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """
            SELECT
                COUNT(*)                                              AS traces,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                AVG(COALESCE(latency_ms, 0))                         AS avg_latency_ms,
                MAX(started_at)                                      AS last_active
            FROM eval_traces
            """,
        )

    async def fetch_users(self, pool: Any, *, limit: int) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """
            SELECT
                session_id,
                COUNT(*) AS trace_count,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN status = 'error'   THEN 1 ELSE 0 END) AS error_count,
                AVG(COALESCE(latency_ms, 0))                         AS avg_latency_ms,
                MAX(started_at)                                      AS last_active
            FROM eval_traces
            WHERE session_id IS NOT NULL AND started_at IS NOT NULL
            GROUP BY session_id
            ORDER BY trace_count DESC
            LIMIT $1
            """,
            limit,
        )

    # -- Conversations ---------------------------------------------------

    async def fetch_conversations(
        self,
        pool: Any,
        *,
        search_pat: str | None,
        cursor_started_at: str | None,
        cursor_session_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """
            SELECT
                t.session_id,
                MAX(t.started_at) AS started_at,
                COUNT(*) AS message_count,
                (array_agg(t.model    ORDER BY t.started_at DESC))[1] AS model,
                (array_agg(t.provider ORDER BY t.started_at DESC))[1] AS provider,
                (array_agg(t.inputs_json ORDER BY t.started_at DESC))[1] AS inputs_json
            FROM eval_traces t
            WHERE t.session_id IS NOT NULL
              AND t.started_at IS NOT NULL
              AND (
                $1::text IS NULL
                OR LOWER(t.session_id)  LIKE $1
                OR LOWER(COALESCE(t.inputs_json::text, '')) LIKE $1
                OR LOWER(COALESCE(t.final_output, '')) LIKE $1
              )
            GROUP BY t.session_id
            HAVING (
                $2::timestamptz IS NULL
                OR MAX(t.started_at) < $2
                OR (MAX(t.started_at) = $2 AND t.session_id < $3)
            )
            ORDER BY started_at DESC, t.session_id DESC
            LIMIT $4
            """,
            search_pat,
            cursor_started_at,
            cursor_session_id,
            limit,
        )

    # -- Traces ----------------------------------------------------------

    async def fetch_traces_page(
        self,
        pool: Any,
        *,
        status: str | None,
        model: str | None,
        search_pat: str | None,
        category: str | None,
        cursor_started_at: str | None,
        cursor_trace_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        # NOTE: the f-string interpolates the shared CASE expression as a
        # literal SQL fragment (not a parameter). It is a constant defined
        # in our own module — no user input reaches the interpolation.
        sql = f"""
        SELECT
            trace_id, case_id, session_id, provider, model, endpoint,
            started_at, ended_at, latency_ms, status, error,
            inputs_json, final_output, meta_json
        FROM eval_traces
        WHERE started_at IS NOT NULL
          AND ($1::text IS NULL OR LOWER(COALESCE(status, '')) = $1)
          AND ($2::text IS NULL OR COALESCE(model, '') = $2)
          AND (
            $3::text IS NULL
            OR LOWER(trace_id) LIKE $3
            OR LOWER(COALESCE(session_id, '')) LIKE $3
            OR LOWER(COALESCE(inputs_json::text, '')) LIKE $3
            OR LOWER(COALESCE(final_output, '')) LIKE $3
          )
          AND (
            $4::text IS NULL
            OR question_category = $4
            OR COALESCE({ROUTER_REASON_TO_CATEGORY_CASE}, 'other') = $4
          )
          AND (
            $5::timestamptz IS NULL
            OR started_at < $5
            OR (started_at = $5 AND trace_id < $6)
          )
        ORDER BY started_at DESC, trace_id DESC
        LIMIT $7
        """
        return await _pg_rows(
            pool,
            sql,
            status,
            model,
            search_pat,
            category,
            cursor_started_at,
            cursor_trace_id,
            limit,
        )

    async def fetch_trace_by_id(self, pool: Any, trace_id: str) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            "SELECT * FROM eval_traces WHERE trace_id = $1",
            trace_id,
        )

    async def fetch_trace_events(self, pool: Any, trace_id: str) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            "SELECT * FROM eval_events WHERE trace_id = $1 ORDER BY seq ASC",
            trace_id,
        )

    async def fetch_trace_eval_results(self, pool: Any, trace_id: str) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """
            SELECT r.*,
                   ARRAY_AGG(ere.event_key) FILTER (WHERE ere.event_key IS NOT NULL)
                     AS evidence_event_keys
            FROM eval_results r
            LEFT JOIN eval_result_evidence ere ON ere.eval_id = r.eval_id
            WHERE r.trace_id = $1
            GROUP BY r.eval_id
            """,
            trace_id,
        )

    async def fetch_trace_shadow_judge(self, pool: Any, trace_id: str) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """SELECT helpfulness, faithfulness, policy_adherence, summary, evaluated_at, status
               FROM shadow_judge_evals WHERE trace_id = $1
               ORDER BY evaluated_at DESC LIMIT 1""",
            trace_id,
        )

    async def fetch_session_eval_traces(
        self, pool: Any, trace_ids: list[str]
    ) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """
            SELECT trace_id, meta_json, ended_at, updated_at
            FROM eval_traces
            WHERE trace_id = ANY($1::text[])
            """,
            trace_ids,
        )

    async def fetch_session_eval_results(
        self, pool: Any, trace_ids: list[str]
    ) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """
            SELECT trace_id, metric_name, score, passed
            FROM eval_results
            WHERE trace_id = ANY($1::text[])
            ORDER BY trace_id ASC, metric_name ASC
            """,
            trace_ids,
        )

    async def fetch_session_shadow_judges(
        self, pool: Any, trace_ids: list[str]
    ) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """
            SELECT DISTINCT ON (trace_id)
                   trace_id, helpfulness, faithfulness, policy_adherence, summary, evaluated_at, status
            FROM shadow_judge_evals
            WHERE trace_id = ANY($1::text[])
            ORDER BY trace_id ASC, evaluated_at DESC
            """,
            trace_ids,
        )

    async def fetch_session_traces_fallback(
        self, pool: Any, session_id: str, limit: int
    ) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """
            SELECT trace_id, started_at, inputs_json, final_output,
                   status, model, provider, meta_json
            FROM eval_traces
            WHERE session_id = $1
            ORDER BY started_at ASC
            LIMIT $2
            """,
            session_id,
            limit,
        )

    # -- Guardrails ------------------------------------------------------

    async def fetch_guardrail_trace_rows(
        self,
        pool: Any,
        *,
        limit: int,
        tenant_id: str,
        session_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """
            SELECT
                trace_id, session_id, endpoint, started_at, meta_json,
                inline_guard_decision, inline_guard_reason_code, inline_guard_risk_score
            FROM eval_traces
            WHERE started_at IS NOT NULL
              AND ($1::text IS NULL OR session_id = $1)
              AND ($2 = 'default' OR case_id = $2)
              AND ($3::timestamptz IS NULL OR started_at >= $3)
              AND ($4::timestamptz IS NULL OR started_at <= $4)
              AND (
                inline_guard_decision IS NOT NULL
                OR meta_json::text LIKE '%"inline_guard"%'
              )
            ORDER BY started_at DESC
            LIMIT $5
            """,
            session_id,
            tenant_id,
            start,
            end,
            limit,
        )

    async def fetch_shadow_judge_aggregates(self, pool: Any) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """
            SELECT
                COUNT(*) AS total_evals,
                AVG(COALESCE(helpfulness, 0))       AS avg_helpfulness,
                AVG(COALESCE(faithfulness, 0))       AS avg_faithfulness,
                AVG(COALESCE(policy_adherence, 0))   AS avg_policy_adherence
            FROM shadow_judge_evals
            """,
        )

    async def fetch_shadow_judge_failures(
        self, pool: Any, limit_failures: int
    ) -> list[dict[str, Any]]:
        return await _pg_rows(
            pool,
            """
            SELECT trace_id, session_id, model, summary, status,
                   helpfulness, faithfulness, policy_adherence, evaluated_at
            FROM shadow_judge_evals
            WHERE status <> 'ok'
               OR policy_adherence < 0.5
               OR faithfulness < 0.5
               OR helpfulness < 0.5
            ORDER BY evaluated_at DESC
            LIMIT $1
            """,
            limit_failures,
        )


# Module-level singleton, matching KnowledgeBaseRepo usage pattern
analytics_repo = AdminAnalyticsRepo()
