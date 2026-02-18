// ============================================================
// Neo4j Eval Store Schema (Community-safe)
// - no NODE KEY (Enterprise-only)
// - unique via single-property constraints
// - JSON blobs stored as strings (*_json)
// ============================================================

// ---------- Constraints ----------
CREATE CONSTRAINT evaltrace_uniq IF NOT EXISTS
FOR (t:EvalTrace) REQUIRE t.trace_id IS UNIQUE;

CREATE CONSTRAINT evalresult_uniq IF NOT EXISTS
FOR (r:EvalResult) REQUIRE r.eval_id IS UNIQUE;

CREATE CONSTRAINT evalevent_key_uniq IF NOT EXISTS
FOR (e:EvalEvent) REQUIRE e.event_key IS UNIQUE;

// ---------- Trace indexes (filters/sort) ----------
CREATE INDEX evaltrace_session_idx IF NOT EXISTS
FOR (t:EvalTrace) ON (t.session_id);

CREATE INDEX evaltrace_status_idx IF NOT EXISTS
FOR (t:EvalTrace) ON (t.status);

CREATE INDEX evaltrace_provider_idx IF NOT EXISTS
FOR (t:EvalTrace) ON (t.provider);

CREATE INDEX evaltrace_model_idx IF NOT EXISTS
FOR (t:EvalTrace) ON (t.model);

CREATE INDEX evaltrace_case_idx IF NOT EXISTS
FOR (t:EvalTrace) ON (t.case_id);

CREATE INDEX evaltrace_started_at_idx IF NOT EXISTS
FOR (t:EvalTrace) ON (t.started_at);

// ---------- Event indexes ----------
CREATE INDEX evalevent_trace_id_idx IF NOT EXISTS
FOR (e:EvalEvent) ON (e.trace_id);

CREATE INDEX evalevent_seq_idx IF NOT EXISTS
FOR (e:EvalEvent) ON (e.seq);

CREATE INDEX evalevent_type_idx IF NOT EXISTS
FOR (e:EvalEvent) ON (e.event_type);

CREATE INDEX evalevent_name_idx IF NOT EXISTS
FOR (e:EvalEvent) ON (e.name);

// ---------- Result indexes (dashboard top + failures) ----------
CREATE INDEX evalresult_metric_idx IF NOT EXISTS
FOR (r:EvalResult) ON (r.metric_name);

CREATE INDEX evalresult_passed_idx IF NOT EXISTS
FOR (r:EvalResult) ON (r.passed);

CREATE INDEX evalresult_updated_at_idx IF NOT EXISTS
FOR (r:EvalResult) ON (r.updated_at);

// Fast “latest failures overall”
CREATE INDEX evalresult_passed_updated_at_idx IF NOT EXISTS
FOR (r:EvalResult) ON (r.passed, r.updated_at);

// Fast “latest failures for ONE metric”
CREATE INDEX evalresult_metric_passed_updated_at_idx IF NOT EXISTS
FOR (r:EvalResult) ON (r.metric_name, r.passed, r.updated_at);

// ---------- Fulltext indexes ----------
CREATE FULLTEXT INDEX evalevent_text IF NOT EXISTS
FOR (e:EvalEvent) ON EACH [e.text];

CREATE FULLTEXT INDEX evaltrace_text IF NOT EXISTS
FOR (t:EvalTrace) ON EACH [t.final_output, t.inputs_json];

CREATE FULLTEXT INDEX evalresult_text IF NOT EXISTS
FOR (r:EvalResult) ON EACH [r.metric_name, r.reasoning];

// ---------- Vector indexes (1536 dim: text-embedding-3-small) ----------
CREATE VECTOR INDEX evaltrace_embeddings IF NOT EXISTS
FOR (t:EvalTrace) ON (t.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX evalresult_embeddings IF NOT EXISTS
FOR (r:EvalResult) ON (r.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};