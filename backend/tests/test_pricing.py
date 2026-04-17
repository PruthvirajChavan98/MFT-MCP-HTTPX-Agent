"""Tests for calculate_run_cost_detailed — guards the two regression bugs fixed 2026-04-13.

Both regressions were silent production billing errors that had been running since
2026-04-05:

1. Cached prompt tokens were charged at full rate AND half rate (~3x over-charge
   on the cached portion; ~18% over-charge on a representative cache-heavy call).

2. Reasoning tokens (a subset of completion_tokens per OpenAI usage spec) were
   charged as a separate line item on top of completion_cost, doubling the bill
   on o1/o3/gpt-oss reasoning runs.

These tests pin the correct behavior so future refactors can't re-introduce either
bug without a red test.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.agent_service.core.pricing import calculate_run_cost_detailed

# Representative per-token rates for OpenRouter gpt-4o:
#   $3.00 per 1M prompt tokens  → 3e-6  per token
#   $10.00 per 1M completion    → 1e-5  per token
_P_RATE = 3e-6
_C_RATE = 1e-5
_PRICING_GPT4O: dict[str, Any] = {"prompt": _P_RATE, "completion": _C_RATE}


# ─────────────────────────────────────────────────────────────────────
# REGRESSION #1 — cached-token double-count
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cached_tokens_are_not_double_charged() -> None:
    """1000 prompt tokens, 200 cached. Correct bill:
        billable_prompt = 800 at full rate + 200 at half rate
        = 800 * 3e-6  +  200 * 1.5e-6
        = 2.4e-3      +  3.0e-4
        = 2.7e-3
    The prior bug charged 1000 at full rate PLUS 200 at half rate = 3.3e-3.
    """
    usage = {
        "prompt_tokens": 1000,
        "completion_tokens": 0,
        "cached_tokens": 200,
    }
    with patch(
        "src.agent_service.core.pricing.model_service.get_price",
        new=AsyncMock(return_value=_PRICING_GPT4O),
    ):
        total, breakdown = await calculate_run_cost_detailed("gpt-4o", usage, "openrouter")

    assert total == pytest.approx(2.7e-3, abs=1e-9)
    assert breakdown["prompt_cost"] == pytest.approx(800 * _P_RATE, abs=1e-9)
    assert breakdown["cached_cost"] == pytest.approx(200 * _P_RATE * 0.5, abs=1e-9)
    # Regression guard — the old bug's total was 3.3e-3; make sure we don't land on it.
    assert total != pytest.approx(3.3e-3, abs=1e-9)


@pytest.mark.asyncio
async def test_no_cached_tokens_behaves_as_before() -> None:
    """Regression guard: 1000 prompt, 0 cached → prompt_cost = 1000 * full, cached_cost = None."""
    usage = {"prompt_tokens": 1000, "completion_tokens": 500}
    with patch(
        "src.agent_service.core.pricing.model_service.get_price",
        new=AsyncMock(return_value=_PRICING_GPT4O),
    ):
        total, breakdown = await calculate_run_cost_detailed("gpt-4o", usage, "openrouter")

    assert breakdown["prompt_cost"] == pytest.approx(1000 * _P_RATE, abs=1e-9)
    assert breakdown["completion_cost"] == pytest.approx(500 * _C_RATE, abs=1e-9)
    assert breakdown["cached_cost"] is None
    assert total == pytest.approx(1000 * _P_RATE + 500 * _C_RATE, abs=1e-9)


@pytest.mark.asyncio
async def test_all_prompt_tokens_cached_zero_billable_prompt() -> None:
    """Edge case: every prompt token was served from cache → billable = 0, cached charged at half."""
    usage = {"prompt_tokens": 500, "completion_tokens": 0, "cached_tokens": 500}
    with patch(
        "src.agent_service.core.pricing.model_service.get_price",
        new=AsyncMock(return_value=_PRICING_GPT4O),
    ):
        total, breakdown = await calculate_run_cost_detailed("gpt-4o", usage, "openrouter")

    assert breakdown["prompt_cost"] == pytest.approx(0.0, abs=1e-9)
    assert breakdown["cached_cost"] == pytest.approx(500 * _P_RATE * 0.5, abs=1e-9)
    assert total == pytest.approx(500 * _P_RATE * 0.5, abs=1e-9)


@pytest.mark.asyncio
async def test_cached_tokens_exceed_prompt_tokens_clamps_to_zero() -> None:
    """Defensive: malformed usage where cached > prompt. billable_prompt must not go negative."""
    usage = {"prompt_tokens": 100, "completion_tokens": 0, "cached_tokens": 500}
    with patch(
        "src.agent_service.core.pricing.model_service.get_price",
        new=AsyncMock(return_value=_PRICING_GPT4O),
    ):
        total, breakdown = await calculate_run_cost_detailed("gpt-4o", usage, "openrouter")

    assert breakdown["prompt_cost"] == pytest.approx(0.0, abs=1e-9)
    # cached_cost is still 500 * half_rate — we don't try to reconcile malformed vendor input
    assert breakdown["cached_cost"] == pytest.approx(500 * _P_RATE * 0.5, abs=1e-9)
    assert total >= 0.0


@pytest.mark.asyncio
async def test_cache_read_input_tokens_alias_is_honored() -> None:
    """Anthropic-style key 'cache_read_input_tokens' should be treated as cached_tokens."""
    usage = {
        "prompt_tokens": 1000,
        "completion_tokens": 0,
        "cache_read_input_tokens": 300,
    }
    with patch(
        "src.agent_service.core.pricing.model_service.get_price",
        new=AsyncMock(return_value=_PRICING_GPT4O),
    ):
        total, breakdown = await calculate_run_cost_detailed("claude-3.5", usage, "openrouter")

    expected = 700 * _P_RATE + 300 * _P_RATE * 0.5
    assert total == pytest.approx(expected, abs=1e-9)


# ─────────────────────────────────────────────────────────────────────
# REGRESSION #2 — reasoning-token double-count
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reasoning_tokens_are_not_charged_separately() -> None:
    """1000 completion tokens, 300 reasoning (SUBSET of completion). Correct bill:
        completion_cost = 1000 * c_rate   (reasoning already inside this)
        reasoning_cost  = None
    The prior bug added 300 * c_rate on top → 1300 * c_rate → 30% over-charge.
    """
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 1000,
        "reasoning_tokens": 300,
    }
    with patch(
        "src.agent_service.core.pricing.model_service.get_price",
        new=AsyncMock(return_value=_PRICING_GPT4O),
    ):
        total, breakdown = await calculate_run_cost_detailed("o1-mini", usage, "openrouter")

    assert breakdown["completion_cost"] == pytest.approx(1000 * _C_RATE, abs=1e-9)
    assert breakdown["reasoning_cost"] is None
    assert total == pytest.approx(1000 * _C_RATE, abs=1e-9)
    # Regression guard — old bug landed on 1300 * c_rate.
    assert total != pytest.approx(1300 * _C_RATE, abs=1e-9)
    # Reasoning count preserved for observability
    assert breakdown["usage"]["reasoning_tokens"] == 300


@pytest.mark.asyncio
async def test_reasoning_zero_still_observable_as_none() -> None:
    """When reasoning_tokens == 0, the usage field is None (not 0), matching prior UX."""
    usage = {"prompt_tokens": 100, "completion_tokens": 200, "reasoning_tokens": 0}
    with patch(
        "src.agent_service.core.pricing.model_service.get_price",
        new=AsyncMock(return_value=_PRICING_GPT4O),
    ):
        _, breakdown = await calculate_run_cost_detailed("gpt-4o", usage, "openrouter")

    assert breakdown["usage"]["reasoning_tokens"] is None


# ─────────────────────────────────────────────────────────────────────
# Combined regression + general paths
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cached_and_reasoning_simultaneous_both_correctly_billed() -> None:
    """Worst-case real call: 2000 prompt / 500 cached / 1500 completion / 400 reasoning.
    Correct:
        prompt_cost = 1500 * p_rate
        cached_cost = 500 * p_rate * 0.5
        completion_cost = 1500 * c_rate
        reasoning_cost = None
        total = 1500*p + 250*p + 1500*c = 1750*p + 1500*c
    Prior bug would total: 2000*p + 1800*c + 250*p = 2250*p + 1800*c.
    """
    usage = {
        "prompt_tokens": 2000,
        "completion_tokens": 1500,
        "cached_tokens": 500,
        "reasoning_tokens": 400,
    }
    with patch(
        "src.agent_service.core.pricing.model_service.get_price",
        new=AsyncMock(return_value=_PRICING_GPT4O),
    ):
        total, breakdown = await calculate_run_cost_detailed("o1-mini", usage, "openrouter")

    expected = 1500 * _P_RATE + 500 * _P_RATE * 0.5 + 1500 * _C_RATE
    assert total == pytest.approx(expected, abs=1e-9)
    assert breakdown["reasoning_cost"] is None
    assert breakdown["cached_cost"] == pytest.approx(500 * _P_RATE * 0.5, abs=1e-9)


@pytest.mark.asyncio
async def test_groq_free_tier_zero_cost() -> None:
    usage = {"prompt_tokens": 10_000, "completion_tokens": 5_000, "reasoning_tokens": 1_000}
    total, breakdown = await calculate_run_cost_detailed("llama-3.1-70b", usage, "groq")

    assert total == 0.0
    assert breakdown["free_tier"] is True
    assert breakdown["total_cost"] == 0.0
    assert breakdown["usage"]["reasoning_tokens"] == 1_000


@pytest.mark.asyncio
async def test_nvidia_free_tier_zero_cost() -> None:
    usage = {"prompt_tokens": 500, "completion_tokens": 500}
    total, breakdown = await calculate_run_cost_detailed("nvidia/llama-4", usage, "nvidia")

    assert total == 0.0
    assert breakdown["free_tier"] is True


@pytest.mark.asyncio
async def test_pricing_unavailable_returns_zero_with_flag() -> None:
    """When model_service.get_price returns None, bill 0 and mark pricing_unavailable."""
    usage = {"prompt_tokens": 1000, "completion_tokens": 500}
    with patch(
        "src.agent_service.core.pricing.model_service.get_price",
        new=AsyncMock(return_value=None),
    ):
        total, breakdown = await calculate_run_cost_detailed("unknown-model", usage, "openrouter")

    assert total == 0.0
    assert breakdown["pricing_unavailable"] is True
    assert breakdown["free_tier"] is False


@pytest.mark.asyncio
async def test_empty_usage_returns_zero() -> None:
    total, breakdown = await calculate_run_cost_detailed("gpt-4o", {}, "openrouter")
    assert total == 0.0
    assert breakdown == {}


@pytest.mark.asyncio
async def test_empty_model_id_returns_zero() -> None:
    total, breakdown = await calculate_run_cost_detailed("", {"prompt_tokens": 100}, "openrouter")
    assert total == 0.0
    assert breakdown == {}


@pytest.mark.asyncio
async def test_exception_in_get_price_returns_zero_without_crashing() -> None:
    """Pricing lookup crashes must not crash the streaming path — return 0 cost + empty dict."""
    usage = {"prompt_tokens": 100, "completion_tokens": 100}
    with patch(
        "src.agent_service.core.pricing.model_service.get_price",
        new=AsyncMock(side_effect=RuntimeError("pricing service down")),
    ):
        total, breakdown = await calculate_run_cost_detailed("gpt-4o", usage, "openrouter")

    assert total == 0.0
    assert breakdown == {}


@pytest.mark.asyncio
async def test_input_tokens_alias_honored() -> None:
    """Anthropic key 'input_tokens' should be read when 'prompt_tokens' absent."""
    usage = {"input_tokens": 1000, "output_tokens": 500}
    with patch(
        "src.agent_service.core.pricing.model_service.get_price",
        new=AsyncMock(return_value=_PRICING_GPT4O),
    ):
        total, breakdown = await calculate_run_cost_detailed("claude-3.5", usage, "openrouter")

    expected = 1000 * _P_RATE + 500 * _C_RATE
    assert total == pytest.approx(expected, abs=1e-9)
    assert breakdown["usage"]["prompt_tokens"] == 1000
    assert breakdown["usage"]["completion_tokens"] == 500
