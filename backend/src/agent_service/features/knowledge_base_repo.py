from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from typing import Any, Iterable

_table_ready = False
_table_lock = asyncio.Lock()
DEFAULT_CATEGORY_ID = "technical"
VECTOR_STATUS_PENDING = "pending"
VECTOR_STATUS_SYNCING = "syncing"
VECTOR_STATUS_SYNCED = "synced"
VECTOR_STATUS_FAILED = "failed"
_VECTOR_STATUS_VALUES = {
    VECTOR_STATUS_PENDING,
    VECTOR_STATUS_SYNCING,
    VECTOR_STATUS_SYNCED,
    VECTOR_STATUS_FAILED,
}
_DEFAULT_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("billing", "billing", "Billing"),
    ("account", "account", "Account"),
    ("data", "data", "Data"),
    ("technical", "technical", "Technical"),
    ("sales", "sales", "Sales"),
)


def normalize_question(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def content_hash(question: str, answer: str) -> str:
    payload = f"{normalize_question(question)}::{(answer or '').strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_category(value: str | None) -> str:
    if not value:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized


def _normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        source = value.split(",")
    elif isinstance(value, list):
        source = value
    else:
        return []

    tags: list[str] = []
    seen = set()
    for tag in source:
        text = re.sub(r"\s+", " ", str(tag or "")).strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        tags.append(text)
    return tags


def _build_category_lookup(rows: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in rows:
        category_id = str(row["id"])
        candidates = {
            category_id,
            _normalize_category(str(row["slug"])),
            _normalize_category(str(row["label"])),
            str(row["slug"]).strip().lower(),
            str(row["label"]).strip().lower(),
        }
        for candidate in candidates:
            if candidate:
                lookup[candidate] = category_id
    return lookup


def _resolve_category_id_from_lookup(
    category: str | None,
    category_lookup: dict[str, str],
    category_labels: list[str],
) -> str:
    if not category or not category.strip():
        return DEFAULT_CATEGORY_ID

    raw = category.strip()
    key = _normalize_category(raw)
    if key in category_lookup:
        return category_lookup[key]

    lower = raw.lower()
    if lower in category_lookup:
        return category_lookup[lower]

    available = ", ".join(category_labels)
    raise ValueError(f"Unknown category '{raw}'. Allowed categories: {available}")


class KnowledgeBaseRepo:
    async def ensure_table(self, pool: Any) -> None:
        global _table_ready
        if _table_ready:
            return

        async with _table_lock:
            if _table_ready:
                return

            await pool.execute("""
                CREATE TABLE IF NOT EXISTS public.faq_categories (
                    category_id text PRIMARY KEY,
                    slug text NOT NULL UNIQUE,
                    label text NOT NULL UNIQUE,
                    is_active boolean NOT NULL DEFAULT true,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """)
            await pool.executemany(
                """
                INSERT INTO public.faq_categories (category_id, slug, label, is_active, created_at, updated_at)
                VALUES ($1, $2, $3, true, now(), now())
                ON CONFLICT (category_id)
                DO UPDATE
                SET slug = EXCLUDED.slug,
                    label = EXCLUDED.label,
                    is_active = true,
                    updated_at = now()
                """,
                _DEFAULT_CATEGORIES,
            )

            await pool.execute("""
                CREATE TABLE IF NOT EXISTS public.nbfc_faqs (
                    id bigserial PRIMARY KEY,
                    faq_id text,
                    question_key text NOT NULL UNIQUE,
                    question text NOT NULL,
                    answer text NOT NULL,
                    category_id text,
                    tags text[] DEFAULT '{}',
                    vector_status text,
                    vector_error text,
                    vector_updated_at timestamptz,
                    source text NOT NULL DEFAULT 'manual',
                    source_ref text,
                    content_hash text NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ADD COLUMN IF NOT EXISTS faq_id text
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ADD COLUMN IF NOT EXISTS category_id text
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ADD COLUMN IF NOT EXISTS tags text[] DEFAULT '{}'
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ADD COLUMN IF NOT EXISTS vector_status text
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ADD COLUMN IF NOT EXISTS vector_error text
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ADD COLUMN IF NOT EXISTS vector_updated_at timestamptz
                """)

            rows_missing_ids = await pool.fetch("""
                SELECT id
                FROM public.nbfc_faqs
                WHERE faq_id IS NULL OR faq_id = ''
                """)
            if rows_missing_ids:
                await pool.executemany(
                    """
                    UPDATE public.nbfc_faqs
                    SET faq_id = $1
                    WHERE id = $2
                    """,
                    [(str(uuid.uuid4()), row["id"]) for row in rows_missing_ids],
                )

            await pool.execute(
                """
                UPDATE public.nbfc_faqs
                SET category_id = $1
                WHERE category_id IS NULL OR category_id = ''
                """,
                DEFAULT_CATEGORY_ID,
            )
            await pool.execute("""
                UPDATE public.nbfc_faqs
                SET tags = '{}'::text[]
                WHERE tags IS NULL
                """)
            await pool.execute(
                """
                UPDATE public.nbfc_faqs
                SET vector_status = $1
                WHERE vector_status IS NULL OR vector_status = ''
                """,
                VECTOR_STATUS_PENDING,
            )

            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ALTER COLUMN faq_id SET NOT NULL
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ALTER COLUMN category_id SET DEFAULT 'technical'
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ALTER COLUMN category_id SET NOT NULL
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ALTER COLUMN tags SET DEFAULT '{}'::text[]
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ALTER COLUMN tags SET NOT NULL
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ALTER COLUMN vector_status SET DEFAULT 'pending'
                """)
            await pool.execute("""
                ALTER TABLE public.nbfc_faqs
                ALTER COLUMN vector_status SET NOT NULL
                """)

            await pool.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'nbfc_faqs_category_fk'
                    ) THEN
                        ALTER TABLE public.nbfc_faqs
                        ADD CONSTRAINT nbfc_faqs_category_fk
                        FOREIGN KEY (category_id)
                        REFERENCES public.faq_categories(category_id);
                    END IF;
                END $$;
                """)
            await pool.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'nbfc_faqs_vector_status_check'
                    ) THEN
                        ALTER TABLE public.nbfc_faqs
                        ADD CONSTRAINT nbfc_faqs_vector_status_check
                        CHECK (vector_status IN ('pending', 'syncing', 'synced', 'failed'));
                    END IF;
                END $$;
                """)

            await pool.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_nbfc_faqs_faq_id
                ON public.nbfc_faqs (faq_id)
                """)
            await pool.execute("""
                CREATE INDEX IF NOT EXISTS idx_nbfc_faqs_updated_at
                ON public.nbfc_faqs (updated_at DESC)
                """)
            await pool.execute("""
                CREATE INDEX IF NOT EXISTS idx_nbfc_faqs_question
                ON public.nbfc_faqs (question)
                """)
            await pool.execute("""
                CREATE INDEX IF NOT EXISTS idx_nbfc_faqs_category
                ON public.nbfc_faqs (category_id)
                """)

            _table_ready = True

    async def list_faqs(self, pool: Any, limit: int, skip: int) -> list[dict[str, Any]]:
        await self.ensure_table(pool)
        rows = await pool.fetch(
            """
            SELECT
                f.faq_id,
                f.question,
                f.answer,
                f.created_at,
                f.updated_at,
                COALESCE(c.label, 'Technical') AS category,
                f.tags,
                f.vector_status,
                f.vector_error,
                f.vector_updated_at
            FROM public.nbfc_faqs f
            LEFT JOIN public.faq_categories c ON c.category_id = f.category_id
            ORDER BY updated_at DESC
            OFFSET $1
            LIMIT $2
            """,
            skip,
            limit,
        )
        return [
            {
                "id": row["faq_id"],
                "question": row["question"],
                "answer": row["answer"],
                "category": row["category"] or "Technical",
                "tags": list(row["tags"] or []),
                "vector_status": row["vector_status"] or VECTOR_STATUS_PENDING,
                "vectorized": (row["vector_status"] or VECTOR_STATUS_PENDING)
                == VECTOR_STATUS_SYNCED,
                "vector_error": row["vector_error"],
                "vector_updated_at": (
                    row["vector_updated_at"].isoformat() if row["vector_updated_at"] else None
                ),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            for row in rows
        ]

    async def list_categories(self, pool: Any) -> list[dict[str, Any]]:
        await self.ensure_table(pool)
        rows = await pool.fetch("""
            SELECT category_id, slug, label, is_active
            FROM public.faq_categories
            WHERE is_active = true
            ORDER BY label ASC
            """)
        return [
            {
                "id": row["category_id"],
                "slug": row["slug"],
                "label": row["label"],
                "is_active": row["is_active"],
            }
            for row in rows
        ]

    async def resolve_category_id(self, pool: Any, category: str | None) -> str:
        await self.ensure_table(pool)
        categories = await self.list_categories(pool)
        return _resolve_category_id_from_lookup(
            category,
            _build_category_lookup(categories),
            [str(row["label"]) for row in categories],
        )

    async def upsert_many(
        self,
        pool: Any,
        items: Iterable[dict[str, Any]],
        *,
        source: str,
        source_ref: str | None = None,
    ) -> int:
        await self.ensure_table(pool)
        categories = await self.list_categories(pool)
        category_lookup = _build_category_lookup(categories)
        category_labels = [str(row["label"]) for row in categories]
        rows = []
        for item in items:
            question = (item.get("question") or "").strip()
            answer = (item.get("answer") or "").strip()
            if not question or not answer:
                continue
            category_id = _resolve_category_id_from_lookup(
                str(item.get("category") or ""),
                category_lookup,
                category_labels,
            )
            tags = _normalize_tags(item.get("tags"))
            rows.append(
                {
                    "faq_id": str(item.get("id") or "").strip() or str(uuid.uuid4()),
                    "question_key": normalize_question(question),
                    "question": question,
                    "answer": answer,
                    "category_id": category_id,
                    "tags": tags,
                    "source": source,
                    "source_ref": source_ref,
                    "content_hash": content_hash(question, answer),
                }
            )

        if not rows:
            return 0

        await pool.executemany(
            """
            INSERT INTO public.nbfc_faqs (
                faq_id,
                question_key,
                question,
                answer,
                category_id,
                tags,
                vector_status,
                vector_error,
                vector_updated_at,
                source,
                source_ref,
                content_hash,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, NULL, NULL, $8, $9, $10, now(), now())
            ON CONFLICT (question_key)
            DO UPDATE
              SET question = EXCLUDED.question,
                  answer = EXCLUDED.answer,
                  category_id = EXCLUDED.category_id,
                  tags = EXCLUDED.tags,
                  vector_status = EXCLUDED.vector_status,
                  vector_error = NULL,
                  vector_updated_at = NULL,
                  source = EXCLUDED.source,
                  source_ref = EXCLUDED.source_ref,
                  content_hash = EXCLUDED.content_hash,
                  updated_at = now()
            """,
            [
                (
                    row["faq_id"],
                    row["question_key"],
                    row["question"],
                    row["answer"],
                    row["category_id"],
                    row["tags"],
                    VECTOR_STATUS_PENDING,
                    row["source"],
                    row["source_ref"],
                    row["content_hash"],
                )
                for row in rows
            ],
        )
        return len(rows)

    async def update_one(
        self,
        pool: Any,
        *,
        faq_id: str | None,
        original_question: str | None,
        new_question: str | None,
        new_answer: str | None,
        new_category: str | None,
        new_tags: list[str] | None,
    ) -> bool:
        await self.ensure_table(pool)
        identifier_id = (faq_id or "").strip()
        original_key = normalize_question(original_question or "")
        row = None
        if identifier_id:
            row = await pool.fetchrow(
                """
                SELECT faq_id, question, answer, category_id, tags
                FROM public.nbfc_faqs
                WHERE faq_id = $1
                """,
                identifier_id,
            )
        if row is None and original_key:
            row = await pool.fetchrow(
                """
                SELECT faq_id, question, answer, category_id, tags
                FROM public.nbfc_faqs
                WHERE question_key = $1
                """,
                original_key,
            )
        if row is None:
            return False

        final_question = (new_question or row["question"] or "").strip()
        final_answer = (new_answer or row["answer"] or "").strip()
        if not final_question or not final_answer:
            return False
        final_category = await self.resolve_category_id(pool, new_category or row["category_id"])
        final_tags = _normalize_tags(new_tags if new_tags is not None else row["tags"])
        target_key = normalize_question(final_question)

        await pool.execute(
            """
            UPDATE public.nbfc_faqs
            SET question_key = $1,
                question = $2,
                answer = $3,
                category_id = $4,
                tags = $5,
                source = 'manual_edit',
                source_ref = NULL,
                content_hash = $6,
                vector_status = $7,
                vector_error = NULL,
                vector_updated_at = NULL,
                updated_at = now()
            WHERE faq_id = $8
            """,
            target_key,
            final_question,
            final_answer,
            final_category,
            final_tags,
            content_hash(final_question, final_answer),
            VECTOR_STATUS_PENDING,
            row["faq_id"],
        )
        return True

    async def delete_one(
        self,
        pool: Any,
        *,
        faq_id: str | None = None,
        question: str | None = None,
    ) -> int:
        await self.ensure_table(pool)
        target_id = (faq_id or "").strip()
        if target_id:
            result = await pool.execute(
                """
                DELETE FROM public.nbfc_faqs
                WHERE faq_id = $1
                """,
                target_id,
            )
        else:
            result = await pool.execute(
                """
                DELETE FROM public.nbfc_faqs
                WHERE question_key = $1
                """,
                normalize_question(question or ""),
            )
        # asyncpg returns: DELETE <n>
        return int(str(result).split()[-1])

    async def delete_all(self, pool: Any) -> int:
        await self.ensure_table(pool)
        result = await pool.execute("DELETE FROM public.nbfc_faqs")
        return int(str(result).split()[-1])

    async def search_local(self, pool: Any, query: str, limit: int = 5) -> list[dict[str, Any]]:
        await self.ensure_table(pool)
        q = (query or "").strip()
        if not q:
            return []

        rows = await pool.fetch(
            """
            SELECT question, answer
            FROM public.nbfc_faqs
            WHERE question ILIKE ('%' || $1 || '%')
               OR answer ILIKE ('%' || $1 || '%')
            ORDER BY updated_at DESC
            LIMIT $2
            """,
            q,
            limit,
        )
        return [
            {
                "question": row["question"],
                "answer": row["answer"],
                "score": 1.0,
            }
            for row in rows
        ]

    async def dump_all(self, pool: Any) -> list[dict[str, str]]:
        await self.ensure_table(pool)
        rows = await pool.fetch("""
            SELECT question_key, question, answer
            FROM public.nbfc_faqs
            ORDER BY updated_at DESC
            """)
        return [
            {
                "question_key": row["question_key"],
                "question": row["question"],
                "answer": row["answer"],
            }
            for row in rows
        ]

    async def set_vector_status_for_question_keys(
        self,
        pool: Any,
        question_keys: list[str],
        *,
        status: str,
        error: str | None = None,
    ) -> None:
        await self.ensure_table(pool)
        if not question_keys:
            return
        if status not in _VECTOR_STATUS_VALUES:
            raise ValueError(f"Unsupported vector status: {status}")

        await pool.execute(
            """
            UPDATE public.nbfc_faqs
            SET vector_status = $1,
                vector_error = $2,
                vector_updated_at = CASE
                    WHEN $3 THEN now()
                    ELSE NULL
                END
            WHERE question_key = ANY($4::text[])
            """,
            status,
            error,
            status in {VECTOR_STATUS_SYNCED, VECTOR_STATUS_FAILED},
            question_keys,
        )
