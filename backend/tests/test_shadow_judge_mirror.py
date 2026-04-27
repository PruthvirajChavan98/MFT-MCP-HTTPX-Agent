"""Lock that shadow-judge persistence mirrors 3 rows into ``eval_results``.

The trace-detail Evaluation panel reads ``eval_results``. The shadow-judge
worker writes its primary row to ``shadow_judge_evals`` (different table).
After this refactor the worker also projects 3 sibling rows into
``eval_results`` with deterministic eval_ids so the panel surfaces those
LLM-graded dimensions alongside RAGAS metrics.

Mirror writes are idempotent (UPSERT on deterministic eval_id) and must
not fail the worker batch if they error — those guarantees are exercised
here.
"""

from __future__ import annotations

import pytest

from src.agent_service.worker.shadow_judge_worker import ShadowJudgeWorker


class _RecordingPool:
    """Minimal asyncpg.Pool stand-in that records every executemany call."""

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.calls: list[tuple[str, list[tuple]]] = []
        self._fail_on = fail_on

    async def executemany(self, sql: str, params: list[tuple]) -> None:
        if self._fail_on and self._fail_on in sql:
            raise RuntimeError("simulated DB write failure")
        self.calls.append((sql, list(params)))


def _row(trace_id: str, *, helpfulness=0.9, faithfulness=0.85, policy=1.0) -> dict:
    return {
        "eval_id": f"eval-{trace_id}",
        "trace_id": trace_id,
        "session_id": "sess-1",
        "model": "gpt-oss-120b",
        "helpfulness": helpfulness,
        "faithfulness": faithfulness,
        "policy_adherence": policy,
        "summary": "ok",
        "evaluated_at": "2026-04-27T00:00:00Z",
    }


@pytest.mark.asyncio
async def test_persist_writes_three_mirror_rows_per_input() -> None:
    pool = _RecordingPool()
    worker = ShadowJudgeWorker()
    worker._pool = pool  # type: ignore[assignment]

    rows = [_row("trace-A"), _row("trace-B")]
    await worker._persist_rows(rows)

    # Two SQL statements run: shadow_judge_evals INSERT, then eval_results INSERT.
    assert len(pool.calls) == 2
    primary_sql, primary_params = pool.calls[0]
    mirror_sql, mirror_params = pool.calls[1]

    assert "shadow_judge_evals" in primary_sql
    assert "eval_results" in mirror_sql

    # 2 rows in -> 6 mirror rows out (3 metrics × 2 traces)
    assert len(mirror_params) == 6


@pytest.mark.asyncio
async def test_mirror_uses_deterministic_eval_ids_for_idempotency() -> None:
    pool = _RecordingPool()
    worker = ShadowJudgeWorker()
    worker._pool = pool  # type: ignore[assignment]

    await worker._persist_rows([_row("trace-X")])
    _, mirror_params = pool.calls[1]

    eval_ids = sorted(p[0] for p in mirror_params)
    assert eval_ids == [
        "shadow:trace-X:faithfulness",
        "shadow:trace-X:helpfulness",
        "shadow:trace-X:policy_adherence",
    ]
    # Re-run to confirm same IDs (true idempotency comes from ON CONFLICT in SQL).
    pool2 = _RecordingPool()
    worker._pool = pool2  # type: ignore[assignment]
    await worker._persist_rows([_row("trace-X")])
    eval_ids_round2 = sorted(p[0] for p in pool2.calls[1][1])
    assert eval_ids_round2 == eval_ids


@pytest.mark.asyncio
async def test_mirror_metric_names_and_threshold_are_correct() -> None:
    pool = _RecordingPool()
    worker = ShadowJudgeWorker()
    worker._pool = pool  # type: ignore[assignment]

    await worker._persist_rows([_row("trace-T", helpfulness=0.95, faithfulness=0.5, policy=0.7)])
    _, mirror_params = pool.calls[1]

    by_metric = {p[2]: p for p in mirror_params}  # column 2 = metric_name
    # Expected metric names + the >=0.7 pass threshold semantics
    assert by_metric["Helpfulness"][3] == 0.95
    assert by_metric["Helpfulness"][4] is True  # passed
    assert by_metric["Faithfulness"][3] == 0.5
    assert by_metric["Faithfulness"][4] is False  # below threshold
    assert by_metric["PolicyAdherence"][3] == 0.7
    assert by_metric["PolicyAdherence"][4] is True  # exactly at threshold
    # evaluator_id encodes the model
    assert all(p[6] == "shadow_judge:gpt-oss-120b" for p in mirror_params)


@pytest.mark.asyncio
async def test_mirror_failure_does_not_kill_batch() -> None:
    """Primary shadow_judge_evals write must succeed even if mirror errors."""
    pool = _RecordingPool(fail_on="eval_results")
    worker = ShadowJudgeWorker()
    worker._pool = pool  # type: ignore[assignment]

    # Should NOT raise — the mirror write swallows its exception
    await worker._persist_rows([_row("trace-Z")])

    # Primary write completed; mirror write was attempted but raised
    assert len(pool.calls) == 1
    assert "shadow_judge_evals" in pool.calls[0][0]


@pytest.mark.asyncio
async def test_mirror_skips_rows_missing_trace_id() -> None:
    pool = _RecordingPool()
    worker = ShadowJudgeWorker()
    worker._pool = pool  # type: ignore[assignment]

    rows = [_row("trace-good")]
    rows[0].pop("trace_id", None)  # corrupt a row
    rows.append(_row("trace-fine"))

    await worker._persist_rows(rows)
    # Primary write attempts both rows; mirror writes only the one with trace_id.
    _, mirror_params = pool.calls[1]
    trace_ids = {p[1] for p in mirror_params}
    assert trace_ids == {"trace-fine"}
