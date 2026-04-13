from __future__ import annotations

import asyncio
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.agent_service.api.admin_auth import require_admin

router = APIRouter(tags=["feedback"])

_table_ready = False
_table_lock = asyncio.Lock()


class FeedbackCreateRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=200)
    trace_id: Optional[str] = Field(default=None, max_length=200)
    rating: Literal["thumbs_up", "thumbs_down"]
    comment: Optional[str] = Field(default=None, max_length=2000)
    category: Optional[str] = Field(default=None, max_length=120)


def _get_pool(request: Request):
    pool_manager = getattr(request.app.state, "postgres_pool", None)
    pool = getattr(pool_manager, "pool", None) if pool_manager else None
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL pool unavailable. Configure POSTGRES_DSN for feedback storage.",
        )
    return pool


async def _ensure_table(pool) -> None:
    global _table_ready
    if _table_ready:
        return

    async with _table_lock:
        if _table_ready:
            return

        await pool.execute("""
            CREATE TABLE IF NOT EXISTS public.nbfc_feedback (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id text NOT NULL,
                trace_id text,
                rating text NOT NULL CHECK (rating IN ('thumbs_up', 'thumbs_down')),
                comment text,
                category text,
                created_at timestamptz NOT NULL DEFAULT now()
            )
            """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_nbfc_feedback_created_at
            ON public.nbfc_feedback (created_at DESC)
            """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_nbfc_feedback_session_id
            ON public.nbfc_feedback (session_id)
            """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_nbfc_feedback_rating
            ON public.nbfc_feedback (rating)
            """)

        _table_ready = True


@router.post("/agent/feedback")
async def submit_feedback(payload: FeedbackCreateRequest, request: Request):
    pool = _get_pool(request)
    await _ensure_table(pool)

    row = await pool.fetchrow(
        """
        INSERT INTO public.nbfc_feedback (session_id, trace_id, rating, comment, category)
        VALUES ($1, NULLIF($2, ''), $3, NULLIF($4, ''), NULLIF($5, ''))
        RETURNING id::text AS id, created_at
        """,
        payload.session_id.strip(),
        (payload.trace_id or "").strip(),
        payload.rating,
        (payload.comment or "").strip(),
        (payload.category or "").strip(),
    )

    if row is None:
        raise HTTPException(status_code=500, detail="Failed to persist feedback")

    return {
        "status": "created",
        "id": row["id"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/agent/admin/feedback")
async def get_feedback(
    request: Request,
    _: None = Depends(require_admin),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    rating: Optional[Literal["thumbs_up", "thumbs_down"]] = None,
    session_id: Optional[str] = None,
):
    pool = _get_pool(request)
    await _ensure_table(pool)

    rows = await pool.fetch(
        """
        SELECT
            id::text AS id,
            session_id,
            trace_id,
            rating,
            comment,
            category,
            created_at
        FROM public.nbfc_feedback
        WHERE ($1::text IS NULL OR rating = $1)
          AND ($2::text IS NULL OR session_id = $2)
        ORDER BY created_at DESC
        OFFSET $3
        LIMIT $4
        """,
        rating,
        session_id.strip() if session_id else None,
        offset,
        limit,
    )

    items = [
        {
            "id": row["id"],
            "session_id": row["session_id"],
            "trace_id": row["trace_id"],
            "rating": row["rating"],
            "comment": row["comment"],
            "category": row["category"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]

    return {"items": items, "count": len(items), "limit": limit, "offset": offset}


@router.get("/agent/admin/feedback/summary")
async def get_feedback_summary(request: Request, _: None = Depends(require_admin)):
    pool = _get_pool(request)
    await _ensure_table(pool)

    row = await pool.fetchrow("""
        SELECT
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE rating = 'thumbs_up')::int AS thumbs_up,
            COUNT(*) FILTER (WHERE rating = 'thumbs_down')::int AS thumbs_down
        FROM public.nbfc_feedback
        """)

    total = int(row["total"]) if row and row["total"] is not None else 0
    thumbs_up = int(row["thumbs_up"]) if row and row["thumbs_up"] is not None else 0
    thumbs_down = int(row["thumbs_down"]) if row and row["thumbs_down"] is not None else 0

    return {
        "total": total,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "positive_rate": (thumbs_up / total) if total else 0.0,
    }
