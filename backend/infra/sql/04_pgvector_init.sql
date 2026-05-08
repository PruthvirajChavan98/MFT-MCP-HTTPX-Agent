-- =============================================================================
-- 04_pgvector_init.sql — pgvector extension + vector columns / tables
--
-- Loaded by db_migrate.sh in the same way 02_eval_schema.sql is. Idempotent:
-- CREATE EXTENSION IF NOT EXISTS, ADD COLUMN IF NOT EXISTS, CREATE TABLE IF NOT
-- EXISTS, CREATE INDEX IF NOT EXISTS — re-running is a no-op.
--
-- Backfill of the new `embedding` columns from Milvus is done out-of-band by
-- backend/scripts/migrate_milvus_to_pgvector.py. Until that runs the columns
-- stay NULL and the pgvector backend reads zero rows; with VECTOR_STORE_BACKEND
-- defaulting to milvus on the merging PR, the live system keeps reading from
-- Milvus until the flag flips.
-- =============================================================================

-- NOTE: CREATE EXTENSION vector runs in db_migrate.sh as the postgresadmin
-- superuser before this file is applied, since the pgvector extension is
-- not marked "trusted" in pgvector/pgvector:pg18-trixie. By the time this
-- file runs as the app user (mft), the extension is already installed in
-- the target database and `vector(N)` types resolve.

-- ─────────────────────────────────────────────────────────────────────────────
-- eval_traces — add 1536-dim embedding column + HNSW index for cosine search.
-- The text doc that gets embedded already lives in eval_traces.doc.
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE eval_traces
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

CREATE INDEX IF NOT EXISTS eval_traces_embedding_hnsw
    ON eval_traces USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- ─────────────────────────────────────────────────────────────────────────────
-- eval_results — same shape.
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE eval_results
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

CREATE INDEX IF NOT EXISTS eval_results_embedding_hnsw
    ON eval_results USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- ─────────────────────────────────────────────────────────────────────────────
-- kb_faqs — was Milvus-only with metadata fields. New pgvector table mirrors
-- the langchain-milvus document shape (page_content + metadata) flattened.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kb_faqs (
    question_key    text PRIMARY KEY,
    question        text NOT NULL,
    answer          text NOT NULL,
    category        text NOT NULL DEFAULT '',
    embedding       vector(1536) NOT NULL,
    embedding_model text NOT NULL,
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS kb_faqs_embedding_hnsw
    ON kb_faqs USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

CREATE INDEX IF NOT EXISTS kb_faqs_category ON kb_faqs (category);

-- ─────────────────────────────────────────────────────────────────────────────
-- inline_guard_cache — 384-dim MiniLM embeddings, content-hash dedupe key.
-- The (content_hash, model_version, embedder_version) UNIQUE makes the
-- writeback ON CONFLICT idempotent across model upgrades.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inline_guard_cache (
    pk               bigserial PRIMARY KEY,
    decision         varchar(16) NOT NULL,
    reason_code      varchar(64) NOT NULL,
    risk_score       double precision NOT NULL,
    model_version    varchar(64) NOT NULL,
    embedder_version varchar(64) NOT NULL,
    content_hash     varchar(64) NOT NULL,
    ts               bigint NOT NULL,
    embedding        vector(384) NOT NULL,
    UNIQUE (content_hash, model_version, embedder_version)
);

CREATE INDEX IF NOT EXISTS inline_guard_cache_embedding_hnsw
    ON inline_guard_cache USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

CREATE INDEX IF NOT EXISTS inline_guard_cache_ts ON inline_guard_cache (ts);
