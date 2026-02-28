#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

try:
    from src.common.neo4j_mgr import neo4j_mgr
except ModuleNotFoundError:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
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


def _to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _fetch_batch(limit: int) -> list[dict[str, Any]]:
    return await neo4j_mgr.execute_read(
        """
        MATCH (t:EvalTrace)
        WHERE (t.inline_guard_decision IS NULL OR trim(coalesce(t.inline_guard_decision, '')) = '')
          AND t.meta_json CONTAINS '"inline_guard"'
        RETURN t.trace_id AS trace_id, t.meta_json AS meta_json
        ORDER BY t.started_at DESC
        LIMIT $limit
        """,
        {"limit": limit},
    )


async def _count_missing() -> int:
    rows = await neo4j_mgr.execute_read(
        """
        MATCH (t:EvalTrace)
        WHERE (t.inline_guard_decision IS NULL OR trim(coalesce(t.inline_guard_decision, '')) = '')
          AND t.meta_json CONTAINS '"inline_guard"'
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
        SET t.inline_guard_decision = row.inline_guard_decision,
            t.inline_guard_reason_code = row.inline_guard_reason_code,
            t.inline_guard_risk_score = row.inline_guard_risk_score,
            t.updated_at = datetime()
        """,
        {"rows": rows},
    )


async def run(*, apply: bool, batch_size: int) -> int:
    await neo4j_mgr.connect()
    processed = 0

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
                meta_obj = _json_load_maybe(item.get("meta_json"))
                inline_guard = meta_obj.get("inline_guard") if isinstance(meta_obj, dict) else None
                if not isinstance(inline_guard, dict):
                    continue

                decision = str(inline_guard.get("decision") or "").strip()
                if not decision:
                    continue

                updates.append(
                    {
                        "trace_id": item.get("trace_id"),
                        "inline_guard_decision": decision,
                        "inline_guard_reason_code": str(
                            inline_guard.get("reason_code") or ""
                        ).strip()
                        or None,
                        "inline_guard_risk_score": _to_float_or_none(
                            inline_guard.get("risk_score")
                        ),
                    }
                )

            if apply and updates:
                await _apply_updates(updates)

            processed += len(updates)
            print(f"processed={processed} apply={apply}")

            if len(batch) < batch_size:
                break
    finally:
        await neo4j_mgr.close()

    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill inline guard fields on EvalTrace nodes")
    parser.add_argument("--apply", action="store_true", help="Persist updates to Neo4j")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    total = asyncio.run(run(apply=args.apply, batch_size=max(1, args.batch_size)))
    print(f"done total_processed={total} apply={args.apply}")


if __name__ == "__main__":
    main()
