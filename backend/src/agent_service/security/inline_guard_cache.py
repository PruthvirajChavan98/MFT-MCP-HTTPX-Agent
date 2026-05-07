"""Vector-similarity cache for inline-guard decisions (Layer 2.5).

Sits between the regex pre-filter (Layer 1) and the Groq Safeguard 120B
classifier (Layer 2) inside ``evaluate_prompt_safety_decision``.

* **Lookup** — embed prompt with the local CPU embedder (~10 ms), top-1
  cosine search against ``inline_guard_cache`` (~5 ms). On a sufficiently
  similar hit with matching model/embedder versions and a fresh TTL, return
  the cached decision and skip the classifier.
* **Write-back** — on cache miss, after the classifier returns a verdict,
  schedule a fire-and-forget write-back through ``eval_store/_bg.schedule()``
  so the response path is not blocked.
* **Reshadow** — a small fraction of cache hits also call the classifier and
  compare; mismatches log a warning and drop the entry. Catches drift and
  cache poisoning.
* **Fail-open** — any cache failure (Milvus down, embedder OOM) returns
  ``None`` from lookup so the caller falls through to the classifier; the
  cache is a perf accelerator, not a correctness gate.
"""

from __future__ import annotations

import hashlib
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Optional

from langchain_core.documents import Document
from prometheus_client import Counter, Histogram

from src.agent_service.core.config import (
    INLINE_GUARD_CACHE_ENABLED,
    INLINE_GUARD_CACHE_RESHADOW_RATE,
    INLINE_GUARD_CACHE_SIM_THRESHOLD,
    INLINE_GUARD_CACHE_TTL_SECONDS,
    INLINE_GUARD_GROQ_MODEL,
    LOCAL_EMBEDDER_VERSION,
)
from src.agent_service.eval_store._bg import schedule

log = logging.getLogger(__name__)

INLINE_GUARD_CACHE_TOTAL = Counter(
    "agent_inline_guard_cache_total",
    "Inline-guard vector-cache outcomes per request.",
    ["outcome"],  # hit | miss | disabled | error
)

INLINE_GUARD_CACHE_LOOKUP_SECONDS = Histogram(
    "agent_inline_guard_cache_lookup_seconds",
    "Inline-guard vector-cache lookup latency (embed + Milvus search).",
)

INLINE_GUARD_CACHE_WRITEBACK_SECONDS = Histogram(
    "agent_inline_guard_cache_writeback_seconds",
    "Inline-guard vector-cache write-back latency.",
)


@dataclass(slots=True, frozen=True)
class CacheLookup:
    """A successful cache hit with the metadata needed by the caller."""

    decision: str
    reason_code: str
    risk_score: float
    score: float  # cosine similarity in [0, 1]
    model_version: str
    embedder_version: str


def _normalise_prompt(prompt: str) -> str:
    """Cheap deterministic normalisation for the content_hash."""
    return " ".join(prompt.lower().split())


def _content_hash(prompt: str) -> str:
    return hashlib.sha256(_normalise_prompt(prompt).encode("utf-8")).hexdigest()[:32]


def _is_fresh(ts: int) -> bool:
    return (time.time() - ts) <= INLINE_GUARD_CACHE_TTL_SECONDS


def _get_store() -> Any | None:
    """Lazy accessor for the Milvus guard-cache store. Imported here so the
    cache module is testable without spinning up the manager singleton."""
    try:
        from src.common.milvus_mgr import milvus_mgr

        return milvus_mgr.guard_cache
    except Exception:  # noqa: BLE001
        return None


async def lookup(prompt: str) -> Optional[CacheLookup]:
    """Top-1 vector lookup keyed by the prompt; returns ``None`` on:
    - cache disabled
    - cache miss
    - similarity below threshold
    - stale model_version / embedder_version
    - expired TTL
    - any infra error (fail-open)
    """
    if not INLINE_GUARD_CACHE_ENABLED:
        INLINE_GUARD_CACHE_TOTAL.labels(outcome="disabled").inc()
        return None

    store = _get_store()
    if store is None:
        INLINE_GUARD_CACHE_TOTAL.labels(outcome="error").inc()
        log.debug("[guard_cache] store unavailable — fail-open to classifier")
        return None

    try:
        with INLINE_GUARD_CACHE_LOOKUP_SECONDS.time():
            hits = await store.asimilarity_search_with_score(prompt, k=1)
    except Exception:  # noqa: BLE001
        INLINE_GUARD_CACHE_TOTAL.labels(outcome="error").inc()
        log.exception("[guard_cache] lookup failed — fail-open to classifier")
        return None

    if not hits:
        INLINE_GUARD_CACHE_TOTAL.labels(outcome="miss").inc()
        return None

    doc, score = hits[0]
    # langchain-milvus returns a *distance* in [0, 2] for COSINE — convert to
    # a similarity score in [0, 1] where 1.0 is identical.
    similarity = max(0.0, 1.0 - (float(score) / 2.0))
    if similarity < INLINE_GUARD_CACHE_SIM_THRESHOLD:
        INLINE_GUARD_CACHE_TOTAL.labels(outcome="miss").inc()
        return None

    meta = doc.metadata or {}
    model_version = str(meta.get("model_version") or "")
    embedder_version = str(meta.get("embedder_version") or "")
    decision = str(meta.get("decision") or "")
    reason_code = str(meta.get("reason_code") or "")
    risk_score_raw = meta.get("risk_score")
    ts_raw = meta.get("ts")

    if (
        not decision
        or model_version != INLINE_GUARD_GROQ_MODEL
        or embedder_version != LOCAL_EMBEDDER_VERSION
        or not isinstance(ts_raw, (int, float))
        or not _is_fresh(int(ts_raw))
    ):
        INLINE_GUARD_CACHE_TOTAL.labels(outcome="miss").inc()
        return None

    INLINE_GUARD_CACHE_TOTAL.labels(outcome="hit").inc()
    return CacheLookup(
        decision=decision,
        reason_code=reason_code,
        risk_score=float(risk_score_raw) if isinstance(risk_score_raw, (int, float)) else 0.0,
        score=similarity,
        model_version=model_version,
        embedder_version=embedder_version,
    )


async def writeback(prompt: str, decision: str, reason_code: str, risk_score: float) -> None:
    """Persist a fresh classifier decision into the cache. Idempotent on
    content_hash (we delete any stale entry for the same hash first)."""
    if not INLINE_GUARD_CACHE_ENABLED:
        return

    store = _get_store()
    if store is None:
        return

    try:
        with INLINE_GUARD_CACHE_WRITEBACK_SECONDS.time():
            content_hash = _content_hash(prompt)
            doc = Document(
                page_content=prompt[:1000],
                metadata={
                    "decision": decision,
                    "reason_code": reason_code,
                    "risk_score": float(risk_score),
                    "model_version": INLINE_GUARD_GROQ_MODEL,
                    "embedder_version": LOCAL_EMBEDDER_VERSION,
                    "content_hash": content_hash,
                    "ts": int(time.time()),
                },
            )
            await store.aadd_documents([doc])
    except Exception:  # noqa: BLE001
        log.exception(
            "[guard_cache] writeback failed for prompt content_hash=%s — request not affected",
            _content_hash(prompt),
        )


def schedule_writeback(prompt: str, decision: str, reason_code: str, risk_score: float) -> None:
    """Fire-and-forget version of writeback — the response path never awaits."""
    if not INLINE_GUARD_CACHE_ENABLED:
        return
    schedule(writeback(prompt, decision, reason_code, risk_score))


def should_reshadow() -> bool:
    """Returns True for ~RESHADOW_RATE of cache hits — caller should also
    invoke the classifier and compare to the cached decision."""
    if INLINE_GUARD_CACHE_RESHADOW_RATE <= 0:
        return False
    return random.random() < INLINE_GUARD_CACHE_RESHADOW_RATE
