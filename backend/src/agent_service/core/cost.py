import logging
from typing import Any, Dict, Tuple

from src.agent_service.llm.catalog import model_service

log = logging.getLogger("cost_tracker")


async def calculate_run_cost_detailed(
    model_id: str, usage: Dict[str, int], provider: str
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculates detailed cost breakdown with per-category pricing.

    Groq and Nvidia are FREE in BYOK mode.
    OpenRouter has per-model pricing.

    Returns:
        (total_cost, breakdown_dict)
    """
    if not usage or not model_id:
        return 0.0, {}

    try:
        target = model_id.strip()

        # Extract token counts (support multiple formats)
        prompt_tokens = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0) or (prompt_tokens + completion_tokens)

        # ✅ Reasoning tokens (o1/o3/gpt-oss models)
        reasoning_tokens = usage.get("reasoning_tokens", 0)

        # FREE TIER: Groq and Nvidia
        if provider in ("groq", "nvidia"):
            breakdown = {
                "prompt_cost": 0.0,
                "completion_cost": 0.0,
                "reasoning_cost": 0.0 if reasoning_tokens > 0 else None,
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
                    "reasoning_tokens": (
                        reasoning_tokens if reasoning_tokens > 0 else None
                    ),  # ✅ Include
                    "cached_tokens": None,
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
            log.warning(f"No pricing found for {target}, assuming free")
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
                    "reasoning_tokens": (
                        reasoning_tokens if reasoning_tokens > 0 else None
                    ),  # ✅ Include
                },
            }

        # Pricing rates (per token)
        p_rate = float(pricing.get("prompt", 0))
        c_rate = float(pricing.get("completion", 0))

        # Calculate costs
        prompt_cost = prompt_tokens * p_rate
        completion_cost = completion_tokens * c_rate

        # Reasoning cost (same as completion for most models)
        reasoning_cost = reasoning_tokens * c_rate if reasoning_tokens > 0 else None

        # Cached tokens
        cached_tokens = usage.get("cache_read_input_tokens", 0) or usage.get("cached_tokens", 0)
        cached_cost = cached_tokens * (p_rate * 0.5) if cached_tokens > 0 else None

        total_cost = prompt_cost + completion_cost
        if reasoning_cost:
            total_cost += reasoning_cost
        if cached_cost:
            total_cost += cached_cost

        breakdown = {
            "prompt_cost": round(prompt_cost, 8),
            "completion_cost": round(completion_cost, 8),
            "reasoning_cost": round(reasoning_cost, 8) if reasoning_cost else None,
            "cached_cost": round(cached_cost, 8) if cached_cost else None,
            "total_cost": round(total_cost, 8),
            "model": model_id,
            "provider": provider,
            "currency": "USD",
            "free_tier": False,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "reasoning_tokens": (
                    reasoning_tokens if reasoning_tokens > 0 else None
                ),  # ✅ Include
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

    except Exception as e:
        log.error(f"Failed to calculate detailed cost for {model_id}: {e}")
        return 0.0, {}


async def calculate_run_cost(model_id: str, usage: Dict[str, int]) -> float:
    """
    Legacy function - returns only total cost.
    Kept for backward compatibility.
    """
    total, _ = await calculate_run_cost_detailed(model_id, usage, provider="unknown")
    return total
