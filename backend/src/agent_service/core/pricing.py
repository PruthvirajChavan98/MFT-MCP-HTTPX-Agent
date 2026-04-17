from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from src.agent_service.llm.catalog import model_service

log = logging.getLogger("cost_tracker")


async def calculate_run_cost_detailed(
    model_id: str, usage: Mapping[str, int | None], provider: str
) -> tuple[float, dict[str, Any]]:
    """Calculate detailed cost breakdown with per-category pricing.

    Groq and Nvidia are FREE in BYOK mode. OpenRouter has per-model pricing.

    Billing semantics (fixed 2026-04-13 — previously had two double-count bugs):

    - Cached prompt tokens (``cache_read_input_tokens`` / ``cached_tokens``) are a
      SUBSET of ``prompt_tokens``. Vendor APIs report them as the portion of the
      prompt served from cache. The correct bill is:
      ``(prompt - cached) * full_rate + cached * half_rate``. The prior code
      was ``prompt * full_rate + cached * half_rate``, charging cached tokens at
      1.5x instead of 0.5x — a ~3x over-charge on the cached portion.

    - Reasoning tokens (``reasoning_tokens`` for o1/o3/gpt-oss reasoning models)
      are a SUBSET of ``completion_tokens`` per the OpenAI usage spec
      (``completion_tokens_details.reasoning_tokens``). None of the providers
      we support bill reasoning tokens separately. The prior code added
      ``reasoning_tokens * c_rate`` on top of ``completion_tokens * c_rate``,
      doubling the bill on reasoning runs. Fix: no separate reasoning cost.
      Reasoning-token counts stay in the ``usage`` breakdown for observability.

    Returns:
        ``(total_cost, breakdown_dict)``. Total is USD; breakdown contains
        per-category costs rounded to 8 decimal places plus raw token counts.
    """
    if not usage or not model_id:
        return 0.0, {}

    try:
        target = model_id.strip()

        prompt_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        completion_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
        total_tokens = usage.get("total_tokens") or (prompt_tokens + completion_tokens)

        # Reasoning tokens (o1/o3/gpt-oss reasoning models) — subset of completion_tokens
        reasoning_tokens = usage.get("reasoning_tokens") or 0

        # Cached prompt tokens — subset of prompt_tokens
        cached_tokens = usage.get("cache_read_input_tokens") or usage.get("cached_tokens") or 0

        # FREE TIER: Groq and Nvidia
        if provider in ("groq", "nvidia"):
            breakdown = {
                "prompt_cost": 0.0,
                "completion_cost": 0.0,
                "reasoning_cost": None,  # billed as part of completion
                "cached_cost": None,
                "total_cost": 0.0,
                "model": model_id,
                "provider": provider,
                "currency": "USD",
                "free_tier": True,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "reasoning_tokens": reasoning_tokens if reasoning_tokens > 0 else None,
                    "cached_tokens": cached_tokens if cached_tokens > 0 else None,
                },
                "pricing_rates": {
                    "prompt_per_token": 0.0,
                    "completion_per_token": 0.0,
                    "prompt_per_1m": 0.0,
                    "completion_per_1m": 0.0,
                },
            }
            return 0.0, breakdown

        # PAID TIER: OpenRouter
        pricing = await model_service.get_price(target)

        if not pricing:
            log.warning("No pricing found for %s, assuming free", target)
            return 0.0, {
                "prompt_cost": 0.0,
                "completion_cost": 0.0,
                "total_cost": 0.0,
                "model": model_id,
                "provider": provider,
                "currency": "USD",
                "free_tier": False,
                "pricing_unavailable": True,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "reasoning_tokens": reasoning_tokens if reasoning_tokens > 0 else None,
                    "cached_tokens": cached_tokens if cached_tokens > 0 else None,
                },
            }

        # Pricing rates (per token)
        p_rate = float(pricing.get("prompt", 0))
        c_rate = float(pricing.get("completion", 0))

        # Calculate costs — cached tokens are subtracted from billable prompt before
        # applying full rate, then added back at half rate.
        billable_prompt_tokens = max(0, prompt_tokens - cached_tokens)
        prompt_cost = billable_prompt_tokens * p_rate
        completion_cost = completion_tokens * c_rate
        cached_cost = cached_tokens * (p_rate * 0.5) if cached_tokens > 0 else None

        # reasoning_tokens are ALREADY in completion_tokens; no separate line item.
        reasoning_cost = None

        total_cost = prompt_cost + completion_cost
        if cached_cost is not None:
            total_cost += cached_cost

        breakdown = {
            "prompt_cost": round(prompt_cost, 8),
            "completion_cost": round(completion_cost, 8),
            "reasoning_cost": reasoning_cost,
            "cached_cost": round(cached_cost, 8) if cached_cost is not None else None,
            "total_cost": round(total_cost, 8),
            "model": model_id,
            "provider": provider,
            "currency": "USD",
            "free_tier": False,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "reasoning_tokens": reasoning_tokens if reasoning_tokens > 0 else None,
                "cached_tokens": cached_tokens if cached_tokens > 0 else None,
            },
            "pricing_rates": {
                "prompt_per_token": p_rate,
                "completion_per_token": c_rate,
                "prompt_per_1m": round(p_rate * 1_000_000, 4),
                "completion_per_1m": round(c_rate * 1_000_000, 4),
            },
        }

        return total_cost, breakdown

    except Exception:
        log.error("Failed to calculate detailed cost for %s", model_id, exc_info=True)
        return 0.0, {}
