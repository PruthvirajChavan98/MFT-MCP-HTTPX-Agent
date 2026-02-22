from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.agent_service.core.config import (
    GROQ_API_KEYS,
    GROQ_BASE_URL,
    SHADOW_JUDGE_BATCH_SIZE,
    SHADOW_JUDGE_ENABLED,
    SHADOW_JUDGE_MODEL,
    SHADOW_JUDGE_MODEL_FALLBACK,
    SHADOW_JUDGE_POLL_SECONDS,
    SHADOW_JUDGE_REASONING_EFFORT,
)
from src.agent_service.core.http_client import close_http_client, get_http_client
from src.agent_service.eval_store.shadow_queue import RedisTraceQueue, trace_queue
from src.common.neo4j_mgr import neo4j_mgr

log = logging.getLogger(__name__)

_WRITE_EVALS_QUERY = """
UNWIND $rows AS row
CREATE (e:ShadowJudgeEval)
SET e = row
"""


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _default_eval_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "eval_id": uuid.uuid4().hex,
        "evaluated_at": _utc_iso_now(),
        "trace_id": item.get("trace_id"),
        "session_id": item.get("session_id"),
        "helpfulness": 0.0,
        "faithfulness": 0.0,
        "policy_adherence": 0.0,
        "summary": "Evaluation parsing fallback applied.",
        "model": SHADOW_JUDGE_MODEL,
    }


class ShadowJudgeWorker:
    def __init__(self, queue: RedisTraceQueue = trace_queue):
        self.queue = queue
        self.poll_seconds = SHADOW_JUDGE_POLL_SECONDS
        self.batch_size = SHADOW_JUDGE_BATCH_SIZE

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
                    "Evaluate each conversation item. Return JSON array with entries containing "
                    "trace_id, helpfulness, faithfulness, policy_adherence, summary. "
                    "Scores must be between 0 and 1."
                ),
            },
            {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
        ]
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "model_kwargs": {"reasoning_effort": SHADOW_JUDGE_REASONING_EFFORT},
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEYS[0]}",
            "Content-Type": "application/json",
        }
        client = await get_http_client()
        response = await client.post(
            f"{GROQ_BASE_URL.rstrip('/')}/openai/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
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
                    "evaluated_at": _utc_iso_now(),
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
            return await self._call_groq(batch, SHADOW_JUDGE_MODEL_FALLBACK)

    async def _persist_rows(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        await neo4j_mgr.execute_write(_WRITE_EVALS_QUERY, {"rows": rows})

    async def process_once(self) -> int:
        if not SHADOW_JUDGE_ENABLED:
            return 0
        batch = await self.queue.pop_batch(limit=self.batch_size)
        if not batch:
            return 0
        rows = await self._evaluate_batch(batch)
        await self._persist_rows(rows)
        return len(rows)

    async def run_forever(self) -> None:
        await neo4j_mgr.connect()
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
            await neo4j_mgr.close()


async def run_worker() -> None:
    worker = ShadowJudgeWorker()
    await worker.run_forever()
