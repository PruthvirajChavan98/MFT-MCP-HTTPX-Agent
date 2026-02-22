from __future__ import annotations

import pytest

from src.agent_service.security import inline_guard


@pytest.mark.asyncio
async def test_evaluate_prompt_safety_returns_true_when_both_checks_pass(monkeypatch):
    monkeypatch.setattr(inline_guard, "INLINE_GUARD_ENABLED", True)
    monkeypatch.setattr(inline_guard, "_vector_rail_check", lambda prompt: _async_bool(True))
    monkeypatch.setattr(
        inline_guard, "_openrouter_prompt_guard_check", lambda prompt: _async_bool(True)
    )

    assert await inline_guard.evaluate_prompt_safety("normal customer query") is True


@pytest.mark.asyncio
async def test_evaluate_prompt_safety_fails_closed_on_check_exception(monkeypatch):
    monkeypatch.setattr(inline_guard, "INLINE_GUARD_ENABLED", True)

    async def _raise_error(prompt: str) -> bool:
        raise RuntimeError("network failure")

    monkeypatch.setattr(inline_guard, "_vector_rail_check", _raise_error)
    monkeypatch.setattr(
        inline_guard, "_openrouter_prompt_guard_check", lambda prompt: _async_bool(True)
    )

    assert await inline_guard.evaluate_prompt_safety("suspicious prompt") is False


async def _async_bool(value: bool) -> bool:
    return value
