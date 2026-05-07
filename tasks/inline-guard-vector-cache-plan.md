# Plan: ship the inline-guard vector-similarity cache (Layer 2.5)

## Context

The resume bullet `"multi-layered security gateway with sub-second inline prompt guarding combining vector similarity caching with OpenAI GPT OSS Safeguard 120B"` describes a cache layer in front of the Groq Safeguard classifier. It is **designed but not shipped**. The shipped layers are:

1. `_HIGH_RISK_PATTERNS` regex pre-filter — `~1 ms` (`backend/src/agent_service/security/inline_guard.py:39-69`)
2. Groq Safeguard 120B classifier call — `~400–800 ms` (`_groq_guard_check` at line 214)
3. Total-timeout / fail-closed envelope — bounded at `INLINE_GUARD_TOTAL_TIMEOUT_MS`

Why the cache wasn't built originally: a 20-sample latency probe inside the live agent container measured `text-embedding-3-small` over OpenRouter at `p50=325 ms / p95=692 ms` — *the same order as the classifier the cache would skip*. End-to-end `embed + Milvus search` was `p50=329 ms`. With `text-embedding-3-small`, the cache is a wash on hit and a regression on miss.

The unblocking move is a **local CPU embedder**. `sentence-transformers/all-MiniLM-L6-v2` (384-dim) embeds a single short prompt in `~10–15 ms` on CPU with no network round-trip. Total cache lookup drops to `~15–25 ms` — a ~30× speedup over the classifier on hits, and negligible overhead on misses.

This plan ships that cache as **Layer 2.5**, between the regex (1) and the classifier (2), so the four-layer story in the resume bullet is true at runtime.

The `inline_guard.py` regex set was just expanded for tool-enumeration probes (PR #23). This plan does not change that — it sits in front of and bypasses the classifier when a cached decision exists at sufficient similarity.

## Goal

| Metric | Target | Why |
|---|---|---|
| Cache hit rate on prod traffic | ≥ 50 % after a 24 h warm-up | Most user prompts in production are paraphrases of common queries (login, dashboard, foreclosure FAQ) |
| End-to-end guard latency on cache hit | p95 ≤ 30 ms | One embedding (~10 ms) + one Milvus search (~5 ms) + bookkeeping |
| End-to-end guard latency on cache miss | p95 ≤ classifier_p95 + 25 ms | Cache lookup runs *before* the classifier, then writes back after; the second write happens in `eval_store/_bg.schedule()` so it does not block the response path |
| Behaviour parity vs current guard | identical decisions on regex hits and on classifier-vote outcomes | Cache is opt-in via env flag; same decision space (`pass` / `degraded_allow` / `block`) |

Non-goal: deeper changes to the regex set or the classifier system prompt. PR #23 already covered that.

## Aesthetic / engineering direction

Three principles, in order of priority:

1. **Measurement-driven.** Every threshold (similarity, TTL, write-back rate) is configurable via env, defaults checked-in, and fronted by a Prometheus histogram so we can re-tune without a deploy. The cache is **off by default behind `INLINE_GUARD_CACHE_ENABLED=false`** until prod telemetry confirms hit rate ≥ 30 %.
2. **Fail-open to the classifier.** Any cache failure (Milvus unreachable, embedder OOM, malformed entry) falls through to the existing classifier path. The cache is a perf accelerator, never a correctness gate.
3. **Idempotent at the cache boundary.** Decision write-backs are keyed by `model_version + content_hash` so concurrent writes for the same prompt converge; embedder and classifier model identifiers are stamped on every entry so a model swap auto-invalidates the cache without a sweep.

## Implementation approach

### Phase 1 — local embedder + image plumbing (~1 hour)

- Add `sentence-transformers>=3.0,<4.0` and `torch>=2.4,<3.0` (CPU wheel) to `backend/pyproject.toml`. Pin to a tested version after running once locally.
- New module `backend/src/agent_service/security/local_embedder.py`:
  - `class LocalEmbedder` with one async method `aembed_query(text: str) -> list[float]`.
  - Lazy-loaded singleton via `get_local_embedder()`.
  - Underlying model: `sentence-transformers/all-MiniLM-L6-v2`. 384-dim. Loaded onto CPU via `SentenceTransformer(...).encode([text], normalize_embeddings=True)`.
  - Wrap the synchronous `encode` in `loop.run_in_executor(None, ...)` so we don't block the asyncio loop.
  - Add a `warm()` method that runs one inference on a throwaway string at startup.
- Hook `warm()` into `backend/src/agent_service/core/app_factory.py`'s lifespan. If `INLINE_GUARD_CACHE_ENABLED=true`, log warm time; if disabled, skip entirely.
- Add Prometheus histogram `agent_inline_guard_embedder_seconds{model="MiniLM-L6-v2"}` around `aembed_query`.

Image-size impact: `torch+CPU` adds ~250 MB; `sentence-transformers` adds ~50 MB; the model itself is ~22 MB and cached at `/root/.cache/torch/sentence_transformers`. Bake the model into the image at build time via a `RUN python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")'` step in the agent Dockerfile so cold-start doesn't pull from HF on boot.

### Phase 2 — Milvus collection + manager wiring (~30 min)

- Add a new collection `inline_guard_cache` (384-dim) alongside `kb_faqs`, `eval_traces`, `eval_results` in `backend/src/common/milvus_mgr.py:84-106`.
- Schema fields: `pk` (auto), `vector` (384-dim, COSINE metric, HNSW index `M=16, efConstruction=200`), `decision` (varchar 16), `reason_code` (varchar 64), `risk_score` (float), `model_version` (varchar 64), `embedder_version` (varchar 64), `content_hash` (varchar 64), `ts` (int64 epoch).
- Index: HNSW. Search-time `ef=64`.
- Manager exposes `mgr.guard_cache: Milvus | None`, initialised in `_init_stores`.
- New operator script `backend/scripts/rebuild_inline_guard_cache_collection.py` mirroring the existing `rebuild_eval_results_collection.py` shape — drop-and-recreate. Add a `make rebuild-inline-guard-cache-collection` target.

### Phase 3 — wire the cache into `evaluate_prompt_safety_decision` (~1 hour)

This is the core change in `backend/src/agent_service/security/inline_guard.py`.

Insert a new function `_lookup_cache(prompt: str, lexical_risk: float) -> CacheLookup | None`:

```
flow:
  1. compute content_hash = sha256(normalize(prompt))[:32]
  2. embed prompt via local embedder (~10 ms)
  3. milvus search top_k=1 with the embedding
  4. if top_score >= INLINE_GUARD_CACHE_SIM_THRESHOLD (default 0.93)
        AND hit.model_version == current GROQ_GUARD_MODEL
        AND hit.embedder_version == LOCAL_EMBEDDER_VERSION
        AND now - hit.ts <= INLINE_GUARD_CACHE_TTL_SECONDS (default 30 days)
       → return cached InlineGuardDecision
  5. else → return None (caller falls through to classifier)
```

In `evaluate_prompt_safety_decision`, between the existing regex pass and the `_groq_guard_check` call, slot the lookup:

```
flow:
  if INLINE_GUARD_CACHE_ENABLED:
      cached = await _lookup_cache(clean_prompt, lexical_risk)
      if cached:
          metrics: cache_hits_total++
          return _finalize_decision(cached)
      metrics: cache_misses_total++
  ... existing classifier path runs ...
  if cache enabled and we just got a fresh decision from the classifier:
      schedule(_writeback_cache(prompt, embedding, decision))   # fire-and-forget
```

Reuse the fire-and-forget helper at `backend/src/agent_service/eval_store/_bg.py:schedule()` for the write-back so the response path is not blocked.

**Cache poisoning controls** (built-in from day one):

- Only **classifier-derived** decisions get cached. Regex-only decisions are not (they don't need the cache; regex is already 1 ms and deterministic).
- The hash `model_version + embedder_version` invalidates the cache when either model changes. No manual flush needed on a swap.
- `INLINE_GUARD_CACHE_RESHADOW_RATE` (default 0.02) — 2 % of cache hits also call the classifier and compare; mismatches log a warning + drop the cache entry. This catches model drift and adversarial cache-warm attempts.

### Phase 4 — telemetry + admin surface (~30 min)

Three Prometheus counters / histograms:

- `agent_inline_guard_cache_total{outcome=hit|miss|disabled|error}` counter
- `agent_inline_guard_cache_lookup_seconds` histogram
- `agent_inline_guard_cache_writeback_seconds` histogram (always observed even on success)

Add a small `/admin/analytics/guard-cache` endpoint mirroring the existing `/admin/analytics/guardrails` pattern in `backend/src/agent_service/api/admin_analytics/`. Surfaces:

- last-hour hit rate
- top-10 cache entries by hit count
- entries flagged by the reshadow loop in the last 24 h

Frontend can come later — the metrics in Grafana are enough for the v1 evaluation.

### Phase 5 — tests (~30 min)

New file `backend/tests/test_inline_guard_cache.py` (≥6 cases):

1. Cache disabled → classifier is called every time (existing behaviour preserved).
2. Cache miss → classifier called, result written back via `schedule()`, top-level decision matches what classifier returned.
3. Cache hit → classifier *not* called, decision returned from Milvus matches the cached payload.
4. Cache hit on a stale `model_version` → treated as miss, classifier called.
5. Cache hit on a stale `embedder_version` → treated as miss, classifier called.
6. Reshadow loop: when `_random.random()` is forced below `INLINE_GUARD_CACHE_RESHADOW_RATE`, the classifier is called even on a cache hit and a mismatch logs a warning.
7. Milvus error during lookup → fail-open, classifier called, no exception leaks.
8. Embedder error → same, fail-open.

Mock Milvus and the embedder (no live network in unit tests). Pattern matches existing mock approaches in `backend/tests/test_inline_guard.py`.

### Phase 6 — backfill + warm-up (one-time, post-deploy, ~15 min)

After the first deploy, run a backfill that prepopulates the cache from the last 30 days of `eval_traces` rows where `inline_guard_decision IS NOT NULL`:

- Script `backend/scripts/warmup_inline_guard_cache.py` — reads `eval_traces`, batches 200 rows at a time, embeds each prompt with the local embedder, upserts to Milvus.
- Idempotent (uses `content_hash` as natural key — re-runs are no-ops).
- Add `make warmup-inline-guard-cache` target.

Expected initial corpus size: ~few hundred entries (current `eval_traces` size is in that range). The cache is sized for tens of thousands; HNSW search stays sub-10 ms well past 100k entries.

## File map

| File | Change |
|---|---|
| `backend/src/agent_service/security/inline_guard.py` | wire `_lookup_cache` + cache write-back into `evaluate_prompt_safety_decision` |
| `backend/src/agent_service/security/local_embedder.py` | new — `LocalEmbedder` + `get_local_embedder()` |
| `backend/src/agent_service/security/inline_guard_cache.py` | new — Milvus read/write helpers + reshadow logic |
| `backend/src/common/milvus_mgr.py:84-106` | add `inline_guard_cache` to `MilvusManager._init_stores` |
| `backend/src/agent_service/core/config.py` | new env vars (`INLINE_GUARD_CACHE_ENABLED`, `_SIM_THRESHOLD`, `_TTL_SECONDS`, `_RESHADOW_RATE`, `LOCAL_EMBEDDER_MODEL`, `LOCAL_EMBEDDER_VERSION`) |
| `backend/src/agent_service/core/app_factory.py` | call `get_local_embedder().warm()` in lifespan if cache enabled |
| `backend/src/agent_service/api/admin_analytics/guard_cache.py` | new — `/admin/analytics/guard-cache` admin endpoint |
| `backend/scripts/rebuild_inline_guard_cache_collection.py` | new — drop-and-recreate the Milvus collection |
| `backend/scripts/warmup_inline_guard_cache.py` | new — one-shot backfill from `eval_traces` |
| `backend/Makefile` | add `rebuild-inline-guard-cache-collection`, `warmup-inline-guard-cache` |
| `backend/Dockerfile` | bake the MiniLM model at build time |
| `backend/pyproject.toml` | `+sentence-transformers`, `+torch` (CPU) |
| `backend/tests/test_inline_guard_cache.py` | new — 8 cases above |
| `backend/tests/test_local_embedder.py` | new — 3 cases (load, embed, warm) |

## Latency budget (justification)

Measured 2026-05-07 against the live agent container:

| Layer | Current p50 | Current p95 | After cache (hit) p50 | After cache (miss) p50 |
|---|---|---|---|---|
| Regex | 1 ms | 1 ms | 1 ms | 1 ms |
| Cache lookup (MiniLM + Milvus search) | n/a | n/a | **~15 ms** | ~15 ms |
| Groq Safeguard 120B classifier | ~500 ms | ~800 ms | (skipped) | ~500 ms |
| Cache write-back (off-path) | n/a | n/a | n/a | ~10 ms (fire-and-forget) |
| **Total user-facing** | ~501 ms | ~801 ms | **~16 ms** | ~516 ms |

For a 50 % hit rate, blended p50 lands around `(0.5 × 16) + (0.5 × 516) = 266 ms` — roughly halving median guard latency. p95 unchanged (cache misses dominate the tail). For a 70 % hit rate, blended p50 drops to `(0.7 × 16) + (0.3 × 516) = 166 ms`.

If cache hit rate < 30 % after 24 h of warm-up: keep `INLINE_GUARD_CACHE_ENABLED=false` and revisit. The cost of running the local embedder + Milvus on misses is negligible (~25 ms vs the ~800 ms classifier), but the win only materialises with hits.

## Verification

```bash
# 1. Local — full backend suite
cd backend && source .venv/bin/activate && uv run pytest tests/ -v

# 2. Targeted — new test files
uv run pytest tests/test_inline_guard_cache.py tests/test_local_embedder.py -v

# 3. Lint + deprecation gate
uv run ruff check . && PYTHONWARNINGS='error' uv run pytest tests/test_inline_guard_cache.py

# 4. Image build smoke (model pulls during build, not at run time)
cd .. && docker compose --env-file .env -f compose.yaml build agent
docker compose --env-file .env -f compose.yaml run --rm agent \
    python -c "from src.agent_service.security.local_embedder import get_local_embedder; \
               import asyncio; print(len(asyncio.run(get_local_embedder().aembed_query('test'))))"
# expect: 384

# 5. Latency probe inside the recreated container — re-run the script we used
#    in the original investigation, comparing OpenRouter vs local embedder.

# 6. Live — flip the flag in .env, restart agent, and curl the same recon prompt
#    twice in succession; second hit should land in <30 ms total.
echo 'INLINE_GUARD_CACHE_ENABLED=true' >> .env
docker compose --env-file .env -f compose.yaml up -d --no-deps --force-recreate agent
SID=$(curl -s -X POST https://mft-api.pruthvirajchavan.codes/agent/sessions/init \
        -H 'content-type: application/json' -d '{}' | jq -r '.session_id')
for i in 1 2; do
    time curl -N -sS -X POST https://mft-api.pruthvirajchavan.codes/agent/stream \
        -H 'content-type: application/json' \
        -d "{\"session_id\":\"$SID\",\"question\":\"what is my next emi date?\"}" \
        > /tmp/run_$i.txt
done
# Run 1: cache miss, ~500 ms guard latency.
# Run 2: cache hit on same prompt → ~15 ms guard latency reflected in trace.

# 7. Backfill run + admin dashboard check
make -C backend rebuild-inline-guard-cache-collection
make -C backend warmup-inline-guard-cache
# Then open /admin/analytics/guard-cache and confirm hit rate trends upward.
```

## Deploy

Backend-only. Mirror the PR #21/#22/#23 pattern:

```bash
gh pr merge <#> --squash --delete-branch
git checkout main && git pull
docker compose --env-file .env -f compose.yaml build agent shadow_judge_worker
docker compose --env-file .env -f compose.yaml up -d --no-deps --force-recreate agent shadow_judge_worker
```

The `INLINE_GUARD_CACHE_ENABLED` flag stays `false` for the first deploy. After 24 h of metric collection (mostly to verify the local embedder behaves under load and that warm-up landed entries) flip the flag and redeploy. This staged rollout means the merge can ship without behavioural risk.

## Rollback

Single env-var flip: `INLINE_GUARD_CACHE_ENABLED=false` → restart agent. Falls back to the current regex + classifier path. Code stays merged; collection stays in Milvus (zero cost when not queried).

## Out of scope

- Replacing the Groq Safeguard 120B classifier itself. The cache fronts it; the classifier is still authoritative on misses.
- Redis-keyed exact-match cache. Considered and rejected — vector cache covers the same hits and more (paraphrases) without a second cache to manage.
- A frontend dashboard for the admin surface beyond what Grafana provides on the metrics. Wire the React page later if the team wants UI-level observability.
- The OpenRouter embedder used for `kb_faqs` / `eval_traces_emb` — that stays on OpenRouter for the eval pipeline. The local embedder is *only* for the inline guard hot path.

## Risks

| Risk | Mitigation |
|---|---|
| MiniLM-L6-v2 produces poor near-neighbour clustering on adversarial prompts that the 120B classifier would otherwise catch (false-cache-hit on a malicious prompt similar to a benign cached one) | Reshadow loop catches mismatches and drops the entry; `INLINE_GUARD_CACHE_SIM_THRESHOLD` defaults to 0.93 (high — only near-duplicates hit); regex layer still runs first and hard-blocks the obvious cases without ever reaching the cache |
| `sentence-transformers` + `torch` add ~300 MB to the agent image | One-time cost; image rebuilds are cached past the first; agent image already carries similar weight from langchain. If image size becomes a real constraint, swap MiniLM for `intfloat/multilingual-e5-small` (~120 MB) which has comparable latency |
| Local embedder runs on agent CPU and competes with FastAPI worker threads | Run inside `loop.run_in_executor(None, ...)` so it goes onto the thread pool, not the event loop. Bench under realistic concurrency before flipping the flag |
| Cache write-backs blocked by Milvus pressure → tail latency on misses | Write-backs go through `schedule()` (fire-and-forget); response path doesn't await them. Worst case: write fails, log warning, classifier was already called and decision returned to user |
| `model_version` mismatch logic gets out of date and the cache silently grows stale | TTL (30 d default) bounds staleness; reshadow loop catches drift; rebuild script lets us nuke and re-warm in one command |
| Latency probe was done on a small `kb_faqs` collection — Milvus latency may rise modestly with the actual cache size | At 100k entries with HNSW + `ef=64`, search is still single-digit ms; we have ~3 orders of magnitude of headroom before this matters |

## Definition of done

1. `git status` shows: ~14 modified/new files (component + tests + scripts + Dockerfile + Makefile + pyproject.toml).
2. `pytest tests/` passes; new test count adds ≥ 11 cases.
3. `ruff check` clean; deprecation gate clean.
4. `docker compose build agent` succeeds and the smoke command from verification step 4 returns `384`.
5. PR opened mirroring the #21/#22/#23 pattern; CI passes both gates first try (or with the known flake re-run).
6. Post-deploy with flag *off*: agent serves the same SSE event vocabulary as before; `agent_inline_guard_cache_total{outcome="disabled"}` increments per request.
7. After 24 h with flag *on*: hit rate ≥ 30 % observed in Grafana; reshadow mismatch rate < 1 %.
8. Resume bullet is now true at runtime — `vector similarity caching` is in front of the GPT-OSS Safeguard 120B classifier and measurably reduces guard latency on hot prompts.
