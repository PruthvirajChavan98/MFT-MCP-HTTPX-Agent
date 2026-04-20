from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx

from src.agent_service.core.config import (
    GROQ_API_KEYS,
    GROQ_BASE_URL,
    GROQ_KEY_COOLING_TTL_S,
    POSTGRES_DSN,
    SHADOW_JUDGE_BATCH_SIZE,
    SHADOW_JUDGE_ENABLED,
    SHADOW_JUDGE_MODEL,
    SHADOW_JUDGE_MODEL_FALLBACK,
    SHADOW_JUDGE_POLL_SECONDS,
)
from src.agent_service.core.http_client import close_http_client, get_http_client
from src.agent_service.eval_store.shadow_queue import RedisTraceQueue, trace_queue
from src.agent_service.llm.groq_rotator import mark_key_cooling, next_groq_key
from src.common.milvus_mgr import milvus_mgr

log = logging.getLogger(__name__)

_INSERT_SHADOW_JUDGE_EVAL = """
INSERT INTO shadow_judge_evals (
    eval_id, trace_id, session_id, model,
    helpfulness, faithfulness, policy_adherence,
    summary, raw_json, evaluated_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
ON CONFLICT (eval_id) DO NOTHING
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _extract_json_block(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1)
    return cleaned.strip()


def _coerce_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, score))


def _default_eval_row(
    item: dict[str, Any],
    *,
    summary: str = "Evaluation parsing fallback applied.",
    model: str | None = None,
) -> dict[str, Any]:
    return {
        "eval_id": uuid.uuid4().hex,
        "evaluated_at": _utc_now(),
        "trace_id": item.get("trace_id"),
        "session_id": item.get("session_id"),
        "helpfulness": 0.0,
        "faithfulness": 0.0,
        "policy_adherence": 0.0,
        "summary": summary,
        "model": model or SHADOW_JUDGE_MODEL,
    }


class ShadowJudgeWorker:
    def __init__(self, queue: RedisTraceQueue = trace_queue):
        self.queue = queue
        self.poll_seconds = SHADOW_JUDGE_POLL_SECONDS
        self.batch_size = SHADOW_JUDGE_BATCH_SIZE
        self._pool: asyncpg.Pool | None = None

    async def _call_groq(self, batch: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
        if not GROQ_API_KEYS:
            raise RuntimeError("GROQ_API_KEYS missing for shadow judge worker.")

        prompt_payload = [
            {
                "trace_id": item.get("trace_id"),
                "session_id": item.get("session_id"),
                "user_prompt": item.get("user_prompt"),
                "agent_response": item.get("agent_response"),
            }
            for item in batch
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a conversation quality evaluator. Evaluate each item and return a JSON object "
                    "with an 'evaluations' key containing an array. Each entry must have: "
                    "trace_id (string), helpfulness (0-1), faithfulness (0-1), policy_adherence (0-1), summary (string)."
                ),
            },
            {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
        ]
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        api_key = await next_groq_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        client = await get_http_client()
        response = await client.post(
            f"{GROQ_BASE_URL.rstrip('/')}/openai/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                await mark_key_cooling(api_key, ttl_seconds=GROQ_KEY_COOLING_TTL_S)
            raise
        body = response.json()
        text = ""
        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str):
                text = content
        if not text:
            raise RuntimeError("Shadow judge received empty response content.")

        parsed = json.loads(_extract_json_block(text))
        if isinstance(parsed, dict):
            parsed = parsed.get("evaluations", [])
        if not isinstance(parsed, list):
            raise RuntimeError("Shadow judge response is not a JSON array.")

        by_trace: dict[str, dict[str, Any]] = {}
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            trace_id = str(entry.get("trace_id") or "")
            if trace_id:
                by_trace[trace_id] = entry

        rows: list[dict[str, Any]] = []
        for item in batch:
            trace_id = str(item.get("trace_id") or "")
            row = by_trace.get(trace_id)
            if not row:
                rows.append(_default_eval_row(item))
                continue
            rows.append(
                {
                    "eval_id": uuid.uuid4().hex,
                    "evaluated_at": _utc_now(),
                    "trace_id": trace_id or None,
                    "session_id": item.get("session_id"),
                    "helpfulness": _coerce_score(row.get("helpfulness")),
                    "faithfulness": _coerce_score(row.get("faithfulness")),
                    "policy_adherence": _coerce_score(row.get("policy_adherence")),
                    "summary": str(row.get("summary") or ""),
                    "model": model,
                }
            )
        return rows

    async def _evaluate_batch(self, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        try:
            return await self._call_groq(batch, SHADOW_JUDGE_MODEL)
        except Exception as primary_exc:  # noqa: BLE001
            log.warning("Primary shadow judge model failed, retrying fallback: %s", primary_exc)
            try:
                return await self._call_groq(batch, SHADOW_JUDGE_MODEL_FALLBACK)
            except httpx.HTTPStatusError as fallback_exc:
                status_code = fallback_exc.response.status_code
                if 400 <= status_code < 500:
                    log.error(
                        "Shadow judge fallback model rejected request (status=%s). "
                        "Persisting default eval rows to prevent queue backlog.",
                        status_code,
                    )
                    summary = (
                        f"Shadow judge unavailable (HTTP {status_code}); "
                        "default evaluation recorded."
                    )
                    return [
                        _default_eval_row(
                            item,
                            summary=summary,
                            model=SHADOW_JUDGE_MODEL_FALLBACK,
                        )
                        for item in batch
                    ]
                raise

    async def _persist_rows(self, rows: list[dict[str, Any]]) -> None:
        if not rows or self._pool is None:
            return
        params = [
            (
                r["eval_id"],
                r.get("trace_id"),
                r.get("session_id"),
                r.get("model"),
                r.get("helpfulness", 0.0),
                r.get("faithfulness", 0.0),
                r.get("policy_adherence", 0.0),
                r.get("summary", ""),
                json.dumps(r, ensure_ascii=False, default=str),
                r.get("evaluated_at"),
            )
            for r in rows
        ]
        await self._pool.executemany(_INSERT_SHADOW_JUDGE_EVAL, params)

    async def process_once(self) -> int:
        if not SHADOW_JUDGE_ENABLED:
            return 0
        batch = await self.queue.pop_batch(limit=self.batch_size)
        if not batch:
            return 0
        try:
            rows = await self._evaluate_batch(batch)
            await self._persist_rows(rows)
            return len(rows)
        except Exception as exc:  # noqa: BLE001
            if hasattr(self.queue, "requeue_or_dead_letter_batch"):
                try:
                    requeued, dead_lettered = await self.queue.requeue_or_dead_letter_batch(  # type: ignore[attr-defined]
                        batch,
                        reason=str(exc),
                    )
                    log.warning(
                        "Shadow judge batch failed; requeued=%s dead_lettered=%s error=%s",
                        requeued,
                        dead_lettered,
                        exc,
                    )
                except Exception as queue_exc:  # noqa: BLE001
                    log.exception("Failed to requeue/dead-letter shadow judge batch: %s", queue_exc)
            raise

    async def run_forever(self) -> None:
        await milvus_mgr.aconnect()
        log.info("Milvus stores initialized.")

        if POSTGRES_DSN:
            self._pool = await asyncpg.create_pool(
                POSTGRES_DSN, min_size=1, max_size=5, command_timeout=30
            )
            log.info("Shadow judge worker: PostgreSQL pool connected.")
        else:
            log.warning("Shadow judge worker: POSTGRES_DSN not set; eval persistence disabled.")

        log.info(
            "Shadow judge worker started (poll=%ss, batch_size=%s).",
            self.poll_seconds,
            self.batch_size,
        )
        try:
            while True:
                try:
                    processed = await self.process_once()
                    if processed:
                        log.info("Shadow judge processed %s traces.", processed)
                except Exception as exc:  # noqa: BLE001
                    log.exception("Shadow judge iteration failed: %s", exc)
                await asyncio.sleep(self.poll_seconds)
        finally:
            await close_http_client()
            if self._pool:
                await self._pool.close()


async def run_worker() -> None:
    worker = ShadowJudgeWorker()
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(run_worker())
