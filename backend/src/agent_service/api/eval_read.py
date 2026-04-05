from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

from src.agent_service.api.admin_auth import require_admin_key
from src.agent_service.eval_store.status import (
    SHADOW_TIMED_OUT_SECONDS,
    SHADOW_WORKER_BACKLOG_SECONDS,
    TRACE_STATUS_GRACE_SECONDS,
    build_eval_status_payload,
    json_load_maybe,
)
from src.common.milvus_mgr import milvus_mgr

log = logging.getLogger("eval_read_api")
router = APIRouter(dependencies=[Depends(require_admin_key)])
_TRACE_STATUS_GRACE_SECONDS = TRACE_STATUS_GRACE_SECONDS
_SHADOW_WORKER_BACKLOG_SECONDS = SHADOW_WORKER_BACKLOG_SECONDS
_SHADOW_TIMED_OUT_SECONDS = SHADOW_TIMED_OUT_SECONDS

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _json_load_maybe(s: Any) -> Any:
    return json_load_maybe(s)


def _get_pool(request: Request) -> Any:
    return request.app.state.pool


def _raise_db_error(exc: Exception, operation: str) -> None:
    msg = str(exc)
    log.error("DB error in %s: %s", operation, msg)
    raise HTTPException(
        status_code=503,
        detail=f"Database unavailable ({operation}): {msg}",
    ) from exc


def _compress_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not events:
        return []
    compressed: list[dict[str, Any]] = []
    current_block: dict[str, Any] | None = None
    for evt in events:
        e = evt.copy()
        etype = e.get("event_type")
        ename = e.get("name")
        if ename == etype:
            e["name"] = None
        is_token = etype in ("token", "reasoning_token")
        is_tool = etype in ("tool_start", "tool_end")
        if current_block and is_token and current_block.get("event_type") == etype:
            new_text = str(e.get("text") or "")
            if current_block.get("text"):
                current_block["text"] += new_text
            else:
                current_block["text"] = new_text
            continue
        if is_tool and compressed:
            last = compressed[-1]
            if last.get("event_type") == etype and last.get("name") == ename:
                continue
        if current_block:
            compressed.append(current_block)
            current_block = None
        if is_token:
            current_block = e
            current_block["text"] = str(current_block.get("text") or "")
        else:
            compressed.append(e)
    if current_block:
        compressed.append(current_block)
    return compressed


# ─────────────────────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────────────────────


class VectorSearchRequest(BaseModel):
    kind: Literal["trace", "result"] = "trace"
    text: Optional[str] = None
    vector: Optional[list[float]] = None
    k: int = 10
    min_score: float = 0.0

    provider: Optional[str] = None
    model: Optional[str] = None
    status: Optional[str] = None
    metric_name: Optional[str] = None
    passed: Optional[bool] = None
    session_id: Optional[str] = None
    case_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# GET /eval/search
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/search")
async def eval_search(
    request: Request,
    limit: int = Query(50),
    offset: int = Query(0),
    session_id: Optional[str] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    case_id: Optional[str] = None,
    metric_name: Optional[str] = None,
    passed: Optional[bool] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    order: Literal["desc", "asc"] = "desc",
):
    pool = _get_pool(request)
    order_dir = "DESC" if order.lower() == "desc" else "ASC"
    metric_name = (metric_name or "").strip() or None

    # Base WHERE params ($1–$5)
    base_args: list[object] = [session_id, status, provider, model, case_id]

    # Build dynamic HAVING clause with positional asyncpg $N params
    metric_having: list[str] = []
    having_args: list[object] = []
    param_idx = len(base_args) + 1  # next param slot after $5

    if metric_name:
        metric_having.append(f"bool_or(r.metric_name = ${param_idx})")
        having_args.append(metric_name)
        param_idx += 1
    if passed is not None:
        metric_having.append(f"bool_or(r.passed = ${param_idx})")
        having_args.append(passed)
        param_idx += 1
    if min_score is not None:
        metric_having.append(f"bool_or(r.score >= ${param_idx})")
        having_args.append(float(min_score))
        param_idx += 1
    if max_score is not None:
        metric_having.append(f"bool_or(r.score <= ${param_idx})")
        having_args.append(float(max_score))
        param_idx += 1

    having_sql = ""
    if metric_having:
        having_sql = "HAVING " + " AND ".join(metric_having)

    try:
        # Count query: wrap subquery so fetchrow returns the true total
        if metric_having:
            count_row = await pool.fetchrow(
                f"""
                SELECT COUNT(*) AS total FROM (
                    SELECT t.trace_id
                    FROM eval_traces t
                    LEFT JOIN eval_results r ON r.trace_id = t.trace_id
                    WHERE ($1::text IS NULL OR t.session_id = $1)
                      AND ($2::text IS NULL OR t.status = $2)
                      AND ($3::text IS NULL OR t.provider = $3)
                      AND ($4::text IS NULL OR t.model = $4)
                      AND ($5::text IS NULL OR t.case_id = $5)
                    GROUP BY t.trace_id
                    {having_sql}
                ) sub
                """,
                *base_args,
                *having_args,
            )
        else:
            count_row = await pool.fetchrow(
                """
                SELECT COUNT(DISTINCT t.trace_id) AS total
                FROM eval_traces t
                WHERE ($1::text IS NULL OR t.session_id = $1)
                  AND ($2::text IS NULL OR t.status = $2)
                  AND ($3::text IS NULL OR t.provider = $3)
                  AND ($4::text IS NULL OR t.model = $4)
                  AND ($5::text IS NULL OR t.case_id = $5)
                """,
                *base_args,
            )
        total = int((count_row or {}).get("total") or 0)

        # Main query: offset/limit come after base + having params
        offset_idx = param_idx
        limit_idx = param_idx + 1

        rows = await pool.fetch(
            f"""
            SELECT
                t.trace_id, t.case_id, t.session_id, t.provider, t.model,
                t.endpoint, t.started_at, t.ended_at, t.latency_ms,
                t.status, t.error,
                COUNT(DISTINCT e.event_key) AS event_count,
                COUNT(DISTINCT r.eval_id)   AS eval_count,
                SUM(CASE WHEN r.passed THEN 1 ELSE 0 END) AS pass_count,
                COALESCE(
                    JSONB_AGG(
                        DISTINCT JSONB_BUILD_OBJECT(
                            'name', r.metric_name,
                            'score', r.score,
                            'passed', r.passed
                        )
                    ) FILTER (WHERE r.eval_id IS NOT NULL),
                    '[]'::jsonb
                ) AS scores
            FROM eval_traces t
            LEFT JOIN eval_events  e ON e.trace_id = t.trace_id
            LEFT JOIN eval_results r ON r.trace_id = t.trace_id
            WHERE ($1::text IS NULL OR t.session_id = $1)
              AND ($2::text IS NULL OR t.status = $2)
              AND ($3::text IS NULL OR t.provider = $3)
              AND ($4::text IS NULL OR t.model = $4)
              AND ($5::text IS NULL OR t.case_id = $5)
            GROUP BY
                t.trace_id, t.case_id, t.session_id, t.provider, t.model,
                t.endpoint, t.started_at, t.ended_at, t.latency_ms, t.status, t.error
            {having_sql}
            ORDER BY t.started_at {order_dir}
            OFFSET ${offset_idx} LIMIT ${limit_idx}
            """,
            *base_args,
            *having_args,
            offset,
            limit,
        )
    except Exception as exc:
        _raise_db_error(exc, "eval_search")

    items = [dict(r) for r in rows]
    for item in items:
        if isinstance(item.get("scores"), str):
            item["scores"] = _json_load_maybe(item["scores"])
    return {"total": total, "limit": limit, "offset": offset, "items": items}


# ─────────────────────────────────────────────────────────────────────────────
# GET /eval/sessions
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/sessions")
async def eval_sessions(
    request: Request,
    limit: int = Query(25),
    offset: int = Query(0),
    app_id: Optional[str] = None,
):
    pool = _get_pool(request)
    try:
        count_row = await pool.fetchrow(
            """
            SELECT COUNT(DISTINCT session_id) AS total
            FROM eval_traces
            WHERE ($1::text IS NULL OR case_id = $1)
            """,
            app_id or None,
        )
        total = int((count_row or {}).get("total") or 0)

        rows = await pool.fetch(
            """
            SELECT
                t.session_id,
                MAX(t.case_id)     AS app_id,
                COUNT(*)           AS trace_count,
                MAX(t.started_at)  AS last_active,
                (array_agg(t.model       ORDER BY t.started_at DESC))[1] AS last_model,
                (array_agg(t.status      ORDER BY t.started_at DESC))[1] AS last_status
            FROM eval_traces t
            WHERE t.session_id IS NOT NULL
              AND ($1::text IS NULL OR t.case_id = $1)
            GROUP BY t.session_id
            ORDER BY last_active DESC
            OFFSET $2 LIMIT $3
            """,
            app_id or None,
            offset,
            limit,
        )
    except Exception as exc:
        _raise_db_error(exc, "eval_sessions")

    return {"total": total, "limit": limit, "offset": offset, "items": [dict(r) for r in rows]}


# ─────────────────────────────────────────────────────────────────────────────
# GET /eval/trace/{trace_id}
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/trace/{trace_id}")
async def eval_trace(request: Request, trace_id: str):
    pool = _get_pool(request)
    try:
        trace_row = await pool.fetchrow("SELECT * FROM eval_traces WHERE trace_id = $1", trace_id)
        if not trace_row:
            raise HTTPException(status_code=404, detail="Trace not found")

        event_rows = await pool.fetch(
            "SELECT * FROM eval_events WHERE trace_id = $1 ORDER BY seq ASC", trace_id
        )
        eval_rows = await pool.fetch(
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
    except HTTPException:
        raise
    except Exception as exc:
        _raise_db_error(exc, "eval_trace")

    trace_obj = dict(trace_row)
    for k in ("inputs_json", "tags_json", "meta_json"):
        trace_obj[k] = _json_load_maybe(trace_obj.get(k))

    events = [dict(e) for e in event_rows]
    for e in events:
        e["payload_json"] = _json_load_maybe(e.get("payload_json"))
        e["meta_json"] = _json_load_maybe(e.get("meta_json"))

    evals = [dict(r) for r in eval_rows]
    for r in evals:
        r["meta_json"] = _json_load_maybe(r.get("meta_json"))
        r["evidence_json"] = _json_load_maybe(r.get("evidence_json"))

    return {"trace": trace_obj, "events": _compress_events(events), "evals": evals}


# ─────────────────────────────────────────────────────────────────────────────
# GET /eval/trace/{trace_id}/eval-status
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/trace/{trace_id}/eval-status")
async def trace_eval_status(request: Request, trace_id: str) -> dict[str, Any]:
    """Return evaluation status for a trace (polled by frontend after chat response)."""
    pool = _get_pool(request)

    try:
        trace_row = await pool.fetchrow(
            """
            SELECT trace_id, meta_json, ended_at, updated_at
            FROM eval_traces
            WHERE trace_id = $1
            """,
            trace_id,
        )

        if not trace_row:
            return {
                "trace_id": trace_id,
                "status": "not_found",
                "reason": None,
                "inline_evals": None,
                "shadow_judge": None,
            }

        # 2. Fetch inline eval results
        result_rows = await pool.fetch(
            """
            SELECT metric_name, score, passed
            FROM eval_results
            WHERE trace_id = $1
            ORDER BY metric_name ASC
            """,
            trace_id,
        )

        # 3. Fetch shadow judge evaluation
        shadow_row = await pool.fetchrow(
            """
            SELECT helpfulness, faithfulness, policy_adherence, summary, evaluated_at
            FROM shadow_judge_evals
            WHERE trace_id = $1
            ORDER BY evaluated_at DESC
            LIMIT 1
            """,
            trace_id,
        )
    except Exception as exc:
        _raise_db_error(exc, "trace_eval_status")

    return build_eval_status_payload(
        trace_id=trace_id,
        trace_row=dict(trace_row),
        result_rows=[dict(row) for row in result_rows],
        shadow_row=dict(shadow_row) if shadow_row else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /eval/fulltext
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/fulltext")
async def eval_fulltext(
    request: Request,
    q: str = Query(..., min_length=1),
    kind: Literal["event", "trace", "result"] = "event",
    limit: int = 50,
    offset: int = 0,
    trace_id: Optional[str] = None,
):
    pool = _get_pool(request)

    try:
        if kind == "event":
            rows = await pool.fetch(
                """
                SELECT
                    'EvalEvent'::text AS label,
                    ts_rank(fts, plainto_tsquery('english', $1)) AS score,
                    trace_id, event_key, seq,
                    text AS preview
                FROM eval_events
                WHERE fts @@ plainto_tsquery('english', $1)
                  AND ($2::text IS NULL OR trace_id = $2)
                ORDER BY score DESC
                OFFSET $3 LIMIT $4
                """,
                q,
                trace_id,
                offset,
                limit,
            )
        elif kind == "trace":
            rows = await pool.fetch(
                """
                SELECT
                    'EvalTrace'::text AS label,
                    ts_rank(fts, plainto_tsquery('english', $1)) AS score,
                    trace_id, NULL::text AS event_key, NULL::int AS seq,
                    final_output AS preview
                FROM eval_traces
                WHERE fts @@ plainto_tsquery('english', $1)
                  AND ($2::text IS NULL OR trace_id = $2)
                ORDER BY score DESC
                OFFSET $3 LIMIT $4
                """,
                q,
                trace_id,
                offset,
                limit,
            )
        else:  # result
            rows = await pool.fetch(
                """
                SELECT
                    'EvalResult'::text AS label,
                    ts_rank(
                        to_tsvector('english', coalesce(reasoning, '')),
                        plainto_tsquery('english', $1)
                    ) AS score,
                    trace_id, eval_id, NULL::text AS event_key, NULL::int AS seq,
                    reasoning AS preview
                FROM eval_results
                WHERE to_tsvector('english', coalesce(reasoning, ''))
                        @@ plainto_tsquery('english', $1)
                  AND ($2::text IS NULL OR trace_id = $2)
                ORDER BY score DESC
                OFFSET $3 LIMIT $4
                """,
                q,
                trace_id,
                offset,
                limit,
            )
    except Exception as exc:
        _raise_db_error(exc, "eval_fulltext")

    return {
        "kind": kind,
        "q": q,
        "limit": limit,
        "offset": offset,
        "items": [dict(r) for r in rows],
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /eval/vector-search
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/vector-search")
async def eval_vector_search(
    request: Request,
    req: VectorSearchRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
):
    pool = _get_pool(request)

    use_vector = req.vector is not None and len(req.vector) > 0
    query_text = (req.text or "").strip()

    if not use_vector and not query_text:
        raise HTTPException(status_code=400, detail="Provide either 'vector' or 'text'")

    # Build Milvus metadata filter expression
    filters: list[str] = []
    if req.kind == "trace":
        if req.provider:
            filters.append(f'provider == "{req.provider}"')
        if req.model:
            filters.append(f'model == "{req.model}"')
        if req.status:
            filters.append(f'status == "{req.status}"')
        if req.session_id:
            filters.append(f'session_id == "{req.session_id}"')
        if req.case_id:
            filters.append(f'case_id == "{req.case_id}"')
    else:
        if req.metric_name:
            filters.append(f'metric_name == "{req.metric_name}"')
        if req.passed is not None:
            filters.append(f'passed == "{str(req.passed)}"')

    expr = " and ".join(filters) or None

    try:
        store = milvus_mgr.eval_traces if req.kind == "trace" else milvus_mgr.eval_results
        if store is None:
            raise RuntimeError("Milvus store not initialized")

        kwargs: dict[str, Any] = {"k": int(req.k)}
        if expr:
            kwargs["expr"] = expr

        if use_vector:
            if req.vector is None:
                raise HTTPException(
                    status_code=400,
                    detail="Vector embedding is required for vector search",
                )
            hits = await store.asimilarity_search_with_score_by_vector(req.vector, **kwargs)
        else:
            hits = await store.asimilarity_search_with_score(query_text, **kwargs)
    except Exception as exc:
        log.error("Milvus vector search failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "store_unavailable",
                "operation": "eval_vector_search",
                "message": str(exc),
            },
        ) from exc

    # Filter by min_score
    hits = [(doc, score) for doc, score in hits if score >= req.min_score]

    if not hits:
        return {"kind": req.kind, "k": req.k, "min_score": req.min_score, "items": []}

    # Batch-fetch full PG metadata
    ids = [
        doc.metadata.get("trace_id" if req.kind == "trace" else "eval_id", "") for doc, _ in hits
    ]
    ids = [i for i in ids if i]

    try:
        if req.kind == "trace":
            pg_rows = await pool.fetch(
                """
                SELECT trace_id, inputs_json, final_output, provider, model,
                       session_id, case_id, status, started_at
                FROM eval_traces WHERE trace_id = ANY($1)
                """,
                ids,
            )
            pg_meta = {r["trace_id"]: dict(r) for r in pg_rows}
        else:
            pg_rows = await pool.fetch(
                """
                SELECT r.eval_id, r.trace_id, r.metric_name, r.score, r.passed, r.reasoning,
                       t.provider, t.model, t.session_id, t.case_id, t.status
                FROM eval_results r
                LEFT JOIN eval_traces t ON t.trace_id = r.trace_id
                WHERE r.eval_id = ANY($1)
                """,
                ids,
            )
            pg_meta = {r["eval_id"]: dict(r) for r in pg_rows}
    except Exception as exc:
        _raise_db_error(exc, "eval_vector_search_pg_fetch")

    out = []
    for doc, score in hits:
        meta = doc.metadata
        id_key = "trace_id" if req.kind == "trace" else "eval_id"
        node_id = meta.get(id_key, "")
        pg = pg_meta.get(node_id, {})

        inputs = _json_load_maybe(pg.get("inputs_json"))
        question = None
        if isinstance(inputs, dict):
            question = inputs.get("question") or inputs.get("input") or inputs.get("query")

        out.append(
            {
                "score": float(score),
                "trace_id": pg.get("trace_id") or meta.get("trace_id"),
                "eval_id": pg.get("eval_id") if req.kind == "result" else None,
                "metric_name": pg.get("metric_name") if req.kind == "result" else None,
                "status": pg.get("status"),
                "provider": pg.get("provider"),
                "model": pg.get("model"),
                "session_id": pg.get("session_id"),
                "app_id": pg.get("case_id"),
                "question": question,
                "final_output": pg.get("final_output"),
                "reasoning": pg.get("reasoning") if req.kind == "result" else None,
            }
        )

    return {"kind": req.kind, "k": req.k, "min_score": req.min_score, "items": out}


# ─────────────────────────────────────────────────────────────────────────────
# GET /eval/metrics/summary
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/metrics/summary")
async def eval_metrics_summary(
    request: Request,
    metric_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    status: Optional[str] = None,
):
    pool = _get_pool(request)
    try:
        rows = await pool.fetch(
            """
            SELECT
                r.metric_name,
                COUNT(*)                                       AS count,
                SUM(CASE WHEN r.passed THEN 1 ELSE 0 END)     AS pass_count,
                AVG(COALESCE(r.score, 0))                      AS avg_score
            FROM eval_results r
            LEFT JOIN eval_traces t ON t.trace_id = r.trace_id
            WHERE r.metric_name IS NOT NULL
              AND ($1::text IS NULL OR r.metric_name = $1)
              AND ($2::text IS NULL OR t.provider = $2)
              AND ($3::text IS NULL OR t.model = $3)
              AND ($4::text IS NULL OR t.status = $4)
            GROUP BY r.metric_name
            ORDER BY r.metric_name ASC
            """,
            metric_name,
            provider,
            model,
            status,
        )
    except Exception as exc:
        _raise_db_error(exc, "eval_metrics_summary")

    items = [dict(r) for r in rows]
    for item in items:
        count = int(item.get("count") or 0)
        pass_count = int(item.get("pass_count") or 0)
        item["pass_rate"] = (pass_count / count) if count else 0.0

    total_evals = sum(int(r.get("count", 0)) for r in items)
    total_passes = sum(int(r.get("pass_count", 0)) for r in items)
    overall_rate = (total_passes / total_evals) if total_evals > 0 else 0.0

    return {
        "items": items,
        "total_metrics": len(items),
        "total_evals": total_evals,
        "overall_pass_rate": overall_rate,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /eval/metrics/failures
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/metrics/failures")
async def eval_metrics_failures(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    metric_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    status: Optional[str] = None,
):
    pool = _get_pool(request)
    metric_name = (metric_name or "").strip() or None

    try:
        rows = await pool.fetch(
            """
            SELECT
                r.eval_id, r.trace_id, r.metric_name, r.score, r.passed,
                r.evaluator_id, r.reasoning, r.updated_at,
                t.status AS trace_status, t.provider, t.model, t.endpoint,
                t.session_id, t.case_id, t.started_at
            FROM eval_results r
            LEFT JOIN eval_traces t ON t.trace_id = r.trace_id
            WHERE r.passed = false
              AND ($1::text IS NULL OR r.metric_name = $1)
              AND ($2::text IS NULL OR t.provider = $2)
              AND ($3::text IS NULL OR t.model = $3)
              AND ($4::text IS NULL OR t.status = $4)
            ORDER BY r.updated_at DESC
            OFFSET $5 LIMIT $6
            """,
            metric_name,
            provider,
            model,
            status,
            offset,
            limit,
        )
    except Exception as exc:
        _raise_db_error(exc, "eval_metrics_failures")

    return {"limit": limit, "offset": offset, "items": [dict(r) for r in rows]}


# ─────────────────────────────────────────────────────────────────────────────
# GET /eval/question-types
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/question-types")
async def question_types(request: Request, limit: int = 200):
    pool = _get_pool(request)
    try:
        rows = await pool.fetch(
            """
            SELECT
                COALESCE(
                    question_category,
                    CASE router_reason
                        WHEN 'lead_intent_new_loan'         THEN 'loan_products_and_eligibility'
                        WHEN 'eligibility_offer'            THEN 'loan_products_and_eligibility'
                        WHEN 'loan_terms_rates'             THEN 'loan_products_and_eligibility'
                        WHEN 'application_status_approval'  THEN 'application_status_and_approval'
                        WHEN 'disbursal'                    THEN 'disbursal_and_bank_credit'
                        WHEN 'kyc_verification'             THEN 'profile_kyc_and_access'
                        WHEN 'otp_login_app_tech'           THEN 'profile_kyc_and_access'
                        WHEN 'emi_payment_reflecting'       THEN 'emi_payments_and_charges'
                        WHEN 'nach_autodebit_bounce'        THEN 'emi_payments_and_charges'
                        WHEN 'charges_fees_penalty'         THEN 'emi_payments_and_charges'
                        WHEN 'statement_receipt'            THEN 'emi_payments_and_charges'
                        WHEN 'foreclosure_partpayment'      THEN 'foreclosure_and_closure'
                        WHEN 'collections_harassment'       THEN 'collections_and_recovery'
                        WHEN 'fraud_security'               THEN 'fraud_and_security'
                        WHEN 'customer_support'             THEN 'customer_support_channels'
                        WHEN 'unknown'                      THEN 'other'
                        ELSE NULL
                    END,
                    'Unknown'
                ) AS reason,
                COUNT(*) AS n
            FROM (
                SELECT question_category, router_reason
                FROM eval_traces
                WHERE started_at IS NOT NULL
                ORDER BY started_at DESC
                LIMIT $1
            ) sub
            GROUP BY reason
            ORDER BY n DESC
            """,
            limit,
        )
    except Exception as exc:
        _raise_db_error(exc, "eval_question_types")

    total = sum(int(r["n"]) for r in rows) or 1
    items = [
        {"reason": r["reason"], "count": int(r["n"]), "pct": float(r["n"]) / total} for r in rows
    ]
    return {"limit": limit, "total": total, "items": items}
