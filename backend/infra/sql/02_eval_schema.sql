-- =============================================================================
-- 02_eval_schema.sql — Eval observability tables (replaces Neo4j eval store)
--
-- Loaded automatically by PostgreSQL container on first init via:
--   ./backend/infra/sql/02_eval_schema.sql:/docker-entrypoint-initdb.d/02_eval_schema.sql:ro
--
-- All tables are idempotent (CREATE TABLE IF NOT EXISTS).
-- Milvus stores the actual embedding vectors; these tables hold metadata
-- used for filtered FTS and relational queries.
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- eval_traces
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS eval_traces (
    trace_id                        TEXT        PRIMARY KEY,
    case_id                         TEXT,
    session_id                      TEXT,
    provider                        TEXT,
    model                           TEXT,
    endpoint                        TEXT,

    started_at                      TIMESTAMPTZ,
    ended_at                        TIMESTAMPTZ,
    latency_ms                      INTEGER,
    status                          TEXT,
    error                           TEXT,

    inputs_json                     JSONB       NOT NULL DEFAULT '{}',
    final_output                    TEXT,
    tags_json                       JSONB       NOT NULL DEFAULT '{}',
    meta_json                       JSONB       NOT NULL DEFAULT '{}',

    -- Router / question classification
    question_category               TEXT,
    question_category_confidence    REAL,
    question_category_source        TEXT,

    -- Inline guardrail
    inline_guard_decision           TEXT,
    inline_guard_reason_code        TEXT,
    inline_guard_risk_score         REAL,

    -- Router decision
    router_backend                  TEXT,
    router_sentiment                TEXT,
    router_sentiment_score          REAL,
    router_override                 BOOLEAN,
    router_reason                   TEXT,
    router_reason_score             REAL,

    -- Milvus embedding metadata (vectors in Milvus; hash here to skip re-embedding)
    doc                             TEXT,
    doc_hash                        TEXT,
    embedding_model                 TEXT,
    embedding_updated_at            TIMESTAMPTZ,

    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Full-text search column (auto-maintained STORED generated column)
    fts TSVECTOR GENERATED ALWAYS AS (
        to_tsvector(
            'english',
            coalesce(final_output, '')        || ' ' ||
            coalesce(inputs_json->>'question', '') || ' ' ||
            coalesce(inputs_json->>'input', '')
        )
    ) STORED
);

CREATE INDEX IF NOT EXISTS idx_eval_traces_session   ON eval_traces (session_id);
CREATE INDEX IF NOT EXISTS idx_eval_traces_status    ON eval_traces (status);
CREATE INDEX IF NOT EXISTS idx_eval_traces_model     ON eval_traces (model);
CREATE INDEX IF NOT EXISTS idx_eval_traces_started   ON eval_traces (started_at DESC);
-- Cursor-based pagination (started_at DESC, trace_id DESC) — stable sort
CREATE INDEX IF NOT EXISTS idx_eval_traces_cursor    ON eval_traces (started_at DESC, trace_id DESC);
CREATE INDEX IF NOT EXISTS idx_eval_traces_fts       ON eval_traces USING GIN (fts);
CREATE INDEX IF NOT EXISTS idx_eval_traces_qcat      ON eval_traces (question_category);
CREATE INDEX IF NOT EXISTS idx_eval_traces_guard     ON eval_traces (inline_guard_decision);

-- ─────────────────────────────────────────────────────────────────────────────
-- eval_events
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS eval_events (
    event_key       TEXT        PRIMARY KEY,
    trace_id        TEXT        NOT NULL REFERENCES eval_traces (trace_id) ON DELETE CASCADE,
    seq             INTEGER     NOT NULL,
    ts              TIMESTAMPTZ,
    event_type      TEXT,
    name            TEXT,
    text            TEXT,
    payload_json    JSONB       NOT NULL DEFAULT '{}',
    meta_json       JSONB       NOT NULL DEFAULT '{}',

    fts TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(text, ''))
    ) STORED
);

CREATE INDEX IF NOT EXISTS idx_eval_events_trace ON eval_events (trace_id);
CREATE INDEX IF NOT EXISTS idx_eval_events_seq   ON eval_events (trace_id, seq ASC);
CREATE INDEX IF NOT EXISTS idx_eval_events_fts   ON eval_events USING GIN (fts);

-- ─────────────────────────────────────────────────────────────────────────────
-- eval_results
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS eval_results (
    eval_id             TEXT        PRIMARY KEY,
    trace_id            TEXT        NOT NULL REFERENCES eval_traces (trace_id) ON DELETE CASCADE,
    metric_name         TEXT,
    score               REAL,
    passed              BOOLEAN,
    reasoning           TEXT,
    evaluator_id        TEXT,
    meta_json           JSONB       NOT NULL DEFAULT '{}',
    evidence_json       JSONB       NOT NULL DEFAULT '[]',

    -- Milvus embedding metadata
    doc                 TEXT,
    doc_hash            TEXT,
    embedding_model     TEXT,
    embedding_updated_at TIMESTAMPTZ,

    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_results_trace      ON eval_results (trace_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_metric     ON eval_results (metric_name);
-- Composite for metric dashboard: filter by metric_name+passed, sort by updated_at
CREATE INDEX IF NOT EXISTS idx_eval_results_metric_p   ON eval_results (metric_name, passed, updated_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- eval_result_evidence  (junction: eval_result ↔ eval_event)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS eval_result_evidence (
    eval_id     TEXT NOT NULL REFERENCES eval_results (eval_id)  ON DELETE CASCADE,
    event_key   TEXT NOT NULL REFERENCES eval_events  (event_key) ON DELETE CASCADE,
    PRIMARY KEY (eval_id, event_key)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- shadow_judge_evals  (replaces ShadowJudgeEval Neo4j nodes)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shadow_judge_evals (
    eval_id          TEXT        PRIMARY KEY,
    trace_id         TEXT,
    session_id       TEXT,
    model            TEXT,
    helpfulness      REAL,
    faithfulness     REAL,
    policy_adherence REAL,
    summary          TEXT,
    raw_json         JSONB       NOT NULL DEFAULT '{}',
    evaluated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shadow_judge_evals_trace    ON shadow_judge_evals (trace_id);
CREATE INDEX IF NOT EXISTS idx_shadow_judge_evals_session  ON shadow_judge_evals (session_id);
CREATE INDEX IF NOT EXISTS idx_shadow_judge_evals_eval_at  ON shadow_judge_evals (evaluated_at DESC);
