#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

try:
    from src.agent_service.features.question_category import classify_question_category
    from src.common.neo4j_mgr import neo4j_mgr
except ModuleNotFoundError:
    # Support direct script execution via `python scripts/...` in addition to module mode.
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    from src.agent_service.features.question_category import classify_question_category
    from src.common.neo4j_mgr import neo4j_mgr


def _json_load_maybe(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    if (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    ):
        try:
            return json.loads(stripped)
        except Exception:
            return value
    return value


def _extract_question(inputs_json: Any) -> str:
    payload = _json_load_maybe(inputs_json)
    if isinstance(payload, dict):
        return str(payload.get("question") or "").strip()
    return ""


async def _fetch_batch(limit: int) -> list[dict[str, Any]]:
    return await neo4j_mgr.execute_read(
        """
        MATCH (t:EvalTrace)
        WHERE t.question_category IS NULL OR trim(coalesce(t.question_category, '')) = ''
        RETURN t.trace_id AS trace_id,
               t.inputs_json AS inputs_json,
               t.router_reason AS router_reason
        ORDER BY t.started_at DESC
        LIMIT $limit
        """,
        {"limit": limit},
    )


async def _count_missing() -> int:
    rows = await neo4j_mgr.execute_read(
        """
        MATCH (t:EvalTrace)
        WHERE t.question_category IS NULL OR trim(coalesce(t.question_category, '')) = ''
        RETURN count(t) AS total
        """,
        {},
    )
    if not rows:
        return 0
    return int(rows[0].get("total") or 0)


async def _apply_updates(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    await neo4j_mgr.execute_write(
        """
        UNWIND $rows AS row
        MATCH (t:EvalTrace {trace_id: row.trace_id})
        SET t.question_category = row.question_category,
            t.question_category_confidence = row.question_category_confidence,
            t.question_category_source = row.question_category_source,
            t.updated_at = datetime()
        """,
        {"rows": rows},
    )


async def run(apply: bool, batch_size: int) -> int:
    await neo4j_mgr.connect()
    updated = 0

    try:
        if not apply:
            total = await _count_missing()
            print(f"dry_run_missing={total}")
            return total

        while True:
            batch = await _fetch_batch(batch_size)
            if not batch:
                break

            updates: list[dict[str, Any]] = []
            for item in batch:
                question = _extract_question(item.get("inputs_json"))
                router_reason = item.get("router_reason")
                result = classify_question_category(question, str(router_reason or "") or None)
                updates.append(
                    {
                        "trace_id": item.get("trace_id"),
                        "question_category": result.category,
                        "question_category_confidence": result.confidence,
                        "question_category_source": result.source,
                    }
                )

            if apply:
                await _apply_updates(updates)
            updated += len(updates)
            print(f"processed={updated} apply={apply}")

            if len(batch) < batch_size:
                break
    finally:
        await neo4j_mgr.close()

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill EvalTrace question categories")
    parser.add_argument("--apply", action="store_true", help="Persist updates to Neo4j")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    total = asyncio.run(run(apply=args.apply, batch_size=max(1, args.batch_size)))
    print(f"done total_processed={total} apply={args.apply}")


if __name__ == "__main__":
    main()
