# ===== src/agent_service/api/eval_read.py =====
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from src.agent_service.core.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from src.common.neo4j_mgr import Neo4jManager

log = logging.getLogger("eval_read_api")
router = APIRouter()

# -----------------------------
# Helpers
# -----------------------------


def _json_load_maybe(s: Any) -> Any:
    if not isinstance(s, str):
        return s
    ss = s.strip()
    if not ss:
        return s
    if (ss.startswith("{") and ss.endswith("}")) or (ss.startswith("[") and ss.endswith("]")):
        try:
            return json.loads(ss)
        except:
            return s
    return s


def _rows(q: str, params: dict) -> List[dict]:
    driver = Neo4jManager.get_driver()
    with driver.session() as session:
        return [dict(r) for r in session.run(q, **params)]  # type: ignore


def _one(q: str, params: dict) -> Optional[dict]:
    driver = Neo4jManager.get_driver()
    with driver.session() as session:
        r = session.run(q, **params).single()  # type: ignore
        return dict(r) if r else None


def _compress_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not events:
        return []
    compressed = []
    current_block = None
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


# -----------------------------
# Models
# -----------------------------


class VectorSearchRequest(BaseModel):
    kind: Literal["trace", "result"] = "trace"
    text: Optional[str] = None
    vector: Optional[List[float]] = None
    k: int = 10
    min_score: float = 0.0

    # Filters
    provider: Optional[str] = None
    model: Optional[str] = None
    status: Optional[str] = None
    metric_name: Optional[str] = None
    passed: Optional[bool] = None

    # ✅ NEW: ID Filters
    session_id: Optional[str] = None
    case_id: Optional[str] = None


# -----------------------------
# GET /eval/search
# -----------------------------
@router.get("/search")
async def eval_search(
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
    order_dir = "DESC" if order.lower() == "desc" else "ASC"
    if metric_name:
        metric_name = metric_name.strip()

    where = []
    params = {
        "limit": limit,
        "offset": offset,
        "session_id": session_id,
        "status": status,
        "provider": provider,
        "model": model,
        "case_id": case_id,
        "metric_name": metric_name,
        "passed": passed,
        "min_score": min_score,
        "max_score": max_score,
    }
    where.append("($session_id IS NULL OR t.session_id = $session_id)")
    where.append("($status IS NULL OR t.status = $status)")
    where.append("($provider IS NULL OR t.provider = $provider)")
    where.append("($model IS NULL OR t.model = $model)")
    where.append("($case_id IS NULL OR t.case_id = $case_id)")

    metric_filters = []
    if metric_name:
        metric_filters.append("x.metric_name = $metric_name")
    if passed is not None:
        metric_filters.append("x.passed = $passed")
    if min_score is not None:
        metric_filters.append("x.score >= $min_score")
    if max_score is not None:
        metric_filters.append("x.score <= $max_score")

    if metric_filters:
        filter_str = " AND ".join(metric_filters)
        metric_clause = f"OPTIONAL MATCH (t)-[:HAS_EVAL]->(mr:EvalResult) WITH t, collect(mr) AS evals, [x IN collect(mr) WHERE {filter_str}] AS matching WHERE size(matching) > 0"
    else:
        metric_clause = (
            "OPTIONAL MATCH (t)-[:HAS_EVAL]->(mr:EvalResult) WITH t, collect(mr) AS evals"
        )

    q_count = (
        f"MATCH (t:EvalTrace) WHERE {' AND '.join(where)} {metric_clause} RETURN count(t) AS total"
    )

    q_items = f"""
    MATCH (t:EvalTrace) WHERE {' AND '.join(where)} {metric_clause}
    OPTIONAL MATCH (t)-[:HAS_EVENT]->(ev:EvalEvent)
    WITH t, evals, count(ev) AS event_count
    RETURN t.trace_id AS trace_id, t.case_id AS case_id, t.session_id AS session_id, t.provider AS provider, t.model AS model, t.endpoint AS endpoint, t.started_at AS started_at, t.ended_at AS ended_at, t.latency_ms AS latency_ms, t.status AS status, t.error AS error, event_count, size(evals) AS eval_count, reduce(p = 0, x IN evals | p + CASE WHEN x.passed = true THEN 1 ELSE 0 END) AS pass_count, [e IN evals | {{name: e.metric_name, score: e.score, passed: e.passed}}] as scores
    ORDER BY t.started_at {order_dir} SKIP $offset LIMIT $limit
    """

    total_row = await run_in_threadpool(_one, q_count, params)
    total = int((total_row or {}).get("total") or 0)
    items = await run_in_threadpool(_rows, q_items, params)
    return {"total": total, "limit": limit, "offset": offset, "items": items}


# -----------------------------
# GET /eval/sessions
# -----------------------------
@router.get("/sessions")
async def eval_sessions(
    limit: int = Query(25), offset: int = Query(0), app_id: Optional[str] = None
):
    where_clause = ""
    params = {"limit": limit, "offset": offset}
    if app_id and app_id.strip():
        where_clause = "WHERE t.case_id = $app_id"
        params["app_id"] = app_id.strip()  # type: ignore

    q_count = f"MATCH (t:EvalTrace) {where_clause} WITH t.session_id as sid RETURN count(DISTINCT sid) as total"

    q_items = f"""
    MATCH (t:EvalTrace)
    {where_clause}
    WITH t.session_id AS sid, t
    ORDER BY t.started_at DESC

    WITH sid, collect(t) AS traces
    WITH sid, traces, traces[0] as latest, size(traces) as trace_count,
         [x IN traces WHERE x.case_id IS NOT NULL | x.case_id] as app_ids

    RETURN
        sid AS session_id,
        head(app_ids) AS app_id,
        trace_count,
        latest.started_at AS last_active,
        latest.model AS last_model,
        latest.status AS last_status
    ORDER BY last_active DESC
    SKIP $offset LIMIT $limit
    """

    total_row = await run_in_threadpool(_one, q_count, params)
    total = int((total_row or {}).get("total") or 0)

    items = await run_in_threadpool(_rows, q_items, params)
    return {"total": total, "limit": limit, "offset": offset, "items": items}


# -----------------------------
# GET /eval/trace/{trace_id}
# -----------------------------
@router.get("/trace/{trace_id}")
async def eval_trace(trace_id: str):
    q = "MATCH (t:EvalTrace {trace_id: $trace_id}) OPTIONAL MATCH (t)-[:HAS_EVENT]->(e:EvalEvent) WITH t, e ORDER BY e.seq ASC WITH t, [x IN collect(CASE WHEN e IS NULL THEN null ELSE {event_key: e.event_key, trace_id: e.trace_id, seq: e.seq, ts: e.ts, event_type: e.event_type, name: e.name, text: e.text, payload_json: e.payload_json, meta_json: e.meta_json} END) WHERE x IS NOT NULL] AS events OPTIONAL MATCH (t)-[:HAS_EVAL]->(r:EvalResult) OPTIONAL MATCH (r)-[:EVIDENCE]->(ev:EvalEvent) WITH t, events, r, collect(ev.event_key) AS evidence_event_keys WITH t, events, [x IN collect(CASE WHEN r IS NULL THEN null ELSE {eval_id: r.eval_id, trace_id: r.trace_id, metric_name: r.metric_name, score: r.score, passed: r.passed, reasoning: r.reasoning, evaluator_id: r.evaluator_id, meta_json: r.meta_json, evidence_json: r.evidence_json, evidence_event_keys: evidence_event_keys} END) WHERE x IS NOT NULL] AS evals RETURN {trace_id: t.trace_id, case_id: t.case_id, session_id: t.session_id, provider: t.provider, model: t.model, endpoint: t.endpoint, started_at: t.started_at, ended_at: t.ended_at, latency_ms: t.latency_ms, status: t.status, error: t.error, inputs_json: t.inputs_json, final_output: t.final_output, tags_json: t.tags_json, meta_json: t.meta_json} AS trace, events AS events, evals AS evals"
    row = await run_in_threadpool(_one, q, {"trace_id": trace_id})
    if not row:
        raise HTTPException(status_code=404, detail="Trace not found")
    trace_obj = row["trace"]
    for k in ("inputs_json", "tags_json", "meta_json"):
        trace_obj[k] = _json_load_maybe(trace_obj.get(k))
    events = row.get("events") or []
    for e in events:
        e["payload_json"] = _json_load_maybe(e.get("payload_json"))
        e["meta_json"] = _json_load_maybe(e.get("meta_json"))
    compressed_events = _compress_events(events)
    evals = row.get("evals") or []
    for r in evals:
        r["meta_json"] = _json_load_maybe(r.get("meta_json"))
        r["evidence_json"] = _json_load_maybe(r.get("evidence_json"))
    return {"trace": trace_obj, "events": compressed_events, "evals": evals}


# -----------------------------
# GET /eval/fulltext
# -----------------------------
@router.get("/fulltext")
async def eval_fulltext(
    q: str = Query(..., min_length=1),
    kind: Literal["event", "trace", "result"] = "event",
    limit: int = 50,
    offset: int = 0,
    trace_id: Optional[str] = None,
):
    index = {"event": "evalevent_text", "trace": "evaltrace_text", "result": "evalresult_text"}[
        kind
    ]
    cypher = "CALL db.index.fulltext.queryNodes($index, $q, {skip: $offset, limit: $limit}) YIELD node, score WHERE ($trace_id IS NULL OR node.trace_id = $trace_id) RETURN labels(node) AS labels, score AS score, node.trace_id AS trace_id, node.event_key AS event_key, node.seq AS seq, node.eval_id AS eval_id, node.metric_name AS metric_name, coalesce(node.text, node.final_output, node.reasoning) AS preview ORDER BY score DESC"
    rows = await run_in_threadpool(
        _rows,
        cypher,
        {"index": index, "q": q, "limit": limit, "offset": offset, "trace_id": trace_id},
    )
    return {"index": index, "q": q, "limit": limit, "offset": offset, "items": rows}


# -----------------------------
# POST /eval/vector-search (UPDATED)
# -----------------------------
@router.post("/vector-search")
async def eval_vector_search(
    req: VectorSearchRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
):
    if not req.vector and not req.text:
        raise HTTPException(status_code=400, detail="Provide either 'vector' or 'text'")

    vector = req.vector
    if vector is None:
        key = (x_openrouter_key or OPENROUTER_API_KEY or "").strip()
        if not key:
            raise HTTPException(status_code=400, detail="No OpenRouter key available")
        emb = OpenAIEmbeddings(
            model="openai/text-embedding-3-small",
            api_key=key,  # type: ignore
            base_url=OPENROUTER_BASE_URL,
            check_embedding_ctx_length=False,
        )
        vector = await emb.aembed_query(req.text or "")

    index = "evaltrace_embeddings" if req.kind == "trace" else "evalresult_embeddings"
    where = ["score >= $min_score"]

    params: Dict[str, Any] = {
        "index": index,
        "k": int(req.k),
        "vector": vector,
        "min_score": float(req.min_score),
        "provider": req.provider,
        "model": req.model,
        "status": req.status,
        "metric_name": req.metric_name,
        "passed": req.passed,
        # Filters
        "session_id": req.session_id,
        "case_id": req.case_id,
    }

    if req.kind == "trace":
        where.append("($provider IS NULL OR node.provider = $provider)")
        where.append("($model IS NULL OR node.model = $model)")
        where.append("($status IS NULL OR node.status = $status)")
        # ✅ Add ID filters
        where.append("($session_id IS NULL OR node.session_id = $session_id)")
        where.append("($case_id IS NULL OR node.case_id = $case_id)")
    else:
        where.append("($metric_name IS NULL OR node.metric_name = $metric_name)")
        where.append("($passed IS NULL OR node.passed = $passed)")

    # ✅ FETCHING RICH METADATA
    cypher = f"""
    CALL db.index.vector.queryNodes($index, $k, $vector) YIELD node, score
    WHERE {" AND ".join(where)}
    RETURN
        labels(node) AS labels,
        score AS score,
        node.trace_id AS trace_id,
        node.event_key AS event_key,
        node.seq AS seq,
        node.eval_id AS eval_id,
        node.metric_name AS metric_name,
        node.status AS status,
        node.provider AS provider,
        node.model AS model,
        node.session_id AS session_id,
        node.case_id AS case_id,
        node.inputs_json AS inputs_json,
        node.final_output AS final_output,
        node.reasoning AS reasoning
    ORDER BY score DESC
    """

    rows = await run_in_threadpool(_rows, cypher, params)

    out = []
    for r in rows:
        node = r
        inputs = _json_load_maybe(node.get("inputs_json"))
        question = None
        if isinstance(inputs, dict):
            question = inputs.get("question") or inputs.get("input") or inputs.get("query")

        out.append(
            {
                "labels": r.get("labels"),
                "score": r.get("score"),
                "trace_id": node.get("trace_id"),
                "event_key": node.get("event_key"),
                "seq": node.get("seq"),
                "eval_id": node.get("eval_id"),
                "metric_name": node.get("metric_name"),
                "status": node.get("status"),
                "provider": node.get("provider"),
                "model": node.get("model"),
                # ✅ Return all fields
                "session_id": node.get("session_id"),
                "app_id": node.get("case_id"),
                "question": question,
                "final_output": node.get("final_output"),
                "reasoning": node.get("reasoning"),
            }
        )

    return {"index": index, "k": req.k, "min_score": req.min_score, "items": out}


# -----------------------------
# GET /eval/metrics/summary
# -----------------------------
@router.get("/metrics/summary")
async def eval_metrics_summary(
    metric_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    status: Optional[str] = None,
):
    # 1. Fetch grouped items via Cypher
    q = """
    MATCH (r:EvalResult)
    WHERE r.metric_name IS NOT NULL
      AND ($metric_name IS NULL OR r.metric_name = $metric_name)
    OPTIONAL MATCH (t:EvalTrace {trace_id: r.trace_id})
    WHERE ($provider IS NULL OR t.provider = $provider)
      AND ($model IS NULL OR t.model = $model)
      AND ($status IS NULL OR t.status = $status)
    WITH r.metric_name AS metric_name,
         count(r) AS count,
         avg(coalesce(r.score, 0.0)) AS avg_score,
         sum(CASE WHEN r.passed = true THEN 1 ELSE 0 END) AS pass_count
    RETURN metric_name, count, pass_count,
           (CASE WHEN count = 0 THEN 0.0 ELSE (toFloat(pass_count) / toFloat(count)) END) AS pass_rate,
           avg_score
    ORDER BY metric_name ASC
    """

    rows = await run_in_threadpool(
        _rows,
        q,
        {"metric_name": metric_name, "provider": provider, "model": model, "status": status},
    )

    # 2. Calculate totals in Python
    total_evals = sum(int(r.get("count", 0)) for r in rows)
    total_passes = sum(int(r.get("pass_count", 0)) for r in rows)

    # Avoid division by zero
    overall_rate = (total_passes / total_evals) if total_evals > 0 else 0.0

    # 3. Return the calculated field alongside items
    return {
        "items": rows,
        "total_metrics": len(rows),
        "total_evals": total_evals,
        "overall_pass_rate": overall_rate,
    }


# -----------------------------
# GET /eval/metrics/failures
# -----------------------------
@router.get("/metrics/failures")
async def eval_metrics_failures(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    metric_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    status: Optional[str] = None,
):
    if metric_name is not None:
        metric_name = metric_name.strip() or None

    trace_filters = (provider is not None) or (model is not None) or (status is not None)
    metric_filter = metric_name is not None

    if trace_filters:
        q = (
            """
        MATCH (t:EvalTrace)
        WHERE ($provider IS NULL OR t.provider = $provider)
          AND ($model IS NULL OR t.model = $model)
          AND ($status IS NULL OR t.status = $status)

        MATCH (t)-[:HAS_EVAL]->(r:EvalResult)
        WHERE r.passed = false
          AND r.updated_at IS NOT NULL
        """
            + (" AND r.metric_name = $metric_name" if metric_filter else "")
            + """
        WITH r, t
        ORDER BY r.updated_at DESC
        SKIP $offset LIMIT $limit

        RETURN
          r.eval_id AS eval_id,
          r.trace_id AS trace_id,
          r.metric_name AS metric_name,
          r.score AS score,
          r.passed AS passed,
          r.evaluator_id AS evaluator_id,
          r.reasoning AS reasoning,
          toString(r.updated_at) AS updated_at,

          t.status AS trace_status,
          t.provider AS provider,
          t.model AS model,
          t.endpoint AS endpoint,
          t.session_id AS session_id,
          t.case_id AS case_id,
          t.started_at AS started_at
        """
        )
    else:
        # ✅ FIX: Escaped curly braces {{trace_id: ...}} or switched to string concatenation
        # Since we are using an f-string for the metric_filter logic, we must double braces.
        q = f"""
        MATCH (r:EvalResult)
        WHERE r.passed = false
          AND r.updated_at IS NOT NULL
          {' AND r.metric_name = $metric_name' if metric_filter else ''}
        WITH r
        ORDER BY r.updated_at DESC
        SKIP $offset LIMIT $limit

        OPTIONAL MATCH (t:EvalTrace {{trace_id: r.trace_id}})

        RETURN
          r.eval_id AS eval_id,
          r.trace_id AS trace_id,
          r.metric_name AS metric_name,
          r.score AS score,
          r.passed AS passed,
          r.evaluator_id AS evaluator_id,
          r.reasoning AS reasoning,
          toString(r.updated_at) AS updated_at,

          t.status AS trace_status,
          t.provider AS provider,
          t.model AS model,
          t.endpoint AS endpoint,
          t.session_id AS session_id,
          t.case_id AS case_id,
          t.started_at AS started_at
        """

    rows = await run_in_threadpool(
        _rows,
        q,
        {
            "limit": limit,
            "offset": offset,
            "metric_name": metric_name,
            "provider": provider,
            "model": model,
            "status": status,
        },
    )

    return {"limit": limit, "offset": offset, "items": rows}


@router.get("/question-types")
async def question_types(limit: int = 200):
    rows = Neo4jManager.execute_read(
        """
        MATCH (t:EvalTrace)
        WHERE t.started_at IS NOT NULL
        WITH t ORDER BY t.started_at DESC LIMIT $limit
        RETURN coalesce(t.router_reason, "Unknown") as reason, count(*) as n
        ORDER BY n DESC
        """,
        {"limit": limit},
    )
    total = sum(int(r["n"]) for r in rows) or 1
    items = [
        {"reason": r["reason"], "count": int(r["n"]), "pct": float(r["n"]) / total} for r in rows
    ]
    return {"limit": limit, "total": total, "items": items}
