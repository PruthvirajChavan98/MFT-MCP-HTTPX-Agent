-- ─────────────────────────────────────────────────────────────────────────────
-- shadow_judge_evals.status — classify silent failures so the admin UI can
-- distinguish a real 0/0/0 verdict from a judge that couldn't run.
--
-- Values:
--   'ok'                   — judge ran successfully, scores reflect actual verdict
--   'parse_fallback'       — judge ran but response was missing this trace's entry
--                            (default 0/0/0 row was persisted to prevent backlog)
--   'upstream_unavailable' — primary and fallback models both returned HTTP 4xx/5xx
--                            (default 0/0/0 row was persisted)
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE shadow_judge_evals
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ok';

-- Partial index — most rows are 'ok'; we only ever query the failing ones.
CREATE INDEX IF NOT EXISTS idx_shadow_judge_evals_status
    ON shadow_judge_evals (status)
    WHERE status <> 'ok';

-- One-shot backfill: classify pre-existing rows by summary text.
-- Safe to re-run: the WHERE clause scopes it to rows still defaulted to 'ok'
-- whose summary matches a known failure pattern.
UPDATE shadow_judge_evals
SET status = CASE
        WHEN summary ILIKE '%unavailable%'
          OR summary ILIKE '%HTTP 4%'
          OR summary ILIKE '%HTTP 5%' THEN 'upstream_unavailable'
        WHEN summary ILIKE '%parsing fallback%'
          OR summary ILIKE '%default evaluation%' THEN 'parse_fallback'
        ELSE 'ok'
    END
WHERE status = 'ok'
  AND (
      summary ILIKE '%unavailable%'
   OR summary ILIKE '%HTTP %'
   OR summary ILIKE '%parsing fallback%'
  );
