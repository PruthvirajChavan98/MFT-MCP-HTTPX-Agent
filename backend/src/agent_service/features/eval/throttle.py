"""Sampling and per-process throttle for shadow evaluation."""

from __future__ import annotations

import asyncio
import os
import random
import time

# ---------------------------------------------------------------------------
# Config (env)
# ---------------------------------------------------------------------------
SHADOW_EVAL_ENABLED = (os.getenv("SHADOW_EVAL_ENABLED") or "0").strip() == "1"
SHADOW_EVAL_SAMPLE_RATE = float((os.getenv("SHADOW_EVAL_SAMPLE_RATE") or "0.05").strip())
SHADOW_EVAL_MAX_PER_MIN = int((os.getenv("SHADOW_EVAL_MAX_PER_MIN") or "20").strip())

# ---------------------------------------------------------------------------
# Per-process throttle state
# ---------------------------------------------------------------------------
_window_minute: int = 0
_window_count: int = 0
_throttle_lock = asyncio.Lock()


async def _throttle_ok() -> bool:
    global _window_minute, _window_count
    now_min = int(time.time() // 60)
    async with _throttle_lock:
        if now_min != _window_minute:
            _window_minute = now_min
            _window_count = 0
        if _window_count >= SHADOW_EVAL_MAX_PER_MIN:
            return False
        _window_count += 1
        return True


async def _shadow_eval_decision() -> tuple[bool, str]:
    if not SHADOW_EVAL_ENABLED:
        return False, "disabled"
    if SHADOW_EVAL_SAMPLE_RATE <= 0:
        return False, "disabled"
    if random.random() > SHADOW_EVAL_SAMPLE_RATE:
        return False, "sampled_out"
    if not await _throttle_ok():
        return False, "sampled_out"
    return True, "eligible"


async def should_shadow_eval() -> bool:
    should_run, _ = await _shadow_eval_decision()
    return should_run
