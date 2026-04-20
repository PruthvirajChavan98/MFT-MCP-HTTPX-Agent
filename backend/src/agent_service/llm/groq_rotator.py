"""
Atomic round-robin selection across GROQ_API_KEYS via Redis INCR.

Shared helper — lifted out of `security.inline_guard` (which still delegates
here) so every call-site that hits Groq can distribute load evenly across
the keys configured in `.env`. Without this, all 3 RAGAS metrics (fired
concurrently per evaluated trace) plus the shadow judge worker batch loop
pin to GROQ_API_KEYS[0], saturating one key while the others idle — which
is the observed cause of eval-path 429s and timeouts.

Redis key contract (unchanged from `inline_guard`):
  - `agent:groq_rr_counter`  — monotonically increasing INCR counter.
  - `agent:groq_cooling:{h}` — short-lived TTL key marking a 429'd Groq
    key as "cooling"; `next_groq_key()` skips keys whose hash matches.

Behaviour:
  - 0 keys     → RuntimeError (explicit fail, never silent fallback).
  - 1 key      → fast path, no Redis round trip.
  - N ≥ 2 keys → INCR counter, modulo N, skip cooling keys.
  - N distinct → `next_groq_keys(n)` uses INCRBY to claim consecutive
    counter slots in one round-trip so the returned keys are distinct
    when len(GROQ_API_KEYS) ≥ n.
  - All cooling → return the modulo pick anyway (better to attempt than
    to raise; the caller sees any persistent 429 and can re-cool).
"""

from __future__ import annotations

import hashlib
import logging

from src.agent_service.core import config as _cfg
from src.agent_service.core.config import GROQ_KEY_COOLING_TTL_S
from src.agent_service.core.session_utils import get_redis

log = logging.getLogger(__name__)

_GROQ_RR_COUNTER_KEY = "agent:groq_rr_counter"
_COOLING_KEY_PREFIX = "agent:groq_cooling:"


def _keys() -> list[str]:
    """Read live so test monkeypatches on either this module or core.config apply."""
    module_override = globals().get("GROQ_API_KEYS")
    if module_override is not None:
        return list(module_override)
    return list(_cfg.GROQ_API_KEYS)


# Preserved as a module attribute so existing tests that do
# `monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", [...])` keep working.
GROQ_API_KEYS: list[str] | None = None


def _hash_key(api_key: str) -> str:
    """Short, stable hash of an API key — used only as Redis key material."""
    return hashlib.sha1(api_key.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def _cooling_key(api_key: str) -> str:
    return f"{_COOLING_KEY_PREFIX}{_hash_key(api_key)}"


async def _is_cooling(redis, api_key: str) -> bool:
    return bool(await redis.exists(_cooling_key(api_key)))


async def next_groq_key(*, keys: list[str] | None = None) -> str:
    """Return the next Groq API key in round-robin order.

    Skips cooling keys; if every key is cooling, returns the modulo pick
    (fairness preserved — do not raise on transient total-cooling).

    ``keys`` override is for callers that have their own (test-patchable)
    import of ``GROQ_API_KEYS``; omit to use the module-level config.
    """
    keys = list(keys) if keys is not None else _keys()
    if not keys:
        raise RuntimeError("No GROQ_API_KEYS configured.")
    if len(keys) == 1:
        return keys[0]

    redis = await get_redis()
    counter = await redis.incr(_GROQ_RR_COUNTER_KEY)
    n = len(keys)
    base_idx = (counter - 1) % n

    for offset in range(n):
        idx = (base_idx + offset) % n
        candidate = keys[idx]
        if not await _is_cooling(redis, candidate):
            return candidate

    log.warning(
        "[groq_rotator] All %d Groq keys are cooling; falling through to slot %d",
        n,
        base_idx,
    )
    return keys[base_idx]


async def next_groq_keys(n: int) -> list[str]:
    """Return `n` keys as a single atomic claim.

    Uses `INCRBY n` so the returned slots are consecutive and not
    interleaved by other concurrent callers. When
    `len(GROQ_API_KEYS) >= n` the returned keys are distinct; otherwise
    they cycle (best-effort — caller must tolerate duplicates when
    asking for more keys than exist).

    Cooling keys are NOT skipped here — the RAGAS path using this wants
    3 distinct slots in one RTT, and re-evaluating cooling per slot
    would require N round-trips and lose atomicity. Individual metric
    failures surface as `asyncio.TimeoutError` in the caller and are
    handled there.
    """
    if n <= 0:
        return []
    keys = _keys()
    if not keys:
        raise RuntimeError("No GROQ_API_KEYS configured.")
    total = len(keys)
    if total == 1:
        return [keys[0]] * n

    redis = await get_redis()
    top = await redis.incrby(_GROQ_RR_COUNTER_KEY, n)
    base = top - n  # first slot claimed by this call (0-indexed counter)
    return [keys[(base + i) % total] for i in range(n)]


async def mark_key_cooling(api_key: str, *, ttl_seconds: int | None = None) -> None:
    """Mark an API key as "cooling" so RR skips it for `ttl_seconds`.

    Call after a 429 / rate_limit_exceeded from Groq. TTL defaults to
    `GROQ_KEY_COOLING_TTL_S` (env-tunable).
    """
    if not api_key:
        return
    ttl = ttl_seconds if ttl_seconds is not None else GROQ_KEY_COOLING_TTL_S
    if ttl <= 0:
        return
    redis = await get_redis()
    await redis.set(_cooling_key(api_key), "1", ex=ttl)
    log.info(
        "[groq_rotator] Cooling Groq key %s… for %ds",
        _hash_key(api_key),
        ttl,
    )
