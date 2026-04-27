-- One-shot: project existing rows from `shadow_judge_evals` into
-- `eval_results` so the trace-detail Evaluation panel surfaces the
-- shadow-judge dimensions alongside RAGAS metrics.
--
-- Idempotent: deterministic eval_ids (`shadow:<trace>:<metric>`) collide on
-- conflict and are no-ops. Re-run safe.
--
-- Invocation:
--   docker exec postgres psql -U mft -d mft_security \
--     -f /tmp/backfill_shadow_judge_mirror.sql
--
-- Or copy the file in first:
--   docker cp backend/scripts/backfill_shadow_judge_mirror.sql \
--     postgres:/tmp/backfill_shadow_judge_mirror.sql

INSERT INTO eval_results (
    eval_id, trace_id, metric_name, score, passed,
    reasoning, evaluator_id, meta_json, evidence_json
)
SELECT
    'shadow:' || trace_id || ':helpfulness',
    trace_id,
    'Helpfulness',
    helpfulness,
    helpfulness >= 0.7,
    COALESCE(summary, ''),
    'shadow_judge:' || COALESCE(model, 'gpt-oss-120b'),
    '{}'::jsonb,
    '[]'::jsonb
FROM shadow_judge_evals
ON CONFLICT (eval_id) DO NOTHING;

INSERT INTO eval_results (
    eval_id, trace_id, metric_name, score, passed,
    reasoning, evaluator_id, meta_json, evidence_json
)
SELECT
    'shadow:' || trace_id || ':faithfulness',
    trace_id,
    'Faithfulness',
    faithfulness,
    faithfulness >= 0.7,
    COALESCE(summary, ''),
    'shadow_judge:' || COALESCE(model, 'gpt-oss-120b'),
    '{}'::jsonb,
    '[]'::jsonb
FROM shadow_judge_evals
ON CONFLICT (eval_id) DO NOTHING;

INSERT INTO eval_results (
    eval_id, trace_id, metric_name, score, passed,
    reasoning, evaluator_id, meta_json, evidence_json
)
SELECT
    'shadow:' || trace_id || ':policy_adherence',
    trace_id,
    'PolicyAdherence',
    policy_adherence,
    policy_adherence >= 0.7,
    COALESCE(summary, ''),
    'shadow_judge:' || COALESCE(model, 'gpt-oss-120b'),
    '{}'::jsonb,
    '[]'::jsonb
FROM shadow_judge_evals
ON CONFLICT (eval_id) DO NOTHING;

-- Audit summary
SELECT
    metric_name,
    count(*) AS row_count,
    min(score)::numeric(4,3) AS min_score,
    max(score)::numeric(4,3) AS max_score
FROM eval_results
WHERE evaluator_id LIKE 'shadow_judge:%'
GROUP BY metric_name
ORDER BY metric_name;
