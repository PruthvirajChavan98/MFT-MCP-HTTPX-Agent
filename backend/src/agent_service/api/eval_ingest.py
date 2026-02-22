from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from src.agent_service.core.config import REDIS_URL
from src.agent_service.eval_store.embedder import EvalEmbedder
from src.agent_service.eval_store.neo4j_store import EvalNeo4jStore

log = logging.getLogger("eval_ingest")

router = APIRouter()
STORE = EvalNeo4jStore()
EMBEDDER = EvalEmbedder()

EVAL_INGEST_KEY = (os.getenv("EVAL_INGEST_KEY") or "").strip() or None

# Live feed (Redis Streams)
EVAL_LIVE_STREAM_KEY = (os.getenv("EVAL_LIVE_STREAM_KEY") or "eval:live").strip()
EVAL_LIVE_STREAM_MAXLEN = int(os.getenv("EVAL_LIVE_STREAM_MAXLEN") or "50000")


class IngestBundle(BaseModel):
    trace: Optional[Dict[str, Any]] = None
    events: List[Dict[str, Any]] = Field(default_factory=list)
    evals: List[Dict[str, Any]] = Field(default_factory=list)


def _auth_or_401(x_key: Optional[str]) -> None:
    if not EVAL_INGEST_KEY:
        return
    if not x_key or x_key.strip() != EVAL_INGEST_KEY:
        raise HTTPException(status_code=401, detail="Invalid ingest key")


def _schedule(coro):
    try:
        asyncio.create_task(coro)
    except RuntimeError:
        # No running loop (should not happen under uvicorn),
        # but we also don't want ingest to fail.
        pass


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    try:
        return json.dumps(v, ensure_ascii=False)
    except Exception:
        return str(v)


async def _publish_live(summary: Dict[str, Any]) -> None:
    """
        Push a small “new trace ingested” event to Redis Streams for live dashboards.


    async def _publish_router_job(trace_id: str, text: str) -> None:
        \"\"\"Push a router classification job for router_worker (async).\"\"\"
        try:
            if not trace_id or not text:
                return
            r = Redis.from_url(REDIS_URL, decode_responses=True)

            # XADD appends to stream; approximate trimming keeps memory bounded.
            await r.xadd(
                ROUTER_JOBS_STREAM_KEY,
                {"trace_id": str(trace_id), "text": str(text)},
                maxlen=ROUTER_JOBS_STREAM_MAXLEN,
                approximate=True,
            )
            await r.close()
        except Exception as e:
            log.warning("[eval_ingest] router job publish failed: %s", e)

        Redis Streams: XADD appends, XREAD BLOCK tail-follows.
        XREAD docs: use '$' only for first call; resume from last ID to avoid gaps. :contentReference[oaicite:2]{index=2}
    """
    try:
        r = Redis.from_url(REDIS_URL, decode_responses=True)

        # Stream fields must be simple scalars; keep it tiny.
        fields = {k: _safe_str(v) for k, v in (summary or {}).items()}

        # approximate trimming keeps memory bounded
        await r.xadd(
            EVAL_LIVE_STREAM_KEY,
            fields,  # type: ignore
            maxlen=EVAL_LIVE_STREAM_MAXLEN,
            approximate=True,
        )
        await r.close()
    except Exception as e:
        log.warning("[eval_ingest] live publish failed: %s", e)


@router.post("/ingest")
async def ingest(
    bundle: IngestBundle,
    background_tasks: BackgroundTasks,
    x_eval_ingest_key: Optional[str] = Header(None, alias="X-Eval-Ingest-Key"),
):
    _auth_or_401(x_eval_ingest_key)

    trace_id: Optional[str] = None
    if bundle.trace:
        trace_id = str(bundle.trace.get("trace_id") or "").strip() or None
        if not trace_id:
            raise HTTPException(status_code=400, detail="trace.trace_id missing")
        await STORE.upsert_trace(bundle.trace)

    if not trace_id and bundle.events:
        trace_id = str(bundle.events[0].get("trace_id") or "").strip() or None
    if not trace_id and bundle.evals:
        trace_id = str(bundle.evals[0].get("trace_id") or "").strip() or None
    if not trace_id:
        raise HTTPException(status_code=400, detail="trace_id missing")

    # Normalize events (keep payload/meta as dict in-memory; store converts to JSON strings)
    norm_events: List[Dict[str, Any]] = []
    for e in bundle.events:
        try:
            seq = int(e.get("seq") or 0)
            norm_events.append(
                {
                    "trace_id": trace_id,
                    "seq": seq,
                    "event_key": f"{trace_id}:{seq}",
                    "ts": e.get("ts"),
                    "event_type": e.get("event_type"),
                    "name": e.get("name"),
                    "text": e.get("text"),
                    "payload": (
                        e.get("payload")
                        if isinstance(e.get("payload"), dict)
                        else {"value": e.get("payload")}
                    ),
                    "meta": e.get("meta") if isinstance(e.get("meta"), dict) else {},
                }
            )
        except Exception:
            continue

    if norm_events:
        await STORE.upsert_events(trace_id, norm_events)

    # Normalize evals; compute evidence_event_keys for graph links
    norm_evals: List[Dict[str, Any]] = []
    for r in bundle.evals:
        try:
            evidence = r.get("evidence") if isinstance(r.get("evidence"), list) else []
            ev_keys: List[str] = []
            for item in evidence:  # type: ignore
                if isinstance(item, dict) and item.get("seq") is not None:
                    ev_keys.append(f"{trace_id}:{int(item.get('seq'))}")  # type: ignore

            norm_evals.append(
                {
                    "eval_id": str(r.get("eval_id") or "").strip(),
                    "trace_id": trace_id,
                    "metric_name": r.get("metric_name"),
                    "score": float(r.get("score") or 0.0),
                    "passed": bool(r.get("passed")),
                    "reasoning": r.get("reasoning") or "",
                    "evaluator_id": r.get("evaluator_id") or "system",
                    "evidence": evidence,
                    "evidence_event_keys": ev_keys,
                    "meta": r.get("meta") if isinstance(r.get("meta"), dict) else {},
                }
            )
        except Exception:
            continue

    if norm_evals:
        await STORE.upsert_evals(trace_id, norm_evals)

    # Background embeddings (optional; won’t block ingest)
    if bundle.trace:
        _schedule(EMBEDDER.embed_trace_if_needed(bundle.trace, norm_events))
    for ev in norm_evals:
        _schedule(EMBEDDER.embed_eval_if_needed(trace_id, ev))

    # LIVE publish (fire-and-forget; don’t fail ingest if Redis is down)
    passed_count = sum(1 for r in norm_evals if r.get("passed") is True)
    eval_count = len(norm_evals)
    pass_rate = (passed_count / eval_count) if eval_count > 0 else None

    trace_status = None
    started_at = None
    provider = None
    model = None
    endpoint = None
    session_id = None
    case_id = None

    if bundle.trace:
        trace_status = bundle.trace.get("status")
        started_at = bundle.trace.get("started_at")
        provider = bundle.trace.get("provider")
        model = bundle.trace.get("model")
        endpoint = bundle.trace.get("endpoint")
        session_id = bundle.trace.get("session_id")
        case_id = bundle.trace.get("case_id")

    _schedule(
        _publish_live(
            {
                "trace_id": trace_id,
                "status": trace_status or "",
                "started_at": started_at or "",
                "provider": provider or "",
                "model": model or "",
                "endpoint": endpoint or "",
                "session_id": session_id or "",
                "case_id": case_id or "",
                "event_count": len(norm_events),
                "eval_count": eval_count,
                "pass_count": passed_count,
                "pass_rate": pass_rate if pass_rate is not None else "",
            }
        )
    )

    return {
        "status": "ok",
        "trace_id": trace_id,
        "events": len(norm_events),
        "evals": len(norm_evals),
    }
