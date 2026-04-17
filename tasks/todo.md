# Task Plan

## ✅ AUDIT REMEDIATION — COMPLETE (2026-04-17)

All 11 findings from the 2026-04-13 code review (security-reviewer + python-reviewer agents) are closed. The cutover is unblocked; `pre-phase-6-cutover` tag re-points to the post-remediation HEAD.

| # | Severity | Finding | Closed in |
|---|---|---|---|
| 1 | CRITICAL | JWT_ALGORITHM env-overridable (alg=none bypass) | `78862ae` |
| 2 | HIGH | rotate_refresh_token TOCTOU (WATCH/MULTI/EXEC) | `3ffce6c` |
| 3 | HIGH | _parse_refresh split('.') maxsplit=2 | `3ffce6c` |
| 4 | HIGH | mfa_verified_at int() coercion guard | `3ffce6c` |
| 5 | HIGH | Frontend CSRF STATE_CHANGING_METHODS missing PATCH | `c83a0d6` |
| 6 | MEDIUM | TOTP lockout counter race (WATCH/MULTI/EXEC) | `e1a20f9` |
| 7 | MEDIUM | Pytest startup-validation skip too blunt (env-var pivot) | `e1a20f9` |
| 8 | MEDIUM | MFA recovery runbook (endpoint deferred) | docs/runbooks/admin_auth_mfa_recovery.md |
| 10 | HIGH | pricing.py cached-token double-count (~3x overcharge) | `1026a6f` |
| 11 | HIGH | pricing.py reasoning-token double-count (2x on reasoning runs) | `1026a6f` |
| 17/18/19 | LOW | Convention cleanup on event_bus, http_client, follow_ups | `3660bd2` |

**Deferred (out of scope this cycle):**
- #9 (LOW) — `issued_at` storage in Redis hash: imprecise metadata, no security impact. Follow-up sprint.
- #8 (MFA reset endpoint) — needs its own threat model + RBAC. Runbook ships now; endpoint later.

**Baseline → post-remediation test counts:**
- Backend: 253 → 290 (+37 new tests across JWT alg, pricing, refresh TOCTOU, parse hardening, claim guards, TOTP race)
- Frontend: 129 → 130 (+1 PATCH CSRF test)

**Rollback:** `git reset --hard pre-phase-6-cutover` reverts to the post-remediation HEAD (not the pre-remediation state). If a hard rollback is needed back to the pre-review state, use `git reset --hard e3bc64e` (the `fix: recover 4 core modules previously hidden by .gitignore bug` commit).

---

## 📌 TOMORROW — PICKUP PLAN (2026-04-12)

**Read this section first.** Everything below in this file is historical context. Use `CLAUDE.md` for project structure, `tasks/lessons.md` for accumulated gotchas, and the Phase 6 + M1 sections below for execution history.

### Where we left off (2026-04-11 evening)

**Code state**: Phases 0–6h of the admin auth plan COMPLETE and validated. Phase M1 (MCP semantic search tool) COMPLETE and validated. All 4 backend gates green (253 tests), all 4 frontend gates green (129 tests).

**Runtime state**: STALE. The running `agent-local` and `mcp-local` containers still have the pre-Phase-6 code in memory. On-disk code is new. Admin console in a browser is 401'd because the frontend no longer sends `X-Admin-Key` but the running backend still expects it (legacy path in the memory-loaded process, even though on-disk code has the legacy path deleted).

**Outstanding**: (A) user ops cutover to make the running processes match the on-disk code, (B) Phase 7 (docs + MFA modal wiring) not yet started.

---

### Step 0 — PRE-CUTOVER SNAPSHOT (already taken 2026-04-11 evening — reference only)

Before restarting any container tomorrow, confirm the pre-cutover snapshot from 2026-04-11 still exists. It is the fast-rollback path if the cutover breaks the runtime. Covers all three app-tier containers (agent, mcp, frontend). Infra containers (redis, postgres, milvus*) are NOT snapshotted — their state lives in named volumes and is unaffected by the cutover.

- **Snapshot location (host):** `snapshots/2026-04-11T17-52-52Z/` (gitignored, ~377 MB)
- **Snapshot metadata + rollback recipe:** `snapshots/2026-04-11T17-52-52Z/SNAPSHOT_INFO.md`
- **Snapshot images (Docker):**
  - `mft_agent:snapshot-2026-04-11T17-52-52Z`         → `sha256:59b62d5285ca…`
  - `mft_mcp:snapshot-2026-04-11T17-52-52Z`           → `sha256:efe13d76a350…`
  - `mft_frontend_prod:snapshot-2026-04-11T17-52-52Z` → `sha256:4cee1f3f389b…`

Sanity-check before Step 1:

```bash
# All three must print a sha256 line — if any errors, the snapshot has been
# GC'd and you MUST re-snapshot the pre-cutover containers BEFORE proceeding.
docker image inspect mft_agent:snapshot-2026-04-11T17-52-52Z         --format '{{.Id}}'
docker image inspect mft_mcp:snapshot-2026-04-11T17-52-52Z           --format '{{.Id}}'
docker image inspect mft_frontend_prod:snapshot-2026-04-11T17-52-52Z --format '{{.Id}}'
ls -la /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent/snapshots/2026-04-11T17-52-52Z/SNAPSHOT_INFO.md
```

**Rollback path** (only if Step 1 cutover breaks and the fastest recovery is to revert the runtime):

```bash
docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local \
    stop agent-local mcp-local frontend-prod
docker tag mft_agent:snapshot-2026-04-11T17-52-52Z         mft_agent:latest
docker tag mft_mcp:snapshot-2026-04-11T17-52-52Z           mft_mcp:latest
docker tag mft_frontend_prod:snapshot-2026-04-11T17-52-52Z mft_frontend_prod:latest
docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local \
    up -d agent-local mcp-local frontend-prod
```

**Partial rollback is supported** — re-tag and restart only the tier that's broken. A mixed state (new backend + old frontend) will show 401/403 in the admin console but won't corrupt data, because the admin-auth contract is backend-driven and the frontend just renders what the backend allows.

Note: volumes (Redis / Postgres / Milvus data) are NOT captured in the snapshot — they persist across restarts in named volumes regardless. The snapshot only protects the Python `/app` tree, the built frontend `/usr/share/nginx/html` tree, and the image filesystem state.

**Keep the snapshot until:** the cutover has been stable for at least one week AND `fix/final-audit-remediation` has been merged + tagged.

### Step 1 — OPS CUTOVER (user, ~5–10 minutes, MUST run first)

**Pre-flight**: Step 0 snapshot verified. Ensure `docker compose` local stack is up: `make local-up` from `backend/`. Tag the rollback anchor: `git tag pre-phase-6-cutover HEAD`.

```bash
# 1. Enrollment — generates 5 env vars + TOTP provisioning URI
cd /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent/backend
source .venv/bin/activate
python scripts/enroll_super_admin.py
# Walk through the interactive prompts:
#   - email (any real-shape string)
#   - password (12+ chars, entered twice)
# Register the emitted otpauth:// URI in your authenticator app
# (or enter the raw base32 secret manually).

# 2. Paste the emitted env var block into backend/.env
# The 5 vars are: JWT_SECRET, FERNET_MASTER_KEY, SUPER_ADMIN_EMAIL,
# SUPER_ADMIN_PASSWORD_HASH, SUPER_ADMIN_TOTP_SECRET_ENC.
# ADMIN_AUTH_ENABLED is NOT needed — the flag was deleted in Phase 6h;
# JWT enforcement is now unconditional at the code level.
vim backend/.env   # or your editor of choice

# 3. Restart BOTH backend containers — agent-local (FastAPI) and mcp-local (FastMCP)
#    so they pick up the new code AND the new env vars.
cd /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent
docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local \
    restart agent-local mcp-local

# Watch logs for ~5 seconds to confirm clean boot (no validator errors)
docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local \
    logs --tail 30 agent-local mcp-local
```

**If agent-local refuses to boot**, the error will name a missing env var (`_validate_admin_auth_config` fail-fast). Re-check step 2 output vs `backend/.env`.

**If enrollment script fails**, `pyotp` / `argon2-cffi` / `cryptography.fernet` are already installed in the backend venv from Phase 0 — if imports fail, run `make install-dev` and retry.

### Step 2 — BROWSER VERIFICATION (user, ~2 minutes)

1. Open `http://localhost:<agent-local-port>/admin/login` in a browser
2. Enter the email + password from enrollment
3. Enter the 6-digit TOTP code from your authenticator app when prompted
4. Verify you land on `/admin` dashboard (should render without errors)
5. Navigate to a few admin pages (Knowledge Base, Guardrails, Traces) to confirm API calls work
6. Test a READ on KB (browse FAQs) — should work
7. Test a MUTATION on KB (add/edit/delete an FAQ) — will return 403 `mfa_required` with a plain error toast because the MFA prompt modal isn't wired yet. **Expected** until Phase 7a ships.

### Step 3 — Report status to me (tomorrow's agent session)

Once steps 1–2 are complete, tell the agent: **"ops cutover done, start Phase 7"** (or just "proceed"). If anything breaks in step 2, paste the browser error or container log and we'll diagnose.

**Rollback path** (if step 2 reveals a showstopper): `git reset --hard pre-phase-6-cutover && docker compose ... restart agent-local mcp-local`. Zero dataloss.

---

### Step 4 — Phase 7a: MFA prompt modal wiring (agent, ~5 files, ~1 hour)

**Why this matters**: post-cutover, KB mutations return 403 `mfa_required` when the JWT is MFA-stale (>5 min since last TOTP verify). The user sees a plain toast error and has to manually navigate to re-verify. Phase 7a wires the `MfaChallenge` component from Phase 5a into a proper modal that intercepts 403s and retries the failed mutation.

**Files (5, within §2 budget)**:

1. **`src/features/admin/auth/MfaPromptProvider.tsx`** (NEW, ~80 lines)
   - React context holding modal state (`isOpen`, `actionLabel`, `resolver`)
   - `promptMfa(actionLabel: string): Promise<void>` — shows modal, resolves on verify success, rejects on cancel
   - Renders `<MfaChallenge>` wrapped in shadcn `<Dialog>` when `isOpen`
   - Listens for a global `admin:mfa-required` CustomEvent (dispatched from http.ts) and auto-opens itself

2. **`src/shared/api/http.ts`** (modify, ~10 lines)
   - On 403 with `detail.code === "mfa_required"` (non-auth paths), dispatch `admin:mfa-required` CustomEvent
   - Keep existing 401 dispatch for `admin:session-expired`

3. **`src/features/admin/auth/useMfaPrompt.ts`** (NEW, ~30 lines)
   - Hook that returns `{ withMfa: <T>(label: string, fn: () => Promise<T>) => Promise<T> }`
   - Wraps any async operation: tries it, on 403 `mfa_required` calls `promptMfa(label)` then retries once

4. **`src/features/admin/knowledge-base/KnowledgeBasePage.tsx`** (modify, wrap 3 mutations)
   - Wrap `deleteFaq`, `clearAllFaqs`, `updateFaq`, `ingestFaqBatch`, `ingestFaqPdf` calls via `withMfa("Delete FAQ")`, etc.
   - Each mutation becomes: `await withMfa("Save FAQ", () => updateFaq({...}))`

5. **`tests/admin/auth/MfaPromptProvider.test.tsx`** (NEW, ~8 tests)
   - `promptMfa` resolves on verify success, rejects on cancel
   - Global event listener auto-opens modal
   - `withMfa` retry-on-403-mfa-required flow
   - No retry on non-mfa errors
   - Cancel path rejects the original promise
   - Successive mutations share the same provider instance

6. **`src/features/admin/layout/AdminLayout.tsx`** (modify, 1 line)
   - Wrap `<AdminShell />` in `<MfaPromptProvider>` inside the `<AuthGuard>` tree

**Total real file count: 6** — slightly over the 5-file budget, but Phase 7a is cohesive (can't split the provider from its consumers cleanly). Consider approving a small §2 override OR splitting into 7a-infra (provider + http.ts + tests = 3 files) and 7a-consume (KB page + layout = 2 files).

**Validation plan**:
```bash
cd "Chatbot UI and Admin Console"
npm run typecheck              # expect: clean
npm run test                   # expect: 137 passed (129 + 8 new)
npm run build                  # expect: clean
npm run verify:deprecation     # expect: 137 passed, zero warnings
```

**Manual test** (requires ops cutover done): trigger a KB mutation with stale MFA, observe modal, enter TOTP, verify mutation succeeds on retry.

**Clarifying questions for tomorrow**:
- **Q1**: Use shadcn `<Dialog>` or `<AlertDialog>` for the modal shell? (AlertDialog is semantically stronger for "you must do this to continue" but Dialog is the common pattern.)
- **Q2**: `withMfa` retry count — retry once (my default) or allow multiple retries with exponential backoff?
- **Q3**: On cancel, should the original mutation promise reject with a specific `MfaCancelled` error type or just a generic Error? (Cleaner error handling at call sites with typed errors.)
- **Q4**: Phase 7a file split — approve the 6-file override OR split into 7a-infra + 7a-consume?

### Step 5 — Phase 7b: Documentation (agent, ~4 files, ~30 min)

Pure markdown. Low-risk, no validation gates beyond eyeball review.

1. **`CLAUDE.md`** (modify) — update §5 gotchas to reflect post-cutover auth model. Remove any remaining `X-Admin-Key` references. Add a note about the 5-minute MFA freshness window.

2. **`.cursor/rules/admin-auth.mdc`** (NEW) — cursor rule documenting:
   - When to use `require_admin` / `require_super_admin` / `require_mfa_fresh`
   - CSRF double-submit requirement on state-changing endpoints (pattern from `admin_auth_routes.py`)
   - Cookie flag conventions (`httpOnly`, `Secure`, `SameSite=Strict`, path restrictions)
   - `MfaPromptProvider` usage convention for mutation pages (references the Phase 7a file)
   - Enrollment flow pointer (`backend/scripts/enroll_super_admin.py`)

3. **`backend/README.md`** (modify) — new "Admin authentication" section explaining:
   - JWT session cookie is the only auth path
   - 5 required env vars and where they come from (enrollment script)
   - Rate limits (5 req/min login + mfa/verify per-IP)
   - Test scaffolding for admin endpoints (HTTP-level via `httpx.ASGITransport`)

4. **`docs/operations/super-admin-enrollment.md`** (NEW) — ops runbook:
   - "3 AM on-call" format: copy-paste commands, no narrative
   - Sections: Prerequisites, Enrollment, Env setup, Container restart, Browser verification, Rollback, Troubleshooting (common errors + fixes)
   - References the enrollment script but explains what each env var does

### Step 6 — Phase M1 follow-up (agent, 1 file, ~10 min)

**Agent system prompt hint for `search_knowledge_base`** — flagged in Phase M1 residual risks. The LangGraph agent auto-discovers the tool, but a hint in the system prompt about "prefer search_knowledge_base for product/policy questions" would improve selection quality. Needs a quick look at `agent_service/core/app_factory.py` or wherever the system prompt is assembled, then a one-line addition.

Not blocking on Phase 7a/7b. Can slot in anywhere tomorrow.

---

### Follow-up items (NOT tomorrow, tracked for visibility)

- **WAHA API key rotation** — parked per user instruction during Phase 6 planning. Standing item for pre-production.
- **E2E browser test coverage for admin auth flow** — no Playwright tests exist for login → MFA → mutation → logout. Unit tests cover each piece; end-to-end flow is untested in a real browser. Not blocking; queue for a future test sub-phase.
- **Tool description tuning for `search_knowledge_base`** — the "When to use / When NOT to use" language is my best guess at LLM tool-selection behavior. First real chat conversations after mcp-local restart will reveal whether the agent under-uses or over-uses the tool. Iterate empirically.
- **Consolidate dev-dep dual system** — `backend/pyproject.toml` `[dependency-groups] dev` vs `requirements-dev.txt` — see `tasks/lessons.md` L2. A plain `uv sync` prunes packages that `make install-dev` adds. Pre-existing; not part of any admin auth phase; flagged for a small standalone cleanup.
- **Phase 5c test debt was retired** for Phase 5 components. No outstanding test debt for Phases 0–6h or M1. Phase 7a adds its own test file inline.

### What a fresh agent session needs to load before executing

1. Read **`CLAUDE.md`** (project structure, stack, commands, gotchas)
2. Read **`tasks/lessons.md`** (7 accumulated lessons L1–L7; most relevant for Phase 7a: L4 about httpx cookie-jar gotchas and L5 about per-request cookies deprecation)
3. Read **this section** (Tomorrow — Pickup Plan) for the execution order
4. Read the **Phase 6 + M1 history** below for context on what was built
5. Check **`git log --oneline -20`** to see the commit trail from this session
6. Check **`git status`** to see if any changes are uncommitted from this session

**Do NOT re-read** the full Phase 0–6 execution history unless the user asks. The summary at each sub-phase header has everything needed.

---

## 2026-04-10 — Admin & Super-Admin Auth Policy (PHASES 0-5 DONE — PHASE 6 RESTRUCTURED, AWAITING EXECUTION APPROVAL FOR 6a-ADDITIVE)

**Status:** Phases 6a–6h CODE COMPLETE (deferred-restart path). Frontend (27 files) cleaned, backend legacy deleted, all 4 gates green on both stacks. Awaiting user ops steps (enroll → env vars → ONE restart → browser login) before the admin console becomes usable.

### Phase 6b–6h results (2026-04-11) — deferred-restart chained execution per Option A

**User approved Option A**: chain 6b → 6h continuously, skip per-sub-phase validation, run full gate at the end. Each sub-phase committed for review granularity; verification ran once at 6h end.

#### Files touched (30 total)

**Phase 6b — API batch 1 (5 files)**
- `src/features/admin/api/faqs.ts` — removed `adminKey` param from 8 exported functions; added `credentials: 'include'` + `Content-Type` inline to the 2 SSE calls (`streamSse` doesn't default to credentials-include)
- `src/features/admin/api/guardrails.ts` — removed `adminKey` param from 5 functions
- `src/features/admin/api/feedback.ts` — removed `adminKey` param from 2 functions (createFeedback is public, unchanged)
- `src/features/admin/api/admin.faqs.test.ts` — removed `withAdminHeaders` mock, updated 7 tests to match new signatures
- `src/features/admin/api/admin.guardrails.test.ts` — removed `withAdminHeaders` mock, updated 1 test

**Phase 6c — API batch 2 + hooks (5 files)**
- `src/features/admin/api/sessions.ts` — removed `adminKey` from 3 admin-gated functions
- `src/features/admin/api/traces.ts` — removed `adminKey` from 10 functions (biggest API file)
- `src/features/admin/query/queryOptions.ts` — removed `adminKey` from 10 query option factories (30 adminKey occurrences gone)
- `src/features/admin/hooks/useConversationQueries.ts` — removed `adminKey` param from hook + 4 internal query calls
- `src/features/admin/hooks/useLiveGlobalFeed.ts` — removed `adminKey` param entirely; added `credentials: 'include'` to `fetchEventSource` init

**Phase 6d — Pages batch 1 (5 files)**
- `src/features/admin/knowledge-base/KnowledgeBasePage.tsx` — removed `useAdminContext` + 10 adminKey call sites
- `src/features/admin/guardrails/GuardrailsPage.tsx` — removed `useAdminContext` + 6 adminKey call sites
- `src/features/admin/guardrails/GuardrailsPage.test.tsx` — removed `useAdminContextMock` + all fixture references
- `src/features/admin/pages/Dashboard.tsx` — removed `useAdminContext` + 6 adminKey call sites
- `src/features/admin/pages/Conversations.tsx` — removed `useAdminContext` + `adminKey` param from `useConversationQueries`

**Phase 6e — Pages batch 2 (4 files, ModelConfig.tsx was a false positive)**
- `src/features/admin/pages/Conversations.test.tsx` — removed `useAdminContext` mock + updated fetchSessionTraces assertions (2 args → 1 arg)
- `src/features/admin/pages/Feedback.tsx` — removed `useAdminContext` + 4 adminKey call sites
- `src/features/admin/pages/QuestionCategories.tsx` — removed `useAdminContext` + 2 adminKey call sites
- `src/features/admin/pages/UsersAnalytics.tsx` — removed `useAdminContext` + 2 adminKey call sites
- **`ModelConfig.tsx`** — **NOT TOUCHED**: initial grep was a false positive; `useAdminContext` stays for BYOK provider keys (openrouterKey/nvidiaKey/groqKey)

**Phase 6f — Traces batch (5 files)**
- `src/features/admin/pages/ModelConfig.test.tsx` — removed `adminKey` from the `defaultAdminContext` fixture (BYOK-only now)
- `src/features/admin/traces/ChatTracesPage.tsx` — removed `useAdminContext` + `adminKey` from `tracesPageInfiniteQueryOptions` param
- `src/features/admin/traces/ChatTracesPage.test.tsx` — removed `useAdminContext` mock
- `src/features/admin/traces/MetricsDashboard.tsx` — removed `useAdminContext` + 4 adminKey call sites
- `src/features/admin/traces/SemanticSearchUI.tsx` — removed `useAdminContext` + 2 adminKey call sites (including the `fetchVectorSearch` payload field)

**Phase 6g — Final frontend cleanup (6 files, 1 unplanned due to AuthGuard legacy branch removal)**
- `src/features/admin/traces/trace-viewer/GlobalTraceSheet.tsx` — removed `useAdminContext` + `adminKey` from queryKey and fetchAdminTrace call
- `src/features/admin/traces/trace-viewer/GlobalTraceSheet.test.tsx` — removed `useAdminContext` mock
- `src/features/admin/layout/AdminLayout.tsx` — AuthGuard simplified to session-only (no legacy key branch); KeyInput popover admin-key row deleted; `missingAdminKey` dead variable deleted; `AlertCircle` import cleaned up; `useLiveGlobalFeed` call now takes no args; popover renamed "API Keys" → "Provider Keys"
- `src/features/admin/context/AdminContext.tsx` — **`adminKey` field DELETED** from `AdminContextValue`; `nbfc_admin_key` removed from `STORAGE`; one-time migration useEffect still deletes any stale localStorage entry on mount
- `src/shared/api/http.ts` — **`withAdminHeaders()` function DELETED**
- `src/features/admin/auth/AdminAuthProvider.test.tsx` (unplanned) — removed 1 obsolete AuthGuard test ("passes through when legacy adminKey is non-empty") and the `useAdminContextMock` infrastructure; updated remaining AuthGuard tests to session-only expectations. Phase 5c's `{adminKey: ...}` mock setups were deleted because the AuthGuard no longer reads AdminContext.

**Phase 6h — Backend legacy deletion (3 files)**
- `backend/src/agent_service/api/admin_auth.py` — **`require_admin_key` DELETED**; legacy X-Admin-Key fallback branches removed from `require_admin` / `require_super_admin` / `require_mfa_fresh`; all 3 dependencies now JWT-only. File shrunk from 194 → 110 lines. Removed `Header`, `hmac`, `Optional`, `ADMIN_API_KEY`, `ADMIN_AUTH_ENABLED` imports.
- `backend/src/agent_service/core/config.py` — **`ADMIN_API_KEY` and `ADMIN_AUTH_ENABLED` DELETED**; `_validate_admin_auth_config()` simplified to unconditionally require JWT env vars. Test-context escape hatch: validator skips when `"pytest" in sys.modules` so test imports don't fail when env vars are absent.
- `backend/tests/test_admin_auth_dependencies.py` — deleted 7 legacy-mode tests (`test_require_admin_legacy_*`, `test_require_admin_key_uses_hmac_compare_digest`); added 2 new tests (`test_require_super_admin_accepts_super_admin_role`, `test_require_mfa_fresh_rejects_null_mfa`); all remaining tests use JWT cookie path only.

#### Final validation gate (end of 6h)

**Backend:**
- `make lint` → ruff clean + mypy clean on 8-file strict set
- `pytest tests/ -q` → **241 passed in 13.98s** (246 → 241, net −5: −7 legacy + 2 new)
- `PYTHONWARNINGS='error::Deprecation*' pytest tests/ -q` → **241 passed in 14.77s**, zero warnings

**Frontend:**
- `npm run typecheck` → clean (after 1 mid-run fix for a dangling `useAdminContextMock.mockReset()` call)
- `npm run test` → **129 passed in 36.37s** (130 → 129, −1 obsolete legacy-adminKey AuthGuard test)
- `npm run build` → clean production bundle, 1.62s
- `npm run verify:deprecation` → test + build under `--throw-deprecation`, zero warnings

#### Final state

- **Legacy code: ZERO references** to `adminKey`, `useAdminContext().adminKey`, `withAdminHeaders`, `X-Admin-Key`, `require_admin_key`, `ADMIN_API_KEY`, `ADMIN_AUTH_ENABLED` anywhere in the admin auth path. Historical comments in `AdminContext.tsx` and `guardrails.ts` explain the retirement.
- **Backend code path**: `require_admin` / `require_super_admin` / `require_mfa_fresh` are JWT-only, no fallback
- **Frontend API layer**: all 27 admin consumers send requests via `requestJson` (cookie-backed) or `streamSse` / `fetchEventSource` with `credentials: 'include'`
- **AuthGuard**: session-only, redirects to `/admin/login` when `session === null`
- **AdminContext**: BYOK provider keys only (openrouter/nvidia/groq), with one-time `nbfc_admin_key` localStorage cleanup on mount
- **Backend startup**: `_validate_admin_auth_config()` will HARD FAIL app boot if any of `JWT_SECRET`, `FERNET_MASTER_KEY`, `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD_HASH`, `SUPER_ADMIN_TOTP_SECRET_ENC` are missing from the environment — EXCEPT when running under pytest (sys.modules check).

#### Cumulative test count

| Phase | Backend | Frontend |
|---|---|---|
| Phase 5c end | 246 | 130 |
| Phase 6a-additive end | 246 | 130 |
| **Phase 6h end** | **241** | **129** |

Net test delta for Phase 6: −5 backend / −1 frontend. All deletions are legacy-branch coverage that no longer applies.

#### Phase 6 deviations from the sub-plan

1. **6a-additive scope** reduced from 4 files to 2 files after realizing flipping `ADMIN_AUTH_ENABLED` default-in-code would break the test suite at import time. Correct interpretation: flip the flag via `.env` (ops-level), not code.
2. **6e scope** reduced from 5 files to 4 files after discovering `ModelConfig.tsx` was a false-positive in the initial grep — `useAdminContext` is used there but only for BYOK provider keys, not `adminKey`.
3. **6g scope** grew from 5 files to 6 files: needed to update `AdminAuthProvider.test.tsx` to delete the obsolete AuthGuard legacy-adminKey test when the AuthGuard itself lost the legacy branch.
4. **6h scope** reduced from 5 files to 3 files: the `backend/.env.example` no longer had `ADMIN_API_KEY=` to delete (the key was never in the example file, only in code), and the cursor rule `.cursor/rules/admin-auth.mdc` was deferred to Phase 7 documentation.
5. **sys.modules check in config validator**: needed to add `if "pytest" in sys.modules: return` because the validator now runs unconditionally at module load. Without this, the test suite can't import `core.config` when env vars aren't set. Captured as a minor lesson.

### 🛠 YOUR REMAINING OPS STEPS (the deferred restart)

All code is merged. The admin console is currently 401'd in a browser because the running backend process still has the old code loaded but there's no JWT cookie path active. To complete the cutover:

1. **Run the enrollment script** interactively:
   ```bash
   cd /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent/backend
   source .venv/bin/activate
   python scripts/enroll_super_admin.py
   ```
   Enter a real email + password (12+ chars). Register the TOTP URI in your authenticator app.
2. **Paste the emitted env block** into your `backend/.env` file (or create it if it doesn't exist). The block includes:
   - `JWT_SECRET`
   - `FERNET_MASTER_KEY`
   - `SUPER_ADMIN_EMAIL`
   - `SUPER_ADMIN_PASSWORD_HASH`
   - `SUPER_ADMIN_TOTP_SECRET_ENC`
   - ~~`ADMIN_AUTH_ENABLED=true`~~ (not needed — flag was deleted in Phase 6h; JWT enforcement is now unconditional)
3. **Restart the backend container** so `config.py` picks up the new env vars. On first restart, the validator will either succeed (env vars present) or fail hard with a clear message pointing at the enrollment script.
4. **Open `/admin/login`** in a browser, sign in with your email + password.
5. **Enter the TOTP code** from your authenticator app when prompted.
6. **Verify the admin dashboard loads** and you can navigate to Knowledge Base, Guardrails, etc.
7. **Test a KB mutation** (add/edit/delete an FAQ) — should return 403 mfa_required the first time with a stale JWT, then succeed after MFA re-verify. Phase 7 will wire the proper MFA modal prompt; for now mutations return a plain 403 that the frontend surfaces as a toast error.

#### Rollback (if the ops cutover breaks anything)

- **Fastest**: `git reset --hard <pre-phase-6a-commit>` — reverts every Phase 6 code change, restart backend
- **Specific**: `git revert <phase-6h-commit>` — keeps 6a–6g frontend cleanup but restores the backend legacy fallback (you'd need to also revert 6b–6g for the frontend to actually use X-Admin-Key again)
- **No runtime toggle anymore** — the `ADMIN_AUTH_ENABLED` flag was deleted in 6h, so the only rollback path is git

---

**Original Phase 6a-additive results (kept for historical trace):**

### Phase 6a-additive results (2026-04-11)

**Delta from the sub-plan**: scope reduced from 4 files to **2 files** after realizing that flipping `ADMIN_AUTH_ENABLED` code default to `true` would break the test suite at import time (the validator runs on module load before any test fixture can monkeypatch the env). Solution: keep code default `false`; the enrollment script emits `ADMIN_AUTH_ENABLED=true` in its env var block so the user sets the flag via `.env` (ops-level flip, not code-level). The kill switch still works both directions.

- [x] **`backend/scripts/enroll_super_admin.py`** (NEW, ~210 lines) — fully standalone interactive CLI. Uses direct `secrets` / `pyotp` / `argon2.PasswordHasher` / `cryptography.fernet.Fernet` calls — does NOT import `config.py` or `admin_crypto.py` (avoids the config-validator chicken-and-egg when env vars aren't set yet). Prompts for email (regex-validated) + password (getpass, 12-char minimum, confirmation). Generates JWT_SECRET (43-char urlsafe, 43 bytes UTF-8 > 32-byte minimum), FERNET_MASTER_KEY (Fernet.generate_key), argon2id password hash (RFC 9106 low-memory default), pyotp base32 TOTP secret, Fernet-encrypted TOTP ciphertext. **Self-verifies** all 5 values via inline round-trip (JWT length, Fernet encrypt/decrypt, argon2 verify, encrypted TOTP decrypt match, pyotp.TOTP.now() + verify). Prints provisioning URI + raw base32 secret + env var block. Never writes to a file — user pastes into `.env` manually.
- [x] **`.env.example`** (repo root, modify) — replaced outdated "leave false until Phase 6 cutover" guidance with a pointer at `backend/scripts/enroll_super_admin.py` and clarified that `ADMIN_AUTH_ENABLED` is now the runtime kill switch. Manual fallback commands for JWT_SECRET / FERNET_MASTER_KEY generation retained as alternatives.

### What did NOT change in Phase 6a-additive

- `backend/src/agent_service/core/config.py` — **unchanged**. `ADMIN_AUTH_ENABLED` default stays `false` in code; flip happens via `.env`.
- `backend/src/agent_service/api/admin_auth.py` — **unchanged**. `require_admin_key`, legacy fallback branches, and dual-run semantics fully preserved.
- `backend/tests/test_admin_auth_dependencies.py` — **unchanged**. All 15 dependency tests (7 legacy-mode + 8 new-mode) continue to pass.
- No frontend changes.

### Smoke test evidence

Ran the enrollment script non-interactively via piped stdin (`printf 'admin@example.com\\npassword\\npassword\\n' | python scripts/enroll_super_admin.py`). Output shows:
- Self-verification passed on all 5 values
- Valid provisioning URI emitted (`otpauth://totp/mft-agent-admin:...`)
- Well-formed env var block with `ADMIN_AUTH_ENABLED=true` + 5 generated values
- Operator instructions for next steps

### Phase 6a-additive validation

- [x] **Backend `make lint`** → ruff clean + mypy clean on 8-file strict set
- [x] **Targeted mypy on `scripts/enroll_super_admin.py`** → "Success: no issues found in 1 source file"
- [x] **Full backend suite** → `pytest tests/ -q` → **246 passed in 14.81s** (unchanged, as expected)
- [x] **Deprecation gate** → `PYTHONWARNINGS='error::Deprecation*' pytest tests/ -q` → **246 passed in 15.03s**, zero warnings

### Files touched summary (Phase 6a-additive)

| File | Status | Line delta |
|---|---|---|
| `backend/scripts/enroll_super_admin.py` | NEW | +210 |
| `.env.example` | modified | +6 / −10 (rewritten admin auth section) |

**2 files**, well under the 5-file budget per `AGENTS.md` §2.

### Cumulative test count

| Phase | Backend | Frontend |
|---|---|---|
| Phase 5c end | 246 | 130 |
| **Phase 6a-additive end** | **246** | **130** |

Unchanged — this sub-phase adds scaffolding, not code-behavior or tests.

### What's next — YOUR ops steps before Phase 6b

**Do these in your environment before replying "proceed" for Phase 6b:**

1. **Tag the pre-cutover commit** (optional but recommended):
   ```bash
   git tag pre-phase-6b HEAD
   ```
2. **Run the enrollment script** interactively:
   ```bash
   cd /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent/backend
   source .venv/bin/activate
   python scripts/enroll_super_admin.py
   ```
   Enter a real email + password (12+ chars). Register the TOTP URI in your authenticator app (Google Authenticator, Authy, 1Password, etc.) — either scan a QR from the URI or enter the raw base32 secret manually.
3. **Paste the env block** into `backend/.env` (or create it from `.env.example` if it doesn't exist).
4. **Restart the backend** so `config.py` picks up the new env vars. With `ADMIN_AUTH_ENABLED=true`, the validator will require all 5 values at import time — if any are missing, the app refuses to boot with a clear error.
5. **Open `/admin/login` in a browser** and sign in with your email + password.
6. **Enter your TOTP code** when the MFA prompt appears.
7. **Verify the admin dashboard loads** via the JWT cookie path.
8. **If any step fails**: flip `ADMIN_AUTH_ENABLED=false` in `.env` and restart. Legacy code path is fully preserved — admin console reverts to X-Admin-Key behavior instantly.

Once you've completed steps 1-7 successfully, reply **"continue to 6b"** (or **"proceed"**) and I'll start the frontend API layer cleanup batch 1.

---

**Original Phase 6 strategy (approved):**

### Phase 6 — revised structure (2026-04-11, approved)

**Rationale for split**: the original Phase 6a atomic-delete was irreversible beyond `git revert`. The revised structure keeps the legacy `ADMIN_AUTH_ENABLED` flag, `require_admin_key` function, and legacy fallback branches alive-but-dormant during 6a–6g, enabling runtime rollback via flag toggle (`ADMIN_AUTH_ENABLED=false` + restart) without redeploy. Phase 6h then deletes the legacy code AFTER 6b–6g verify the JWT path works end-to-end across all 27 frontend consumers.

**Trade-off accepted**: +1 sub-phase, +4 files net, ~6 sub-phases of dead-code duration. Bought: runtime rollback across the entire cutover window.

### Phase 6 — sub-phase breakdown (revised)

| Sub-phase | Scope | Files | Runtime rollback | Deletes legacy? |
|---|---|---|---|---|
| **6a** | Backend **additive** + enrollment script | 4 | flag toggle | No |
| 6b | Frontend API batch 1 | 5 | flag toggle | No |
| 6c | Frontend API batch 2 + hooks | 5 | flag toggle | No |
| 6d | Frontend pages batch 1 (KB, Guardrails, Dashboard, Conversations) | 5 | flag toggle | No |
| 6e | Frontend pages batch 2 (Feedback, QC, Users, ModelConfig + tests) | 5 | flag toggle | No |
| 6f | Frontend traces batch | 5 | flag toggle | No |
| 6g | Final frontend cleanup (AdminContext.adminKey field removal, AdminLayout, http.ts) | ≤5 | flag toggle | No |
| **6h** | **Backend legacy deletion — point of no return** | 5 | git revert only | **Yes** |

**Total: 8 sub-phases, ~36 files, ~35 lines of net code deletion.**

### Phase 6a-additive scope (4 files, no deletions)

1. **`backend/scripts/enroll_super_admin.py`** (NEW) — interactive CLI; generates JWT_SECRET, FERNET_MASTER_KEY, argon2id password hash, TOTP secret, otpauth URI + QR code; self-verifies via round-trip; prints env var block
2. **`backend/src/agent_service/core/config.py`** — flip `ADMIN_AUTH_ENABLED` default to `true`; update `_validate_admin_auth_config()` to validate JWT env vars when flag is true. **KEEP** `ADMIN_API_KEY` constant; **KEEP** `ADMIN_AUTH_ENABLED` flag
3. **`backend/.env.example`** (repo root) — add enrollment script reference. **KEEP** `ADMIN_API_KEY=` line with a comment marking it as Phase 6h deletion
4. **`backend/src/agent_service/api/admin_auth.py`** — **UNCHANGED**. `require_admin_key` stays, legacy fallback branches stay, dual-run behavior fully preserved. Runtime behavior switches only via the `ADMIN_AUTH_ENABLED=true` default

### Phase 6h-deletive scope (5 files, executes AFTER 6b-6g verified green)

1. `backend/src/agent_service/api/admin_auth.py` — delete `require_admin_key`, delete legacy fallback branches, simplify to JWT-only
2. `backend/src/agent_service/core/config.py` — delete `ADMIN_API_KEY` constant, delete `ADMIN_AUTH_ENABLED` flag, simplify validator
3. `backend/tests/test_admin_auth_dependencies.py` — delete 7 legacy-mode tests (backend: 246 → 239)
4. `backend/.env.example` — delete `ADMIN_API_KEY=` line
5. `.cursor/rules/admin-auth.mdc` (NEW) — post-cutover auth convention document

**6h is the single point of no return.** Executed only after 6b-6g prove the JWT path works across every frontend consumer in a real browser.

### Runtime rollback (6a through 6g)

1. Edit `backend/.env`: set `ADMIN_AUTH_ENABLED=false`
2. Restart backend
3. Backend reverts to legacy X-Admin-Key behavior; frontend's preserved `withAdminHeaders(adminKey)` calls still work
4. Zero redeploy, zero git revert

### Ops prerequisites for Phase 6a-additive

1. ~~Rotate WAHA API key~~ — PARKED per user instruction (dev environment)
2. **Tag the pre-6a commit**: `git tag pre-phase-6a HEAD` (belt-and-braces checkout anchor)
3. **Note rollback SHA**: `git rev-parse HEAD` — noted in personal terminal scrollback
4. **Terminal ready** to run `uv run python backend/scripts/enroll_super_admin.py` locally after 6a commit lands

### Ops steps between 6a and 6b

After 6a deploys:
1. Run `uv run python backend/scripts/enroll_super_admin.py` locally (or in dev env)
2. Script generates + prints env vars — paste into `.env`
3. Restart backend
4. Open browser → `/admin/login`
5. Sign in with enrolled credentials
6. Verify admin dashboard loads via JWT cookie
7. Reply "continue to 6b" to proceed

**Between deploys, runtime kill switch remains active**: if anything breaks, `ADMIN_AUTH_ENABLED=false` reverts to legacy behavior instantly.

---

**Status:** Phase 6 structure revised and approved. Waiting for explicit "proceed" to begin Phase 6a-additive execution.

### Phase 5c results (2026-04-11) — test debt retirement

- [x] **`src/features/admin/layout/AdminLayout.tsx`** (modify, 1-line edit) — added `export` to the `AuthGuard` function declaration so tests can import it directly from the module.
- [x] **`src/features/admin/auth/AdminAuthProvider.test.tsx`** (NEW, ~280 lines, **13 tests**) — provider tests (9): session hydration from `/me`, 401-is-silent, non-401 is error, login round-trip, login failure, logout clears session, logout swallows server error, verifyMfa refreshes session, useAdminAuth throws outside provider. Plus AuthGuard tests (4): renders null while loading, redirects to `/admin/login` when no session/no adminKey, passes through with JWT session, passes through with legacy adminKey (dual-run). Uses `vi.hoisted()` to avoid the classic Vitest `vi.mock()` top-level-reference gotcha.
- [x] **`src/features/admin/auth/LoginPage.test.tsx`** (NEW, ~130 lines, **6 tests**) — renders inputs + autocomplete attributes, disabled-when-empty, happy path login → navigate('/admin', {replace: true}), local error rendering on throw, provider-level error rendering, submitting state transitions.
- [x] **`src/features/admin/auth/MfaChallenge.test.tsx`** (NEW, ~135 lines, **8 tests**) — input inputMode/autocomplete/maxLength, non-digit stripping + 6-char cap, verify-button-disabled-until-6-digits, success path calls verifyMfa + onVerified, failure renders error without calling onVerified, cancel calls onCancel, actionLabel appears in prompt text, generic prompt fallback.
- [x] **`src/shared/api/http.test.ts`** (NEW, ~155 lines, **11 tests**) — credentials=include on every request, no X-CSRF on GET, injected X-CSRF on POST/PUT/DELETE, omitted when no cookie, parsed JSON body on 200, ApiError throw on 500, ApiError instance check, ADMIN_SESSION_EXPIRED_EVENT dispatch on 401 for non-auth paths, NO dispatch for /admin/auth/* paths (avoid loops), URL construction via API_BASE_URL.

### Phase 5c deviations from the sub-plan

1. **Test count**: **38 actual** vs 31 planned (+7). Pattern continues from prior phases — I tend to split edge cases into dedicated tests rather than combine them.
2. **Vitest hoisting gotcha**: first run of `AdminAuthProvider.test.tsx` failed with "Cannot access 'TestApiError' before initialization" because `vi.mock()` is hoisted above the class declaration. Fixed using `vi.hoisted()` factory to declare the class + mock in the hoisted slot. Captured as potential `lessons.md` candidate.
3. **Unhandled rejection in test consumer**: `AdminAuthProvider.login()` and `verifyMfa()` re-throw errors after setting error state (correct production pattern). The test consumer's click handler used `void login(...)` which ignored the re-throw, leaking into a Vitest unhandled-rejection warning. Fixed by wrapping in a local `safeLogin()` / `safeVerifyMfa()` that try/catches the rethrow. Caught on second run.
4. **TypeScript generic on `vi.fn()`**: Vitest v4 requires explicit generic `vi.fn<() => void>()` when the mock is assigned to a typed prop (e.g., `MfaChallengeProps.onVerified`). Default `vi.fn()` returns a broader mock type that TypeScript rejects. Surfaced during `npm run typecheck` after tests were passing.

### Files touched summary (Phase 5c)

| File | Status | Line delta | Tests |
|---|---|---|---|
| `src/features/admin/layout/AdminLayout.tsx` | modify | 1 (export) | — |
| `src/features/admin/auth/AdminAuthProvider.test.tsx` | NEW | +280 | 13 |
| `src/features/admin/auth/LoginPage.test.tsx` | NEW | +130 | 6 |
| `src/features/admin/auth/MfaChallenge.test.tsx` | NEW | +135 | 8 |
| `src/shared/api/http.test.ts` | NEW | +155 | 11 |

5 files exactly at the 5-file phase budget. **38 new tests.**

### Phase 5c validation

- [x] `npm run typecheck` → clean (after Vitest generic fix)
- [x] `npm run test` → **130 passed** (was 92, +38 new)
- [x] `npm run build` → clean production bundle in 1.87s
- [x] `npm run verify:deprecation` → 130 passed + clean build under `--throw-deprecation`, zero warnings

### Cumulative test count

| Phase | Backend | Frontend |
|---|---|---|
| Phase 4d end | 246 | 92 |
| Phase 5a end | 246 | 92 |
| Phase 5b end | 246 | 92 |
| Phase 5c end | 246 | **130** |

### Phase 5 test debt: RETIRED

All 7 Phase 5 components now have dedicated coverage:
- ✅ `AdminAuthProvider` — 9 tests
- ✅ `AuthGuard` (AdminLayout.tsx) — 4 tests
- ✅ `LoginPage` — 6 tests
- ✅ `MfaChallenge` — 8 tests
- ✅ `http.ts` CSRF injection + session-expired event — 11 tests
- ⚪ `AdminLoginRoute` — not dedicated (thin wrapper, transitively covered by LoginPage tests)
- ⚪ Session-expired listener in `AdminShell` — not dedicated (covered indirectly via http.ts event dispatch test)

### What's next: Phase 6 CUTOVER — POINT OF NO RETURN

All Phase 6 prerequisites:
1. ⚠️ **WAHA API key rotation** — still outstanding from session-start security incident
2. ⚠️ **Super-admin env var generation** — via Phase 6a's enrollment script (delivered in 6a commit)
3. ⚠️ **Rollback SHA noted** — write down the current HEAD before 6a deploys
4. ⚠️ **First browser login** — between 6a deploy and 6b deploy, you MUST log into `/admin/login` to get a JWT cookie, else 6b breaks the admin console

Phase 6 splits into **7 sub-phases** (6a through 6g) per the prior plan. Phase 6a is the backend cutover + enrollment script (irreversible once deployed). Phases 6b-6g are incremental frontend cleanup (can be paused between).

Reply **"proceed"** to start **Phase 6a** (requires the 4 prerequisites above), or corrections.

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### Phase 5b results (2026-04-11) — route guards + layout integration

- [x] **`Chatbot UI and Admin Console/src/features/admin/auth/AdminLoginRoute.tsx`** (NEW, ~10 lines) — wrapper that mounts `LoginPage` inside its own `AdminAuthProvider`, so the login route is self-contained and doesn't depend on `AdminLayout`'s provider (which is gated behind the guard).
- [x] **`src/app/routes.ts`** (modify, +6 lines) — added lazy-loaded `AdminLoginRoute` import, registered `/admin/login` as a top-level sibling route BEFORE `/admin` so it matches first. The login route does NOT go through `AdminLayout`, avoiding a guard-redirect loop.
- [x] **`src/features/admin/layout/AdminLayout.tsx`** (modify, ~+50 lines) — introduced `AuthGuard` component with **dual-run semantics**: passes if either `session` (JWT) OR `adminKey` (legacy, non-empty) is present, otherwise `<Navigate to="/admin/login" replace />`. Returns `null` while `isLoading === true` to prevent flash-of-redirect. Added `AdminAuthProvider` as the outermost wrap in `AdminLayout`'s export (above `AdminProvider`). Wired a `ADMIN_SESSION_EXPIRED_EVENT` listener in `AdminShell` that calls `refreshSession()` on 401 dispatch — if the refresh confirms the session is gone, the next render of `AuthGuard` routes to `/admin/login`. Replaced the "Exit Admin" button with a dual-mode button: calls `logout()` before navigating when the user has a JWT session, preserves "Exit Admin" behavior otherwise. Label switches between "Sign out" and "Exit Admin" based on session state.

### Phase 5b dual-run semantics (critical)

The `AuthGuard` is deliberately permissive during dual-run:

```typescript
const hasJwtSession = session !== null;
const hasLegacyKey = Boolean(adminKey && adminKey.trim());
if (!hasJwtSession && !hasLegacyKey) {
  return <Navigate to="/admin/login" replace />;
}
```

**Why**: During dual-run (`ADMIN_AUTH_ENABLED=False`), the backend's `require_admin` still accepts the legacy `X-Admin-Key` header. Users who already have a pasted adminKey continue to access the dashboard exactly as today — no forced login, no regression. Users WITHOUT either credential now see the new `LoginPage` (previously they'd see the dashboard with API errors), which is an improvement even during dual-run.

**Post-Phase 6 cutover**: the `hasLegacyKey` branch is deleted from the guard, leaving only `session !== null`. The `AdminContext` `adminKey` field is deleted entirely, along with all `useAdminContext().adminKey` call sites across the admin pages (11+ files).

### Files touched summary (Phase 5b)

| File | Status | Line delta |
|---|---|---|
| `src/features/admin/auth/AdminLoginRoute.tsx` | NEW | +20 |
| `src/app/routes.ts` | modified | +6 |
| `src/features/admin/layout/AdminLayout.tsx` | modified | +50 |

**3 files**, well within the 5-file phase budget per `AGENTS.md` §2.

### Phase 5b deviation from the sub-plan

**MFA mutation wrapping was NOT done in Phase 5b.** The main plan said to "wrap mutation calls with `requireMfa` helper that triggers the MFA modal on 403" across multiple admin page files (KB, Guardrails, etc.). This was deferred because:

1. During dual-run, the backend's `require_mfa_fresh` is a no-op (legacy mode has no MFA concept), so the wrapper would never actually trigger.
2. Wrapping mutations across 3-4 page files would push Phase 5b past the 5-file budget.
3. The natural time to add MFA wrapping is Phase 6 cutover, when those pages are touched anyway to remove legacy `adminKey` references.

**Phase 6 will need to add MFA mutation wrapping** as part of its cutover scope. I'll document this as a Phase 6 sub-task.

### Phase 5b validation

- [x] `npm run typecheck` → clean
- [x] `npm run test` → **92/92 passed** (23 test files, unchanged)
- [x] `npm run build` → clean production bundle, 1.69s
- [x] `npm run verify:deprecation` → 92/92 tests + clean build, zero deprecation warnings
- [x] **Backend sanity check** — `pytest tests/ -q` → 246/246 passed (no cross-stack regressions)

### Cumulative state after Phase 5

| Phase | Backend tests | Frontend tests |
|---|---|---|
| Phase 4d end | 246 | 92 |
| Phase 5a end | 246 | 92 (no new) |
| Phase 5b end | 246 | 92 (no new) |

**Frontend test debt from Phase 5**: 0 new tests for the 7 new source files/components added across 5a+5b (AdminAuthProvider, LoginPage, MfaChallenge, AdminLoginRoute, http.ts CSRF injection, AuthGuard, session-expired wiring). Recommended: Phase 5c dedicated test sub-phase before Phase 6 cutover, OR add tests inline during Phase 6 when files are touched anyway.

### Phase 5 total (5a + 5b)

| Sub-phase | Files | New tests |
|---|---|---|
| 5a | 4 (3 new source + 1 modified http.ts) | 0 |
| 5b | 3 (1 new + 2 modified) | 0 |
| **Phase 5 total** | **7** | **0** |

### What's next: Phase 6 (feature flag cutover) — POINT OF NO RETURN

This is the irreversible phase. Per main plan §5 Phase 6 scope:

1. **Flip `ADMIN_AUTH_ENABLED=True`** in all environment files (`.env`, `.env.local`, `.env.uat`, `.env.prod`)
2. **Enroll the super-admin** — run a Phase 7 enrollment script to generate argon2id password hash + Fernet-encrypted TOTP secret, seed `SUPER_ADMIN_*` env vars
3. **Delete the legacy auth path** — remove `require_admin_key`, remove `AdminContext.adminKey` field, remove `withAdminHeaders(adminKey)` call sites in 11+ frontend files, remove `AuthGuard`'s legacy-key branch
4. **Add MFA mutation wrapping** on KB/Guardrails pages (deferred from 5b)
5. **Staging dual-run validation** (per plan §6): 24-hour coexistence in staging before flipping production
6. **Production cutover**
7. **Rollback plan**: feature flag `ADMIN_AUTH_ENABLED=False` immediately reverts to legacy behavior without redeployment

**Pre-Phase-6 prerequisites** (you must confirm):
1. **WAHA API key rotation** — still outstanding from the prior security incident. **MUST be done before Phase 6.**
2. **Phase 5c frontend tests** — recommended to have coverage on the new auth components BEFORE cutover, OR accept the test debt for the post-cutover world.
3. **Super-admin enrollment script (Phase 7)** — Phase 6 cannot flip `ADMIN_AUTH_ENABLED=True` without the `SUPER_ADMIN_PASSWORD_HASH` + `SUPER_ADMIN_TOTP_SECRET_ENC` env vars being set. Either run Phase 7 before Phase 6, or split Phase 6 into "landing code" + "ops cutover".
4. **Staging environment** — is staging provisioned for the 24-hour dual-run validation? If not, that step is either skipped (higher risk) or deferred until staging is ready.

Given the irreversibility, I **strongly recommend `/plan phase 6`** before proceeding. Phase 6 touches ~15 files (flag flip + legacy deletion + MFA wrapping + enrollment docs), spans backend + frontend + ops, and has no practical rollback beyond the feature flag.

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### Phase 5a results (2026-04-11) — frontend auth context + login page + MFA modal

- [x] **`Chatbot UI and Admin Console/src/features/admin/auth/AdminAuthProvider.tsx`** (NEW, ~155 lines) — React context for JWT-cookie-backed admin sessions. Exposes `session`, `isLoading`, `error`, `login(email, password)`, `logout()`, `verifyMfa(code)`, `refreshSession()`. On mount, calls `GET /admin/auth/me` to hydrate from the httpOnly cookie — 401 is treated as "no session" (silent), anything else sets `error`. `useAdminAuth()` hook throws if called outside the provider.
- [x] **`src/features/admin/auth/LoginPage.tsx`** (NEW, ~115 lines) — email/password form with Tailwind styling, accessible labels, disabled state during submit, inline error rendering, auto-complete hints (`email`, `current-password`), navigates to `/admin` on success. Shows both local submission errors and provider-level errors.
- [x] **`src/features/admin/auth/MfaChallenge.tsx`** (NEW, ~115 lines) — TOTP code modal component. 6-digit numeric input with `autocomplete="one-time-code"`, center-aligned monospace display, strict `pattern="[0-9]{6}"` validation, `onVerified` / `onCancel` callbacks, `actionLabel` prop for context-specific framing. Does NOT render its own modal shell — parent wraps it in a Dialog/AlertDialog primitive.
- [x] **`src/shared/api/http.ts`** (modify, +~50 lines) — `requestJson` now sends `credentials: 'include'` so cookies flow with every request; CSRF double-submit header (`X-CSRF-Token` read from the `mft_admin_csrf` cookie) is injected on every POST/PUT/DELETE; on 401 responses (except for `/admin/auth/*` endpoints themselves, which would loop), dispatches an `admin:session-expired` CustomEvent that AdminAuthProvider or Phase 5b route guards can listen for. `withAdminHeaders()` legacy helper is preserved unchanged for dual-run.
- [x] **Frontend validation complete**: `npm run typecheck` clean, `npm run test` 92/92 passing, `npm run build` clean, `npm run verify:deprecation` passes with zero deprecation warnings.

### Phase 5a critical deviation — scope correction mid-execution

**The main plan (2026-04-10) said Phase 5a would "retire `nbfc_admin_key` from localStorage" in `AdminContext.tsx`. This was wrong and I caught it mid-execution.** Removing `adminKey` from the `AdminContextValue` interface broke 11+ files across the admin console:

- `features/admin/knowledge-base/KnowledgeBasePage.tsx`
- `features/admin/layout/AdminLayout.tsx` (2 call sites)
- `features/admin/pages/{Conversations,Dashboard,Feedback,QuestionCategories,UsersAnalytics}.tsx`
- `features/admin/traces/{ChatTracesPage,MetricsDashboard,SemanticSearchUI}.tsx`
- `features/admin/traces/trace-viewer/GlobalTraceSheet.tsx`

Each of these reads `adminKey` via `useAdminContext()` and passes it to `withAdminHeaders(adminKey)` to send `X-Admin-Key` on API calls. Since the backend is running under dual-run (`ADMIN_AUTH_ENABLED=False`), `require_admin` still REQUIRES the X-Admin-Key header. Retiring the frontend state would 401-lock the admin console immediately.

**Correction**: `AdminContext.tsx` is now UNCHANGED in Phase 5a — `adminKey` stays fully functional. A prominent comment documents that this field is scheduled for Phase 6 retirement alongside the backend feature flag flip. Retirement happens atomically with the cutover so that both the backend switch to JWT-cookie enforcement AND the frontend switch to using only AdminAuthProvider land in the same commit.

**Updated Phase 5a scope**: 4 source files (3 new + 1 modify of `http.ts`), not 5. Main plan had a scoping error that I corrected in place. The 5-file budget is not exceeded; Phase 5a is under budget.

### Files touched summary (Phase 5a)

| File | Status | Line delta |
|---|---|---|
| `src/features/admin/auth/AdminAuthProvider.tsx` | NEW | +155 |
| `src/features/admin/auth/LoginPage.tsx` | NEW | +115 |
| `src/features/admin/auth/MfaChallenge.tsx` | NEW | +115 |
| `src/shared/api/http.ts` | modified | +~50 (CSRF + credentials + 401 event) |
| `src/features/admin/context/AdminContext.tsx` | **unchanged** (correction) | 0 |

**4 source files**, well within the 5-file phase budget per `AGENTS.md` §2.

### Phase 5a validation

- [x] `npm run typecheck` → clean (after AdminContext revert — initial run caught 29 type errors across 11 files, corrected in-phase)
- [x] `npm run test` → **92 passed** (23 test files — unchanged, existing tests still green)
- [x] `npm run build` → clean production bundle in 1.65s
- [x] `npm run verify:deprecation` → test + build under `--throw-deprecation`, 92/92 passed, zero warnings

### Cumulative test count

| Phase | New tests (backend) | New tests (frontend) | Cumulative backend | Cumulative frontend |
|---|---|---|---|---|
| Phase 4d end | — | — | 246 | 92 |
| Phase 5a end | 0 | 0 | 246 | 92 |

**No new tests in Phase 5a** — the frontend auth components were written without co-located `.test.tsx` files to stay within the 5-file phase budget. The existing 92 tests continue passing. Test debt is noted below and scheduled for a Phase 5c follow-up OR added alongside route guards in Phase 5b.

### Phase 5a test debt (scheduled for later sub-phase)

No automated tests exist yet for:
1. `AdminAuthProvider` mount / hydration / login / logout / verifyMfa
2. `LoginPage` form submission + error rendering
3. `MfaChallenge` code validation + submit flow
4. `http.ts` CSRF header injection + 401 event dispatch

These should be covered by Vitest + React Testing Library. Recommended split: co-located `.test.tsx` files, ~4 test files, ~30 test cases. Estimated 1 sub-phase of work. I'll propose a Phase 5c after 5b completes OR merge tests into 5b if the file budget allows.

### What's next: Phase 5b (route guards + mutation MFA wrapper)

Per main plan:
- `src/app/routes.ts` — add route guards on `/admin/*` routes
- `src/features/admin/layout/AdminLayout.tsx` — consume `AdminAuthProvider`, redirect to `/admin/login` if not authenticated
- Admin page files with mutation UIs (KB, Guardrails) — wrap mutations with MFA prompt helper
- Exact file count determined after reading routes.ts and AdminLayout.tsx

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### Phase 4d results (2026-04-11) — rate limiter wiring

- [x] **`backend/src/agent_service/core/config.py`** (modify, +3 lines) — added `RATE_LIMIT_ADMIN_AUTH_LOGIN_RPS` and `RATE_LIMIT_ADMIN_AUTH_MFA_RPS` constants, default 0.083 rps ≈ 5 req/min, env-overridable.
- [x] **`backend/src/agent_service/core/rate_limiter_manager.py`** (modify, +18 lines) — imported the 2 new constants and added `get_admin_auth_login_limiter()` + `get_admin_auth_mfa_limiter()` factory methods following the existing `_get_limiter("endpoint:<name>", ...)` pattern.
- [x] **`backend/src/agent_service/api/endpoints/admin_auth_routes.py`** (modify, +~40 lines) — imported `enforce_rate_limit` + `get_rate_limiter_manager`; added `_client_ip_from_request(request)` helper using the project's canonical pattern (`request.state.client_ip` → `request.client.host` → `"unknown"` fallback); wired rate limit calls at the top of both `login` and `mfa_verify` handlers before any business logic; added `request: Request` parameter to `login` signature.
- [x] **`backend/tests/test_admin_auth_endpoints.py`** (modify, +27 lines) — added rate limiter stub to the `test_env` fixture: `_StubLimiter`, `_StubManager`, `_noop_enforce`, monkeypatch `get_rate_limiter_manager` and `enforce_rate_limit` on the admin_auth_routes module. Required to prevent `Event loop is closed` errors from the production `RateLimiterManager` singleton caching Redis clients across test event loops.

### Phase 4d deviation

**One unplanned file edit**: `test_admin_auth_endpoints.py` was touched (not in the 3-file sub-plan list). The stub was required to keep the existing 19 integration tests green — without it, 8 tests failed with `Event loop is closed` from the rate limiter's cached Redis client. This is exactly the risk I flagged in D19 residual risks ("rate limiter integration requires test stubs to avoid singleton leakage") and in the Phase 4d sub-plan ("rate limit tests are flaky with fakeredis"). The fix is a test-side stub, not an automated rate limit test.

Phase 4d file count: **4** (3 source + 1 test fixture update). Still within the 5-file phase budget per `AGENTS.md` §2.

### Files touched summary (Phase 4d)

| File | Status | Line delta |
|---|---|---|
| `backend/src/agent_service/core/config.py` | modified | +5 (2 constants + 3 comment lines) |
| `backend/src/agent_service/core/rate_limiter_manager.py` | modified | +18 (2 factory methods + import) |
| `backend/src/agent_service/api/endpoints/admin_auth_routes.py` | modified | +40 (IP helper + 2 rate limit calls + imports) |
| `backend/tests/test_admin_auth_endpoints.py` | modified | +27 (rate limiter stub in test_env fixture) |

### Phase 4d validation

- [x] `make lint` → ruff clean + mypy clean on 8-file strict set
- [x] `pytest tests/ -q` → **246 passed in 14.31s**
- [x] `PYTHONWARNINGS='error::Deprecation*' pytest tests/ -q` → **246 passed in 14.23s** (zero warnings)

### Phase 4 TOTAL (4a + 4b + 4c + 4d)

| Sub-phase | Files | New tests | Cumulative tests |
|---|---|---|---|
| 4a | 5 | +15 | 246 |
| 4b | 5 | 0 | 246 |
| 4c | 3 | 0 | 246 |
| 4d | 4 | 0 | 246 |
| **Phase 4 total** | **17** | **+15** | **246** |

**All 12 migration-target files cleaned**. `require_admin_key` survives only in `admin_auth.py` (its definition, to be deleted in Phase 6) and `test_admin_auth_dependencies.py` (tests that verify the legacy function still works during dual-run).

**Rate limiter wired on `/admin/auth/login` + `/admin/auth/mfa/verify`** — per-IP, 5 req/min fail-closed. D9 (deferred rate limit) closed.

**Security improvements deferred until Phase 6 cutover**: the new role-aware dependencies all fall back to `X-Admin-Key` when `ADMIN_AUTH_ENABLED=False`. Post-cutover, the real JWT-based enforcement activates.

### What's next: Phase 5 (frontend migration)

Per main plan, Phase 5 splits into 5a/5b:
- **5a**: Frontend auth context + login page + MFA modal (5 files)
- **5b**: Route guards on admin pages + mutation-MFA prompt wrapper (≤5 files)

Phase 5 is the last phase before the cutover (Phase 6). It builds the UX that consumes the auth endpoints landed in Phase 3. Recommended: **`/plan phase 5`** because it touches the React + TypeScript + Tailwind + TanStack Query + React Router v7 stack in `Chatbot UI and Admin Console/`, which I've only briefly surveyed.

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### Phase 4c results (2026-04-11) — admin.py read/write split + eval routers

- [x] **`backend/src/agent_service/api/admin.py`** (modify, largest per-handler rewiring of Phase 4) — removed router-level `dependencies=[Depends(require_admin_key)]`, added 9 per-handler dependency decorators:
  - **2 READ handlers → `Depends(require_admin)`**: `GET /agent/admin/faqs`, `GET /agent/admin/faq-categories`
  - **7 MUTATION handlers → `Depends(require_mfa_fresh)`** (chains through require_super_admin → require_admin): `POST /faqs/semantic-search` (defaulted to mutation per D14 fallback since user didn't answer), `POST /faqs/batch-json`, `POST /faqs/upload-pdf`, `PUT /faqs`, `DELETE /faqs`, `DELETE /faqs/all`, `POST /faqs/semantic-delete`
  - **Post-edit audit**: `grep -c Depends(require_admin)` = 2, `grep -c Depends(require_mfa_fresh)` = 7, `grep -c require_admin_key` = 0, handler count = 9. All counts match.
- [x] **`backend/src/agent_service/api/eval_read.py`** — 2 occurrences swapped (import + router-level dependency)
- [x] **`backend/src/agent_service/api/eval_live.py`** — 2 occurrences swapped (import + per-handler dependency on the 1 admin-gated handler)
- [x] **Repo-wide audit**: `grep -l require_admin_key` across `backend/` returns ONLY 2 files (`admin_auth.py`, `test_admin_auth_dependencies.py`) — both intentional. All 12 migration-target files are clean.
- [x] **`make lint` green** — ruff clean + mypy clean on 8-file strict set
- [x] **Full test suite green** — `pytest tests/ -q` → **246 passed in 14.46s** (unchanged)
- [x] **Deprecation gate green** — `PYTHONWARNINGS='error::Deprecation*' pytest tests/ -q` → **246 passed in 14.75s** (zero warnings)

### Phase 4c D14 resolution

**`POST /agent/admin/faqs/semantic-search` defaulted to MUTATION** (under `require_mfa_fresh`) because user did not answer the clarifying question before Phase 4c execution. The Explore agent originally classified it as mutation, and the safer default is to require MFA. If this turns out to be a read-only vector query, it can be downgraded to `require_admin` in a later patch without a migration — just a single-line dependency change in admin.py.

**Implication post-cutover**: super-admins invoking semantic-search will be prompted for TOTP every 5 minutes. This is acceptable for a rarely-invoked endpoint. If the frontend uses it on every KB page load, the UX cost is higher and the classification should be revisited.

### Files touched summary (Phase 4c)

| File | Status | Change |
|---|---|---|
| `backend/src/agent_service/api/admin.py` | modified | Removed router-level dep; added 9 per-handler deps (2 require_admin, 7 require_mfa_fresh) |
| `backend/src/agent_service/api/eval_read.py` | modified | 2 replacements (import + router dep) |
| `backend/src/agent_service/api/eval_live.py` | modified | 2 replacements (import + per-handler dep) |

3 files, under the 5-file phase budget per `AGENTS.md` §2.

### Phase 4 migration status (overall)

| Phase | Files migrated | Running total |
|---|---|---|
| 4a | 3 (overview, conversations, traces) | 3 / 12 |
| 4b | 5 (guardrails, feedback, sessions, live_dashboards, rate_limit_metrics) | 8 / 12 |
| 4c | 3 (admin, eval_read, eval_live) | **11 / 12** |

**12 files** total was the Explore agent's count, but admin_auth.py is where `require_admin_key` LIVES (it's not a target of migration, it's the source). So migration-target count is actually **11 files**, all done. The 12th file is `admin_auth.py` itself, which is retired in Phase 6 (not migrated — deleted).

### Cumulative test count (unchanged since Phase 4a)

| Phase | New tests | Cumulative |
|---|---|---|
| Phase 4a end | — | 246 |
| Phase 4b end | +0 | 246 |
| Phase 4c end | +0 | 246 |

### What's next: Phase 4d (3 files — rate limiter wiring)

Per the sub-plan:
1. `backend/src/agent_service/core/config.py` — add 2 RPS constants (RATE_LIMIT_ADMIN_AUTH_LOGIN_RPS, RATE_LIMIT_ADMIN_AUTH_MFA_RPS)
2. `backend/src/agent_service/core/rate_limiter_manager.py` — add 2 limiter factory methods
3. `backend/src/agent_service/api/endpoints/admin_auth_routes.py` — wire `enforce_rate_limit` on `/login` and `/mfa/verify`

Per-IP identifier, 5 req/min fail-closed (D17/D18). No new automated tests (D19 — rate limit tests are flaky with fakeredis; manual verification only).

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### Phase 4b results (2026-04-11) — second analytics batch + non-admin routers

- [x] **`backend/src/agent_service/api/admin_analytics/guardrails.py`** — router-level swap (import + `dependencies=[Depends(require_admin)]`)
- [x] **`backend/src/agent_service/api/feedback.py`** — 3 occurrences: 1 import + 2 per-handler `_: None = Depends(require_admin)` on `GET /agent/admin/feedback` and `GET /agent/admin/feedback/summary`
- [x] **`backend/src/agent_service/api/endpoints/sessions.py`** — 4 occurrences: 1 import + 3 per-handler `_admin: None = Depends(require_admin)` on `GET /sessions`, `GET /sessions/summary`, `DELETE /sessions/cleanup`
- [x] **`backend/src/agent_service/api/endpoints/live_dashboards.py`** — 2 occurrences: 1 import + `@router.get("/global", dependencies=[Depends(require_admin)])`
- [x] **`backend/src/agent_service/api/endpoints/rate_limit_metrics.py`** — 2 occurrences: 1 import + per-handler `_admin: None = Depends(require_admin)` on `POST /rate-limit/reset/{identifier}`
- [x] **Residual audit**: `grep -l require_admin_key` on all 5 files returns nothing (exit 1) — full replacement verified
- [x] **HTTP-test risk check**: `grep -l "TestClient\|AsyncClient"` across `backend/tests/` returns only `test_admin_auth_endpoints.py` (my Phase 3b file). The 5 migrated routers have no HTTP-level integration tests that could break.
- [x] **`make lint` green** — ruff clean + mypy clean on 8-file strict set
- [x] **Full test suite green** — `pytest tests/ -q` → **246 passed in 14.47s** (unchanged from Phase 4a end)
- [x] **Deprecation gate green** — `PYTHONWARNINGS='error::Deprecation*' pytest tests/ -q` → **246 passed in 14.18s** (zero warnings)

### Phase 4b deviations from the sub-plan

None. Phase 4b was straightforward mechanical swaps — 5 files, identical name-to-name replacement per file, `replace_all=True` with an unambiguous target string, zero new tests.

### Files touched summary (Phase 4b)

| File | Status | `require_admin_key` → `require_admin` occurrences |
|---|---|---|
| `admin_analytics/guardrails.py` | modified | 2 (import + router dep) |
| `api/feedback.py` | modified | 3 (import + 2 handlers) |
| `api/endpoints/sessions.py` | modified | 4 (import + 3 handlers) |
| `api/endpoints/live_dashboards.py` | modified | 2 (import + 1 decorator dep) |
| `api/endpoints/rate_limit_metrics.py` | modified | 2 (import + 1 handler) |

**13 total replacements across 5 files.** Each file at the 5-file phase budget per `AGENTS.md` §2.

### Cumulative test count (unchanged)

| Phase | New tests | Cumulative |
|---|---|---|
| Phase 4a end | — | 246 |
| Phase 4b end | +0 | 246 |

### What's next: Phase 4c (3 files)

Per the sub-plan:
1. **`backend/src/agent_service/api/admin.py`** — per-handler rewiring. **Critical** because it's the ONE file where the dependency must differ per handler: 2 GET handlers get `Depends(require_admin)`, 7 mutation handlers get `Depends(require_mfa_fresh)`. Router-level dependency must be REMOVED and replaced with per-handler.
2. **`backend/src/agent_service/api/eval_read.py`** — 2 occurrences swap to `require_admin`
3. **`backend/src/agent_service/api/eval_live.py`** — 2 occurrences swap to `require_admin`

**Unresolved D14**: Is `POST /agent/admin/faqs/semantic-search` a READ (vector query, no state change) or a MUTATION? I recommended READ. Need your answer before executing 4c — if it's a MUTATION, it gets `require_mfa_fresh` and can't be fired from an MFA-less admin session post-cutover.

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### Phase 4a results (2026-04-11) — core dependencies + first analytics batch

- [x] **`backend/src/agent_service/api/admin_auth.py`** (modify, 25 → 194 lines) — added 3 new dependencies alongside the existing `require_admin_key`: `require_admin`, `require_super_admin`, `require_mfa_fresh`. Each dependency chains via FastAPI `Depends` for correct caching. Dual-run semantics: `ADMIN_AUTH_ENABLED=False` falls back to `X-Admin-Key` legacy path; `ADMIN_AUTH_ENABLED=True` enforces JWT cookie + role + MFA checks. **Pre-existing security fix**: `require_admin_key` upgraded from `!=` to `hmac.compare_digest` for timing-safe comparison.
- [x] **`backend/tests/test_admin_auth_dependencies.py`** (NEW, ~260 lines, **15 tests**) — legacy mode (7 tests): valid key/missing/wrong/503/super_admin-grants-on-key/mfa-skips/hmac-spy; new mode (8 tests): valid cookie/missing/expired/tampered/missing-role/super-admin-rejects-admin-only/mfa-rejects-stale/mfa-accepts-fresh. Mock `Request` objects, direct dependency calls.
- [x] **`backend/src/agent_service/api/admin_analytics/overview.py`** (modify) — swapped `Depends(require_admin_key)` → `Depends(require_admin)` on router dependencies + import.
- [x] **`backend/src/agent_service/api/admin_analytics/conversations.py`** (modify) — same swap.
- [x] **`backend/src/agent_service/api/admin_analytics/traces.py`** (modify) — same swap.
- [x] **`make lint` green** — ruff clean + mypy clean on 8-file strict set (admin_auth.py not yet in strict set — deferred to Phase 7 docs)
- [x] **Full test suite green** — `pytest tests/ -q` → **246 passed in 14.86s** (231 from Phase 3b + 15 new)
- [x] **Deprecation gate green** — `PYTHONWARNINGS='error::Deprecation*' pytest tests/ -q` → **246 passed in 14.49s** (zero warnings)

### Phase 4a key finding

**Existing admin contract tests call handler functions directly** (`await admin.get_faqs(...)`, `await admin_analytics.overview(...)`) rather than going through the HTTP layer via `TestClient`/`AsyncClient`. FastAPI's dependency injection is never invoked in these tests, so swapping `require_admin_key` → `require_admin` has **zero impact** on them. The dual-run fallback is strictly needed for the production path, not the test suite.

This means the residual risk I flagged in the Phase 4 plan — "existing tests might break under the new dependency" — is moot. Direct-call tests are architecturally decoupled from the auth layer. Migration continues without the feared test churn.

### Phase 4a deviations from the sub-plan

1. **Test count**: 15 actual (exactly as planned in sub-plan).
2. **`admin_auth.py` not added to mypy strict set**: the file now has 4 dependency functions with complex dual-run logic. Technically should be in strict set; I deferred adding it because doing so in Phase 4a would push the file count to 6, over the §2 budget of 5. Scheduled for Phase 7 (documentation phase) or a dedicated follow-up task.
3. **`require_admin_key` gets the `hmac.compare_digest` upgrade per D15** — approved as a pre-existing security fix, landed in the same commit as the new dependencies to keep the `admin_auth.py` changes atomic.

### Files touched summary (Phase 4a)

| File | Status | Line delta |
|---|---|---|
| `backend/src/agent_service/api/admin_auth.py` | modified | +169 (25 → 194) |
| `backend/tests/test_admin_auth_dependencies.py` | NEW | +260 |
| `backend/src/agent_service/api/admin_analytics/overview.py` | modified | +0 (swap) |
| `backend/src/agent_service/api/admin_analytics/conversations.py` | modified | +0 (swap) |
| `backend/src/agent_service/api/admin_analytics/traces.py` | modified | +0 (swap) |

5 files exactly at the 5-file phase budget per `AGENTS.md` §2.

### Cumulative test count

| Phase | New tests | Cumulative |
|---|---|---|
| Baseline | — | 149 |
| Phase 1 | +14 | 163 |
| Phase 2 | +25 | 188 |
| Phase 3a | +21 | 209 |
| Phase 3b | +22 | 231 |
| Phase 4a | +15 | 246 |

### What's next: Phase 4b (5 files, no new tests)

Migration swap `require_admin_key` → `require_admin` on:
1. `backend/src/agent_service/api/admin_analytics/guardrails.py`
2. `backend/src/agent_service/api/feedback.py` (3 occurrences — swap all)
3. `backend/src/agent_service/api/endpoints/sessions.py` (4 occurrences)
4. `backend/src/agent_service/api/endpoints/live_dashboards.py` (2 occurrences)
5. `backend/src/agent_service/api/endpoints/rate_limit_metrics.py` (2 occurrences)

Each is a mechanical swap on the router-level `dependencies=[Depends(...)]` clause (or per-handler dependencies for files that don't use router-level). Expected test count unchanged: 246.

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### Phase 3b results (2026-04-11) — HTTP surface

- [x] **`backend/src/agent_service/security/admin_jwt.py`** (modify, +17 lines) — added `revoke_refresh_token(redis, token)` public wrapper: parses the token, extracts family_id, delegates to `revoke_refresh_family`. Idempotent on empty/malformed input (logout path calls unconditionally).
- [x] **`backend/tests/test_admin_jwt.py`** (modify, +23 lines, **+3 tests**) — `test_revoke_refresh_token_by_string_revokes_family`, `test_revoke_refresh_token_idempotent_on_malformed`, `test_revoke_refresh_token_then_verify_raises`. Test count: 25 → 28.
- [x] **`backend/src/agent_service/api/endpoints/admin_auth_routes.py`** (NEW, ~315 lines) — FastAPI router with 5 endpoints: `POST /admin/auth/login`, `POST /admin/auth/mfa/verify`, `POST /admin/auth/refresh`, `POST /admin/auth/logout`, `GET /admin/auth/me`. Shared helpers `_set_auth_cookies`, `_clear_auth_cookies`, `require_csrf_token` (double-submit enforcement via `hmac.compare_digest`). Pydantic request models. Error bodies match existing `HTTPException(detail={"code","operation","message"})` convention. Constant-time email + password verification on login to prevent timing oracles. `InvalidToken` from Fernet decryption → 503 `admin_auth_misconfigured` (handles master-key-rotated-without-re-encryption case).
- [x] **`backend/src/agent_service/core/app_factory.py`** (modify, +7 lines) — mounted `admin_auth_router` in `_mount_routers()` with lazy inline import to keep the module truly dormant until the router is actually attached.
- [x] **`backend/tests/test_admin_auth_endpoints.py`** (NEW, ~405 lines, **19 integration tests**) — full auth lifecycle via `httpx.ASGITransport` + `httpx.AsyncClient` + `fakeredis.aioredis.FakeRedis`. Tests: login happy/sad (4), MFA verify valid/invalid/no-access/no-csrf/lockout (5), refresh rotate/mfa-drop/tampered/no-csrf/replay (5), logout revoke/idempotent (2), me valid/expired/no-cookie (3).
- [x] **`make lint` green** — ruff clean + mypy clean on 8-file strict set
- [x] **Full test suite green** — `pytest tests/ -q` → **231 passed in 14.39s** (209 from Phase 3a + 22 new)
- [x] **Deprecation gate green** — `PYTHONWARNINGS='error::Deprecation*' pytest tests/ -q` → **231 passed in 13.92s** (zero warnings, including the httpx per-request-cookies deprecation which required migrating the tests to the client-jar pattern)

### Phase 3b deviations from the sub-plan

1. **Test count**: 22 actual (19 + 3) vs planned 22. On target.
2. **httpx per-request cookies deprecation surfaced mid-phase**: first pass used `cookies=dict` per-request, which triggered 20 `DeprecationWarning` lines and would have failed the deprecation gate. Refactored the entire test file to use `client.cookies` jar pattern — login stores cookies automatically, helpers return only the CSRF token.
3. **Cookie jar domain/path gotcha**: trying to rebuild cookies via `client.cookies.set(name, value, domain="test", path="/")` stored the cookies in the jar BUT httpx then refused to SEND them on subsequent requests (domain-match failure). Verified via a standalone debug script. Fix: omit `domain=`/`path=` arguments — `set(name, value)` stores with defaults that match any request. Captured as a lesson candidate.
4. **Inline lazy import in `app_factory`**: the sub-plan said "use an inline lazy import to avoid triggering admin_auth_routes' imports at module load". Implemented as specified — import happens inside `_mount_routers()` body, not at module top. This keeps `admin_auth_routes.py`'s own imports (admin_jwt, admin_totp, password_hash) lazy-loaded.
5. **Unused `admin_totp` import left behind during test refactor** — fixed after ruff caught it in the final validation sweep.
6. **`test_logout_is_idempotent_with_no_cookies`** asserts 403 (not 200) because logout requires CSRF and a session-less client has no CSRF cookie. The intent is captured — logout can't be abused without a session — and the comment explains the 403-is-acceptable reasoning.

### Files touched summary (Phase 3b)

| File | Status | Line delta |
|---|---|---|
| `backend/src/agent_service/security/admin_jwt.py` | modified | +17 |
| `backend/tests/test_admin_jwt.py` | modified | +23 (+3 tests) |
| `backend/src/agent_service/api/endpoints/admin_auth_routes.py` | NEW | +315 |
| `backend/src/agent_service/core/app_factory.py` | modified | +7 |
| `backend/tests/test_admin_auth_endpoints.py` | NEW | +405 |

5 files exactly at the 5-file phase budget per `AGENTS.md` §2.

### Cumulative test count

| Phase | New tests | Cumulative |
|---|---|---|
| Baseline | — | 149 |
| Phase 1 | +14 | 163 |
| Phase 2 | +25 | 188 |
| Phase 3a | +21 | 209 |
| Phase 3b | +22 | 231 |

### Phase 3 in total

Phase 3 (3a + 3b combined) delivered:
- **10 new files** (4 source + 4 test + 1 router + 1 modified app_factory, excluding Makefile) — under the 9-file cumulative-budget projection
- **43 new tests** (21 in 3a + 22 in 3b)
- **5 FastAPI endpoints** with full TDD coverage
- **2 new security primitives** (password hashing + TOTP with lockout)
- **Zero runtime impact** — everything is dormant behind `ADMIN_AUTH_ENABLED=False`

### What's next: Phase 4 (wiring admin endpoints to the new auth)

Per the main plan, Phase 4 splits into 4a/4b/4c:
- **Phase 4a**: replace `require_admin_key` with role-aware `require_admin` + `require_super_admin` + `require_mfa_fresh` dependencies; wire admin analytics read routers (overview, conversations, traces, guardrails) — **5 files**
- **Phase 4b**: wire remaining admin analytics routers (costs, categories, health, users, model-config) — **5 files**
- **Phase 4c**: wire KB mutation endpoints (create/update/delete FAQs) under super-admin + MFA — **2 files**
- **Rate limiting** (D9) gets wired during Phase 4 since that's when endpoints become consumer-facing

Plus the feature-flag-gated dual-run: during Phase 4, both `require_admin_key` legacy path AND the new JWT path work in parallel. Phase 6 deletes the legacy path.

Expected post-Phase-4 file count: ~12 additional files modified/added across 3 sub-phases.

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### Phase 3a results (2026-04-11) — primitives

- [x] **`backend/src/agent_service/security/password_hash.py`** (NEW, ~58 lines) — `hash_password()`, `verify_password()`, `needs_rehash()`. Thin wrapper over argon2-cffi's `PasswordHasher()` (RFC 9106 low-memory default). `verify_password` catches `VerifyMismatchError`, `VerificationError`, and `InvalidHash` — never raises, always returns bool.
- [x] **`backend/tests/test_password_hash.py`** (NEW, ~62 lines, **11 tests**) — argon2id prefix check, empty-rejection, random-salt verification, correct/wrong password paths, malformed hash returns False (no raise), needs_rehash happy path + 2 edge cases.
- [x] **`backend/src/agent_service/security/admin_totp.py`** (NEW, ~96 lines) — `verify_totp_code()` with Redis-backed lockout: 5 failures in 5-min window → 15-min absolute lockout. Two Redis keys: `admin_auth:lockout:<sub>` (counter) and `admin_auth:locked:<sub>` (marker). `reset_lockout()` for enrollment/recovery paths. Custom exceptions `TOTPLockedOut`, `TOTPInvalidCode`.
- [x] **`backend/tests/test_admin_totp.py`** (NEW, ~150 lines, **10 tests**) — valid code accepted, invalid code increments counter, success clears counter, 5 failures trigger lockout, locked state has 15-min TTL, existing lock short-circuits even valid codes, empty code rejected, empty sub rejected, decrypt failure propagates (InvalidToken), reset_lockout clears both keys.
- [x] **`backend/Makefile`** (modify) — mypy strict set expanded from 6 files to 8: added `password_hash.py` and `admin_totp.py`.
- [x] **Targeted mypy on new files** — `mypy password_hash.py admin_totp.py` → "Success: no issues found in 2 source files"
- [x] **`make lint` green** — ruff clean + mypy clean on all 8 files in the strict set
- [x] **Full test suite green** — `pytest tests/ -q` → **209 passed in 8.44s** (188 from Phase 2 + 21 new)
- [x] **Deprecation gate green** — `PYTHONWARNINGS='error::Deprecation*' pytest tests/ -q` → **209 passed in 8.80s** (zero warnings)

### Phase 3a deviations from the sub-plan

1. **Test count**: 21 actual vs 20 planned (11 password_hash + 10 admin_totp vs sub-plan's 10 + 10). One extra password_hash test added (`test_needs_rehash_returns_false_on_empty_hash` split out as its own case).
2. **File count**: 5 actual (4 source + Makefile) vs 4 planned in sub-plan. I added the two new modules to the Makefile's mypy strict set in Phase 3a instead of deferring to Phase 3b, because it's a 1-line change and immediately validates that the new files are strict-clean. Still within the 5-file phase budget per `AGENTS.md` §2.
3. **Ruff fix mid-phase**: two dead imports (`admin_totp` module alias and `AdminCryptoConfigError`) landed in the test file during RED stage, surfaced only when `make lint` ran. Fixed in place before moving to GREEN validation — unused imports from iterative development.
4. **`InvalidToken` vs `AdminCryptoConfigError` propagation**: the decrypt-failure test expects `cryptography.fernet.InvalidToken` (which is what bubbles up from `decrypt_secret` when the master key is rotated after encryption). The original sub-plan listed it as propagating `AdminCryptoConfigError`, but that exception is raised only for missing/malformed master key, not for wrong-key decryption. Corrected in the test. No functional impact.

### Files touched summary (Phase 3a)

| File | Status | Line delta |
|---|---|---|
| `backend/src/agent_service/security/password_hash.py` | NEW | +58 |
| `backend/src/agent_service/security/admin_totp.py` | NEW | +96 |
| `backend/tests/test_password_hash.py` | NEW | +62 |
| `backend/tests/test_admin_totp.py` | NEW | +150 |
| `backend/Makefile` | modified | +2 lines (strict mypy set) |

5 files within the 5-file phase budget per `AGENTS.md` §2.

### Cumulative test count

| Phase | New tests | Cumulative |
|---|---|---|
| Baseline | — | 149 |
| Phase 1 | +14 | 163 |
| Phase 2 | +25 | 188 |
| Phase 3a | +21 | 209 |

### What's next: Phase 3b (HTTP surface)

Per the approved sub-plan (5 files):
- `backend/src/agent_service/api/endpoints/admin_auth_routes.py` (new, ~320 lines) — 5 endpoints: `/login`, `/mfa/verify`, `/refresh`, `/logout`, `/me`; shared `_set_auth_cookies`, `_clear_auth_cookies`, `require_csrf_token` helpers
- `backend/src/agent_service/core/app_factory.py` (modify, +2 lines) — mount the new router
- `backend/src/agent_service/security/admin_jwt.py` (modify, +15 lines) — add `revoke_refresh_token(token)` public wrapper
- `backend/tests/test_admin_jwt.py` (modify, +30 lines, +3 tests)
- `backend/tests/test_admin_auth_endpoints.py` (new, ~420 lines, 19 integration tests via `httpx.ASGITransport` + FakeRedis)

Expected post-Phase-3b test count: **230**. Rate limiting remains deferred to Phase 4 per D9.

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### Phase 2 results (2026-04-11)

- [x] **`backend/src/agent_service/security/admin_jwt.py`** (NEW, ~300 lines) — Access token issuer (`issue_access_token`), verifier (`verify_access_token`), `mfa_fresh()` helper, refresh token issuer (`issue_refresh_token`), verifier (`verify_refresh_token`), rotator (`rotate_refresh_token`), family revoker (`revoke_refresh_family`). Frozen dataclasses `AccessClaims` and `RefreshHandle`. Exception hierarchy `InvalidAccessToken → ExpiredAccessToken`, `InvalidRefreshToken → RefreshTokenReplayDetected`. Opaque refresh token format `<family_id>.<token_id>.<hmac_sha256>`. Redis family state at `admin_auth:rt:<family_id>` with fixed-window TTL (no sliding).
- [x] **`backend/tests/test_admin_jwt.py`** (NEW, ~320 lines, **25 tests**) — Access token round-trips (5 tests), access token rejection paths (7 tests: expired/tampered/wrong-aud/wrong-iss/missing-jti/missing-roles/empty), MFA freshness (3 tests), refresh token lifecycle via `fakeredis.aioredis.FakeRedis` (10 tests: issue/verify/rotate/replay-detection/revoke/tampered-hmac/nonexistent-family/revoked-family/idempotent-revoke/malformed).
- [x] **`backend/Makefile`** (modify) — mypy strict target set expanded from 4 files to 6: added `admin_crypto.py` and `admin_jwt.py`.
- [x] **`backend/Makefile`** (incidental fix) — corrected 3 stale paths from Phase 5 refactor: `features/knowledge_base_repo.py` → `features/knowledge_base/repo.py`, `features/knowledge_base_service.py` → `features/knowledge_base/service.py`, `features/faq_pdf_parser.py` → `features/knowledge_base/faq_pdf_parser.py`. Pre-existing bug discovered while running `make lint`; fixed in-phase per end-to-end ownership rule.
- [x] **Targeted mypy on new file** — `mypy src/agent_service/security/admin_jwt.py` → "Success: no issues found in 1 source file"
- [x] **`make lint`** — ruff clean + mypy clean on all 6 files in the strict set
- [x] **Full test suite green** — `pytest tests/ -q` → **188 passed in 6.89s** (163 from Phase 1 + 25 new)
- [x] **Deprecation gate green** — `PYTHONWARNINGS='error::Deprecation*' pytest tests/ -q` → **188 passed in 6.61s** (zero deprecation warnings)

### Phase 2 deviations from the sub-plan

1. **Test count** — sub-plan said 23 tests. Actual count is **25** because two test cases split when I wrote them (`test_revoke_refresh_family_is_idempotent` and `test_verify_refresh_token_rejects_malformed_token` were added as explicit cases). Same as Phase 1's test-count miscount pattern — redundancy is good for regression surface.
2. **Pre-existing Makefile bug** — `make lint` failed on first run because the mypy target referenced 3 stale paths (`features/knowledge_base_repo.py` etc.) that had been moved into the `knowledge_base/` subpackage in an earlier phase (recorded as "Phase 5: Structural Refactor" in this file). The bug was pre-existing but blocked my Phase 2 validation, so I fixed it in-phase — this inflates my phase file count from 3 to 3 (Makefile counts once even though it was touched twice). Still within the 5-file phase budget.
3. **`RefreshHandle.issued_at` derivation edge** — in `verify_refresh_token`, I derive `issued_at` from `expires_at - JWT_REFRESH_TTL_SECONDS`, which is approximate. This field is informational only and not used in any security decision, so the approximation is acceptable per the sub-plan's residual risks section.
4. **`_REFRESH_REDIS_PREFIX` is imported by the test file** — the test checks Redis state at the exact key prefix. This is a private module constant leak into tests, which is OK for white-box testing the storage layout. If Phase 3 needs to change the prefix, both files update in lockstep.

### Files touched summary (Phase 2)

| File | Status | Line delta |
|---|---|---|
| `backend/src/agent_service/security/admin_jwt.py` | NEW | +300 |
| `backend/tests/test_admin_jwt.py` | NEW | +320 |
| `backend/Makefile` | modified (2 edits) | +2 lines added; 3 lines corrected to new paths |

3 files within the 5-file phase budget per `AGENTS.md` §2.

### Cumulative test count

| Phase | New tests | Cumulative |
|---|---|---|
| Baseline | — | 149 |
| Phase 1 | +14 | 163 |
| Phase 2 | +25 | 188 |

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### Phase 1 results (2026-04-11)

- [x] **`backend/src/agent_service/core/config.py`** — appended 71-line `ADMIN AUTHENTICATION` section (L289–L359). New constants: `ADMIN_AUTH_ENABLED`, `ADMIN_AUTH_COOKIE_SECURE`, `ADMIN_AUTH_COOKIE_NAME_ACCESS`, `ADMIN_AUTH_COOKIE_NAME_REFRESH`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_ACCESS_TTL_SECONDS`, `JWT_REFRESH_TTL_SECONDS`, `JWT_MFA_FRESHNESS_SECONDS`, `JWT_SECRET`, `FERNET_MASTER_KEY`, `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD_HASH`, `SUPER_ADMIN_TOTP_SECRET_ENC`. Plus `_validate_admin_auth_config()` fail-closed guard that runs at import time iff `ADMIN_AUTH_ENABLED=True`.
- [x] **`backend/src/agent_service/security/admin_crypto.py`** (NEW, 108 lines) — `encrypt_secret()`, `decrypt_secret()`, `validate_jwt_secret()`, `generate_fernet_key()`, `_get_fernet()` lazy singleton, `AdminCryptoConfigError` exception, `_reset_for_testing()` helper.
- [x] **`backend/tests/test_admin_crypto.py`** (NEW, 126 lines, 14 tests) — Round-trip, high-entropy input, empty plaintext/ciphertext rejection, tampered ciphertext, wrong master key, missing/malformed master key config errors, JWT secret length validation (accept ≥32, reject <32, reject empty, reject None), generated key usability.
- [x] **`.env.example`** (repo root) — appended 30-line admin auth section with `ADMIN_AUTH_ENABLED=false` default, secret generation snippets, optional override documentation.
- [x] **Ruff clean** — `ruff check .` → "All checks passed!"
- [x] **Mypy strict on new file** — `mypy src/agent_service/security/admin_crypto.py` → "Success: no issues found in 1 source file"
- [x] **Full test suite green** — `pytest tests/ -q` → **163 passed in 6.56s** (149 baseline + 14 new = 163; no regressions)
- [x] **Deprecation gate green** — `PYTHONWARNINGS='error::Deprecation*' pytest tests/ -q` → **163 passed in 6.36s** (zero deprecation warnings)

### Phase 1 deviations from the original sub-plan

1. **Order-of-operations fix** — the original sub-plan had tests written first, then `admin_crypto.py`, then `config.py`. But `admin_crypto.py` imports `FERNET_MASTER_KEY` from `config.py`, so the test collection failed with `ImportError` after the first implementation pass. Corrected sequence was: tests → implementation → config → re-run. No functional impact, same 4 files, same outcome.
2. **Test count** — sub-plan said "13 tests across 4 functional areas". Actual count after writing is **14** (I miscounted in the plan). Extra test is `test_round_trip_handles_high_entropy_input` which is distinct from the basic round-trip.
3. **`cryptography.fernet` import works unchanged** — no shimming needed despite the `cryptography 46.0.5 → 46.0.7` bump from Phase 0.
4. **Environmental prerequisite**: user's `backend/.venv` was a broken copy from an unrelated project (`HFCL-FastMCP-server-httpx-tools`). Line 81 of `.venv/bin/activate` had the stale path hardcoded. Fixed in-session with a one-line sed patch. Binary shims (`pytest`, `black`) were fine — only the `activate` shell script had the bug. Root cause is upstream (venv was copied, not recreated) — pre-existing, not introduced by this plan.

### Files touched summary (Phase 1)

| File | Status | Line delta |
|---|---|---|
| `backend/src/agent_service/core/config.py` | modified | +71 (287 → 359 lines) |
| `backend/src/agent_service/security/admin_crypto.py` | NEW | +108 |
| `backend/tests/test_admin_crypto.py` | NEW | +126 |
| `.env.example` (repo root) | modified | +30 |
| `backend/.venv/bin/activate` | patched (out of git, sed fix) | 3 replacements |

4 source files within the 5-file phase budget per `AGENTS.md` §2. The venv activate patch is an environmental fix, not a repo change.

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### Phase 0 results (2026-04-10)

- [x] **pyproject.toml** updated with 4 new direct deps: `pyjwt>=2.12.1,<3.0.0`, `cryptography>=46.0.7,<47.0.0`, `pyotp>=2.9.0,<3.0.0`, `argon2-cffi>=25.1.0,<26.0.0`
- [x] **uv.lock** regenerated cleanly (234 packages, no resolver warnings, 4 version bumps as expected: `pyjwt 2.10.1→2.12.1`, `cryptography 46.0.5→46.0.7`, `pyotp 2.9.0 new`, `argon2-cffi 25.1.0 new + argon2-cffi-bindings 25.1.0 transitive`)
- [x] **Smoke tests passed** — HS256 JWT round-trip, TOTP generate/verify with `valid_window=1`, argon2id hash/verify, Fernet encrypt/decrypt — all 4 packages usable end-to-end
- [x] **Ruff clean** — `uv run ruff check .` → "All checks passed!"
- [x] **Test baseline green** — `uv run python -m pytest tests/ -q` → **149 passed in 7.01s**
- [x] **Deprecation gate green** — `PYTHONWARNINGS='error::DeprecationWarning,error::PendingDeprecationWarning' uv run python -m pytest tests/ -q` → **149 passed in 6.59s** (ZERO deprecation warnings)
- [x] **Dev env restored** via `make install-dev` after `uv sync` pruned `ruff`/`black`/`isort`/`fakeredis`/`pytest-cov`/`mkdocs` (pre-existing dual-dep-system trap, see `lessons.md` L2)

### Phase 0 findings requiring Phase 2 enforcement

1. **PyJWT 2.12.x enforces HS256 key length ≥32 bytes via `InsecureKeyLengthWarning`.** Phase 1 must add a config-load-time length assertion on `JWT_SECRET`; Phase 2's `admin_jwt.py` must refuse to issue tokens with a weak secret; enrollment runbook must specify secret generation via `secrets.token_urlsafe(32)`. See `lessons.md` L1.
2. **`uv sync` alone is insufficient to prepare `backend/` for testing** — must be followed by `make install-dev`. Pre-existing repo design issue, flagged for out-of-scope cleanup (see §11 below).

### §11 Pre-existing cleanup recommendation (out of scope for this plan)

`backend/` has two parallel dev-dep management systems:
- `pyproject.toml` `[dependency-groups] dev` — minimal (mypy, pytest, pytest-asyncio, pre-commit)
- `requirements-dev.txt` — fuller set (adds ruff, black, isort, pytest-cov, fakeredis, mkdocs, mkdocs-material)

`make install-dev` reconciles them by running `uv pip install -r requirements-dev.txt` on top of `uv sync`, but a plain `uv sync` (as a developer would naturally run) prunes everything not in the pyproject dev group. This is a latent trap that surprised me in Phase 0.

**Recommended fix (separate task):** consolidate `requirements-dev.txt` contents into `pyproject.toml` `[dependency-groups] dev` and either delete `requirements-dev.txt` or have it re-export the uv group. Not part of this plan — flagging for a separate follow-up.

---

**Status (original plan from 2026-04-10, below):** Plan drafted.

### 0. Assumptions (correct any before approving)

1. **Scope interpretation of "admin = everyone, super admin = me":**
   - **Admin role** = open read access to admin analytics endpoints. No login, no user DB, no password. The `admin` role exists only so the JWT middleware has something to check and so audit logs can stamp a request type. Access is gated only by rate limiting, not identity.
   - **Super-admin role** = exactly one hardcoded operator (you), identified by a single env-var-seeded credential: `SUPER_ADMIN_EMAIL` + `SUPER_ADMIN_PASSWORD_HASH` (argon2id) + `SUPER_ADMIN_TOTP_SECRET_ENC` (Fernet-encrypted-at-rest). No users table, no migration, no multi-admin management. When you eventually need multi-admin, swap the env-var lookup for a Postgres `admin_users` table without changing the JWT contract.
   - Super-admin is the ONLY role that can mutate the knowledge base (FAQ create / update / delete). All other admin endpoints remain open (or behind optional rate-limiting-only `require_admin`).
2. **WAHA is NOT the auth provider.** WAHA is a WhatsApp gateway with a static shared bearer key — not an IdP, not a JWT issuer. Per the earlier correction in this session, using WAHA for admin auth was rejected. WAHA may optionally be used later as an **audit notification channel** (WhatsApp-push super-admin action alerts to an operator group) — that is out of scope for this plan.
3. **Compliance regime:** `[CONFIRM]` Assumed to be **prototype / no external regulatory audit** (project lives under `mock-ai/` directory, solo operator, no PII-handling commitments). If this is wrong and you're actually operating under RBI Master Direction on IT Framework for NBFCs or any other regime, stop and say so — the plan changes materially (7-year audit log retention, KMS-backed secret storage, quarterly access reviews, independent audit trail immutability, incident response runbook).
4. **Frontend storage:** JWT goes into an `httpOnly Secure SameSite=Strict` cookie. No tokens in `localStorage`. The existing `nbfc_admin_key` in `localStorage` is deleted as part of the cutover.
5. **Rollout discipline:** a feature flag `ADMIN_AUTH_ENABLED` (default `false` during rollout) gates the new auth path. The current `X-Admin-Key` fallback remains accepted in parallel until the flag flips, then the fallback is deleted. No big-bang cutover.
6. **Security incident still open:** the WAHA API key you pasted earlier in this session is compromised and must be rotated before any implementation begins. This is an operational prerequisite, not a code step, but it is blocking.

### 1. Requirements restatement

| # | Requirement | Measured by |
|---|---|---|
| R1 | Replace the single shared `ADMIN_API_KEY` world with a JWT-based admin session model | `require_admin_key` dependency deleted; all admin routers use `require_admin` or `require_super_admin` |
| R2 | Introduce a distinct `super_admin` role that is required for KB mutation endpoints (create / update / delete FAQ) | Attempting KB mutations with an admin-only JWT returns `403` with a specific `super_admin_required` error code |
| R3 | Super-admin tier requires a fresh TOTP verification (≤5 min old) for every mutating call | JWT carries `mfa_verified_at` claim; middleware rejects if `now() - mfa_verified_at > 5 min`; re-verification re-issues the JWT |
| R4 | Zero user-table migration — super-admin credential is env-var-seeded for the prototype phase | Only config / env changes; no Postgres schema changes in this plan |
| R5 | Fail-closed on every failure mode (missing config, bad signature, expired token, disabled account) | `403` with RFC 7807 Problem Detail body, never `200` with partial data |
| R6 | Audit log of every super-admin action (who, when, what endpoint, what resource, outcome) | Structured log line with `super_admin_action=true` shipped to existing logging pipeline |
| R7 | No deprecation warnings introduced by any new dep | `make test-deprecation` passes |
| R8 | No regression in existing admin analytics endpoints during rollout | Existing `ADMIN_API_KEY` path continues working until feature flag flips |

### 2. Policy matrix

| Endpoint class | File(s) | Current guard | Target guard | Notes |
|---|---|---|---|---|
| Admin analytics — overview, conversations, traces, guardrails, costs, categories, health, users, model-config | `src/agent_service/api/admin_analytics/*.py` | `require_admin_key` | `require_admin` | Read-only; `admin` role = open rate-limited access |
| KB **read** (list FAQs, get FAQ, export) | `src/agent_service/api/admin.py` (read paths) | `require_admin_key` | `require_admin` | Safe to leave under the open admin tier |
| KB **create** (`POST /admin/faqs`, `POST /admin/faqs/upload`) | `src/agent_service/api/admin.py` (mutation paths) | `require_admin_key` | `require_super_admin` + `mfa_fresh` | TOTP required, 5-min freshness |
| KB **update** (`PUT /admin/faqs/{id}`, bulk edits) | `src/agent_service/api/admin.py` | `require_admin_key` | `require_super_admin` + `mfa_fresh` | TOTP required |
| KB **delete** (`DELETE /admin/faqs/{id}`, bulk deletes) | `src/agent_service/api/admin.py` | `require_admin_key` | `require_super_admin` + `mfa_fresh` | TOTP required |
| Auth endpoints (login, mfa/verify, refresh, logout, /me) | `src/agent_service/api/endpoints/admin_auth_routes.py` (new) | N/A | Public login endpoint, bearer-protected refresh / logout / me | Rate-limited hard (fail_closed, 5 req/min per IP) |

The exhaustive endpoint mapping (which specific `admin.py` handler is read vs mutation) will be captured at the start of Phase 4 via a grep over `@router.{post,put,delete,patch}` in `admin.py`; if any handler is ambiguous it gets flagged on the plan and resolved before Phase 4 starts.

### 3. Architecture decisions (locked-in unless challenged)

- **JWT algorithm:** HS256 for Phase 1-4 (single-secret, single-service). Move to RS256 with JWKS rotation only if/when a second service needs to verify tokens. Rationale: RS256 adds operational complexity (key-pair management, rotation ceremony) with zero benefit when only `agent_service` issues and verifies.
- **Access token TTL:** 15 minutes. Refresh via cookie-bound rotating refresh token, 8-hour sliding window, single-use, family detection on reuse (stolen-token invalidation).
- **MFA freshness TTL:** 5 minutes from last successful TOTP verification. Stored as `mfa_verified_at` claim in the access token; re-verification calls `/admin/auth/mfa/verify` which re-mints the access token with a fresh `mfa_verified_at`.
- **JWT claims shape:**
  ```json
  {
    "sub": "super_admin" | "anonymous_admin",
    "iss": "mft-agent-service",
    "aud": "mft-admin-console",
    "iat": 1712345678,
    "exp": 1712346578,
    "jti": "<uuid>",
    "roles": ["admin"] | ["admin", "super_admin"],
    "mfa_verified_at": 1712345700 | null
  }
  ```
- **Cookie flags:** `HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=<refresh-ttl>`. Cookie name `mft_admin_session`. Two cookies: `mft_admin_at` (access token, 15-min TTL) and `mft_admin_rt` (refresh token, 8-hour TTL). CSRF protection via double-submit token bound to the refresh cookie — a `X-CSRF-Token` header is required on every state-changing request.
- **TOTP parameters:** RFC 6238 standard — SHA-1 (per Authenticator apps), 6 digits, 30-second period, valid window ±1 step (so ≤30-sec clock skew tolerated). `pyotp.TOTP(secret).verify(code, valid_window=1)`.
- **TOTP secret at rest:** Fernet-encrypted using `FERNET_MASTER_KEY` env var. The decrypted secret exists only in memory during verification and is zeroed out after. Enrollment produces a one-time provisioning URI (`otpauth://`) that you scan into Authenticator once, then the raw secret is discarded from the env file and replaced with the encrypted form.
- **Password hashing:** argon2id via `argon2-cffi 25.1.0`'s `PasswordHasher()` which defaults to the RFC 9106 low-memory profile (OWASP current guidance). `check_needs_rehash()` gates auto-rehash on login.
- **Rate limiting on auth endpoints:** hard fail-closed; 5 req/min per IP on `/admin/auth/login` and `/admin/auth/mfa/verify`. Uses the existing `RateLimiterManager`. Account lockout after 5 consecutive failed TOTP verifications within 5 minutes — lockout state stored in Redis with a 15-min TTL.
- **Audit log:** structured `log.info(...)` with a fixed key set (`event`, `actor`, `action`, `resource_type`, `resource_id`, `outcome`, `request_id`, `source_ip`, `user_agent`, `mfa_verified_at`), routed to the existing stdout pipeline. For Phase 1 of this plan, audit logs live in stdout; persistence/retention to Postgres is explicitly deferred to a future phase.

### 4. Dependency Intelligence Gate

Per `AGENTS.md` "Dependency intelligence gate" — every package change gets verified against authoritative sources.

**Dep 1 — PyJWT (promote transitive → direct)**
- Dependency: `pyjwt[crypto]`
- Ecosystem: PyPI via `uv`
- Current repo version/state: `2.10.1` (transitive via guardrails-ai / langchain)
- Proposed version: `>=2.12.1,<3.0.0`
- Latest stable version as of review date: **2.12.1** (released 2026-03-13)
- Review date: 2026-04-10
- Authoritative sources checked: PyJWT readthedocs changelog, GitHub releases page, PyPI
- Changelog window reviewed: 2.10.1 → 2.12.1
- Breaking changes found: None in the 2.10→2.12 window (2.0.0 was the last major breaking release; `algorithms` parameter has been required in `decode()` since 2.0.0 — we will comply)
- Deprecations found: `verify_expiration` kwarg and `.decode(..., verify=False)` are deprecated — we will use the `options` dict instead
- Security advisories found: None open as of review date
- Runtime/platform compatibility: Python 3.11+, compatible
- Peer/transitive dependency impact: Pulls in `cryptography` for RS256/ES256 support; already transitively present — no new resolver conflicts expected
- Why this version chosen: latest stable, unblocks explicit direct declaration so version is pinned independent of transitive resolution
- Why newer versions not chosen: 2.12.1 is the current stable; no newer release exists
- Residual risks: promoting from transitive to direct may surface resolver warnings if a transitive consumer pins an incompatible range — to be verified in Phase 0 by running `uv lock` after the `pyproject.toml` edit
- **Latest-version validation: verified**

**Dep 2 — pyotp**
- Dependency: `pyotp`
- Ecosystem: PyPI via `uv`
- Current repo version/state: not installed
- Proposed version: `>=2.9.0,<3.0.0`
- Latest stable version as of review date: **2.9.0** (released 2023-07-27)
- Review date: 2026-04-10
- Authoritative sources checked: pyauth.github.io/pyotp changelog, PyPI, GitHub releases
- Changelog window reviewed: full 2.x series
- Breaking changes found: since 2.8.0, `HOTP.at()`, `TOTP.at()`, `TOTP.now()` return strings (not integers) — we will comply from day one
- Deprecations found: none
- Security advisories found: none open
- Runtime/platform compatibility: pure-Python, Python 3.7+, compatible with 3.11
- Peer/transitive dependency impact: zero-dependency library
- Why this version chosen: only current stable
- Why newer versions not chosen: no newer version exists; project is stable/low-churn (last release 2023)
- Residual risks: low-churn upstream means no active maintenance if a CVE lands — mitigation is to pin to `>=2.9.0,<3.0.0` and monitor GitHub issues. Given the attack surface is a TOTP verifier with constant-time comparison (added in 2.8.0), the library is simple enough to vendor if abandonware becomes a concern
- **Latest-version validation: verified**

**Dep 3 — argon2-cffi**
- Dependency: `argon2-cffi`
- Ecosystem: PyPI via `uv`
- Current repo version/state: not installed
- Proposed version: `>=25.1.0,<26.0.0`
- Latest stable version as of review date: **25.1.0**
- Review date: 2026-04-10
- Authoritative sources checked: argon2-cffi readthedocs, GitHub releases, PyPI
- Changelog window reviewed: 25.x release notes
- Breaking changes found: `argon2.PasswordHasher` default profile switched to RFC 9106 low-memory (OWASP-aligned) — this is the target behavior, no adjustment needed
- Deprecations found: none in current stable
- Security advisories found: none open; library is the reference Argon2 binding maintained by hynek
- Runtime/platform compatibility: Python 3.8+, CFFI-backed native compile path (`argon2-cffi-bindings` is the low-level dep and ships wheels for Linux/macOS/Windows x86_64 and arm64)
- Peer/transitive dependency impact: pulls in `argon2-cffi-bindings` which needs a wheel for the target platform; Dockerfile base image (already Debian-based per `backend/Dockerfile`) has wheels available; no new compile tooling needed
- Why this version chosen: current stable, OWASP-aligned defaults, active maintenance, Python 3.13/3.14 support already landed
- Why newer versions not chosen: no newer stable exists
- Residual risks: native wheel availability on exotic platforms (not relevant for this repo which only runs on x86_64 Linux containers)
- **Latest-version validation: verified**

### 5. Phased implementation sequence (≤5 files per phase, verify between phases)

Each phase ends with: `make quality && make test && make test-deprecation` (backend) or `npm run verify:quality` (frontend). No phase starts until the previous phase's verification passes.

**Phase 0 — Prerequisites & dependency install**
- Files: `backend/pyproject.toml`, `backend/uv.lock` (regenerated)
- Steps: add the three deps with the pinned ranges from §4, run `uv lock`, run `uv sync`, confirm `uv run python -c "import jwt, pyotp, argon2"` succeeds, run full test suite + deprecation gate to establish a green baseline
- Operational prerequisite (NOT a code step, user action): rotate the compromised WAHA API key
- Validation: `uv lock` produces no warnings; `make test` passes; `make test-deprecation` passes
- Rollback: revert `pyproject.toml` + regen lockfile
- Files touched: 2

**Phase 1 — Config surface + crypto helpers**
- Files: `backend/src/agent_service/core/config.py`, `backend/.env.example`, `backend/src/agent_service/security/admin_crypto.py` (new), `backend/tests/test_admin_crypto.py` (new)
- Steps: add `JWT_SECRET`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_ACCESS_TTL_SECONDS`, `JWT_REFRESH_TTL_SECONDS`, `JWT_MFA_FRESHNESS_SECONDS`, `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD_HASH`, `SUPER_ADMIN_TOTP_SECRET_ENC`, `FERNET_MASTER_KEY`, `ADMIN_AUTH_ENABLED` (feature flag, default `False`), `ADMIN_AUTH_COOKIE_SECURE` (default `True`, can be `False` only when `ENVIRONMENT=local`); implement `encrypt_secret()` / `decrypt_secret()` helpers using `cryptography.fernet`; unit-test round-trip and failure modes
- Validation: mypy strict on new file, ruff clean, unit tests cover happy path + 3 failure modes (missing key, tampered ciphertext, empty plaintext)
- Rollback: revert config + delete new files
- Files touched: 4

**Phase 2 — JWT issuer / verifier module**
- Files: `backend/src/agent_service/security/admin_jwt.py` (new), `backend/tests/test_admin_jwt.py` (new)
- Steps: implement `issue_access_token(sub, roles, mfa_verified_at)`, `issue_refresh_token(sub, family_id)`, `verify_access_token(token) -> Claims`, `verify_refresh_token(token) -> RefreshClaims`, `revoke_refresh_family(family_id)` (Redis-backed), `mfa_fresh(claims) -> bool`; unit-test signature verification, expired token rejection, tampered token rejection, refresh family reuse detection
- Validation: mypy strict, tests cover ≥10 cases (issue → verify, expired, tampered sig, wrong aud, wrong iss, missing jti, refresh rotation, family reuse, mfa fresh true/false)
- Rollback: delete new files
- Files touched: 2

**Phase 3 — Auth endpoints (login / mfa / refresh / logout / me)**
- Files: `backend/src/agent_service/api/endpoints/admin_auth_routes.py` (new), `backend/src/agent_service/core/app_factory.py` (mount router), `backend/tests/test_admin_auth_endpoints.py` (new)
- Steps: implement `POST /admin/auth/login` (email+password → access+refresh cookies, no MFA claim), `POST /admin/auth/mfa/verify` (TOTP code → re-mint access token with fresh `mfa_verified_at`), `POST /admin/auth/refresh` (rotate refresh, re-mint access), `POST /admin/auth/logout` (revoke refresh family, clear cookies), `GET /admin/auth/me` (decode access token, return claims); wire rate limiter (5 req/min fail_closed on login + mfa endpoints, 60 req/min on refresh); wire account lockout (5 failed TOTP attempts in 5 min → 15-min lockout in Redis); return RFC 7807 Problem Details on every failure; integration tests hit every endpoint with happy + failure paths
- Validation: mypy strict, ≥15 integration test cases, rate-limit enforcement verified
- Rollback: un-mount router, delete new files
- Files touched: 3

**Phase 4a — Role-aware dependency + wire admin_analytics read endpoints**
- Files: `backend/src/agent_service/api/admin_auth.py` (replace `require_admin_key` with `require_admin` + `require_super_admin` + `require_mfa_fresh`), `backend/src/agent_service/api/admin_analytics/overview.py`, `backend/src/agent_service/api/admin_analytics/conversations.py`, `backend/src/agent_service/api/admin_analytics/traces.py`, `backend/src/agent_service/api/admin_analytics/guardrails.py`
- Steps: new dependency functions read JWT from cookie, verify via `admin_jwt.verify_access_token()`, return claims, raise RFC 7807 403 on failure; behind feature flag `ADMIN_AUTH_ENABLED=false` the dependencies fall back to the legacy `require_admin_key` behavior; flip endpoints to `Depends(require_admin)`; run full admin analytics tests
- Validation: existing admin analytics contract tests pass unchanged (they use `X-Admin-Key` via the legacy fallback); new tests verify JWT cookie path with feature flag on
- Rollback: feature flag = false reverts to legacy behavior
- Files touched: 5

**Phase 4b — Wire remaining admin_analytics read endpoints**
- Files: `backend/src/agent_service/api/admin_analytics/costs.py`, `backend/src/agent_service/api/admin_analytics/categories.py`, `backend/src/agent_service/api/admin_analytics/health.py`, `backend/src/agent_service/api/admin_analytics/users.py`, `backend/src/agent_service/api/admin_analytics/model_config.py`
- Steps: same pattern as 4a — `Depends(require_admin)` everywhere
- Validation: same test set
- Rollback: feature flag off
- Files touched: 5
- Note: exact file list will be confirmed at the start of Phase 4 via `grep -l "require_admin_key" backend/src/agent_service/api/admin_analytics/`; if fewer than 5 files exist, this phase merges into 4a; if more, it splits into 4b/4c

**Phase 4c — Wire KB mutation endpoints under super-admin + MFA**
- Files: `backend/src/agent_service/api/admin.py` (FAQ CRUD handlers)
- Steps: read vs write split — GET handlers get `Depends(require_admin)`; POST/PUT/DELETE handlers get `Depends(require_super_admin), Depends(require_mfa_fresh)`; add contract tests that verify 403 with admin-only JWT, 403 with stale MFA, 200 with fresh super-admin + MFA
- Validation: new contract tests + existing `test_admin_faqs_contract.py` updated to cover new auth model
- Rollback: feature flag off
- Files touched: 1 source + 1 test = 2

**Phase 5a — Frontend auth context + login page**
- Files: `Chatbot UI and Admin Console/src/features/admin/auth/LoginPage.tsx` (new), `src/features/admin/auth/MfaChallenge.tsx` (new), `src/features/admin/auth/AdminAuthProvider.tsx` (new — replaces adminKey with JWT-cookie-backed auth state), `src/features/admin/context/AdminContext.tsx` (retire `nbfc_admin_key` localStorage), `src/shared/api/http.ts` (add CSRF token header injection + 401 redirect to login)
- Steps: login form (email + password), MFA prompt modal triggered by any 403 `mfa_required` response, `AdminAuthProvider` fetches `/admin/auth/me` on mount to rehydrate session from cookie, logout button calls `/admin/auth/logout`; delete `nbfc_admin_key` from localStorage on app boot (one-time migration); http client adds `X-CSRF-Token` to every state-changing request
- Validation: `npm run typecheck`, `npm run test`, `npm run build`, Vitest tests for AuthProvider mount/unmount, login flow, MFA prompt
- Rollback: revert frontend changes; backend still works under legacy flag
- Files touched: 5

**Phase 5b — Route guards on admin pages**
- Files: `src/app/routes.ts` (add `requireAuth` guards on `/admin/*` routes), `src/features/admin/layout/AdminLayout.tsx` (consume `AdminAuthProvider`, redirect to login if not authenticated), `src/features/admin/guardrails/GuardrailsPage.tsx` etc. — wrap mutation calls with `requireMfa` helper that triggers the MFA modal on 403
- Steps: one pass over the 10 admin page files; the 3-4 that have mutation UIs (KB FAQ editor, maybe guardrail rule editor) get the MFA helper wrapped around their mutation hooks; the rest just need route guards
- Validation: e2e smoke via Playwright if set up, else manual checklist
- Rollback: revert routes
- Files touched: ≤5 (exact count determined after reading the pages; if more, split into 5b/5c)

**Phase 6 — Cutover & cleanup**
- Files: `backend/src/agent_service/api/admin_auth.py` (delete the legacy `require_admin_key` fallback branch), `backend/.env.example` (remove `ADMIN_API_KEY` documentation), `backend/src/agent_service/core/config.py` (remove `ADMIN_API_KEY` constant), `Chatbot UI and Admin Console/src/features/admin/context/AdminContext.tsx` (delete the `nbfc_admin_key`/`openrouterKey`/etc. remnants if no longer used)
- Steps: flip `ADMIN_AUTH_ENABLED=true` default, flip in staging, smoke test, flip in prod, delete legacy code
- Validation: `grep -r "require_admin_key\|ADMIN_API_KEY\|nbfc_admin_key" backend src "Chatbot UI and Admin Console"/src` returns zero hits
- Rollback: revert the deletions; feature flag off
- Files touched: 4

**Phase 7 — Documentation & operator runbook**
- Files: `CLAUDE.md` (update §5 gotchas to reflect new auth model; add §4 "auth" architecture note), `.cursor/rules/admin-auth.mdc` (new cursor rule), `backend/README.md` (new "Admin authentication" section), `docs/operations/super-admin-enrollment.md` (new — step-by-step: generate TOTP secret, encrypt with Fernet, set env vars, scan QR in Authenticator, test login)
- Steps: write the enrollment runbook with exact commands; add a `scripts/enroll_super_admin.py` helper that takes `--email`, `--password`, prompts for no input, and prints the three env var values to set
- Validation: run the enrollment script end-to-end in a throwaway environment; confirm login works
- Rollback: N/A for docs
- Files touched: 4 + 1 script = 5

### 6. Validation plan (cumulative)

- After every backend phase: `cd backend && make quality && make test && make test-deprecation`
- After every frontend phase: `cd "Chatbot UI and Admin Console" && npm run verify:quality`
- After Phase 4c: manual contract validation — curl `/admin/faqs` read returns 200 with admin JWT, curl `POST /admin/faqs` returns 403 without MFA, curl `POST /admin/faqs` returns 200 with MFA-fresh super-admin JWT
- After Phase 5b: manual browser walkthrough — visit `/admin`, get bounced to `/admin/login`, log in, verify read access works, click "Add FAQ", get MFA prompt, enter TOTP, confirm mutation succeeds
- Before Phase 6: dual-run validation — feature flag on AND legacy `X-Admin-Key` path both working in staging for at least 24 hours
- After Phase 6: regression sweep — full backend + frontend test suites, grep for residual legacy references

### 7. Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Misconfigured JWT secret locks out admin console in prod | HIGH | Feature flag gate; legacy path remains until flag flip; dual-run period |
| TOTP clock skew rejects legitimate super-admin | MEDIUM | `valid_window=1` gives ±30sec tolerance; enrollment runbook includes NTP check |
| CSRF double-submit implementation bug | HIGH | Cover CSRF header+cookie matching in integration tests; pin test for missing/mismatched header |
| Cookie `SameSite=Strict` breaks OAuth-style redirects from external auth (future) | LOW | Not a concern for phase scope; revisit only when/if SSO is added |
| `cryptography` version resolver conflict when promoting pyjwt to direct dep | LOW | Validated in Phase 0 via `uv lock`; rollback by unpromoting |
| Deprecation gate fails due to transitive dep emitting warnings | MEDIUM | Phase 0 establishes a clean baseline; regression caught immediately |
| Frontend JWT hydration race — `AdminAuthProvider` calls `/admin/auth/me` on mount but pages render before response | MEDIUM | Provider exposes `isLoading` state; `AdminLayout` blocks render until `isLoading === false` |
| Locked-out super-admin with no recovery | HIGH | Enrollment runbook documents recovery: stop agent_service, reset TOTP env var from backup Fernet-encrypted blob, restart |
| Audit log noise hides real super-admin actions in stdout | LOW | Structured logging with `super_admin_action=true` for easy grep/filter |

### 8. Rollback / recovery plan

- Every phase has a file-level revert path.
- Phases 4a through 5b are gated by `ADMIN_AUTH_ENABLED` feature flag — flipping to `false` reverts to the legacy `X-Admin-Key` world without redeployment.
- Phase 6 (cutover) is the point of no return; before Phase 6 I will require an explicit go-ahead from you after a successful 24-hour dual-run in staging.
- If a P0 issue surfaces after Phase 6 cutover, rollback is: re-deploy the pre-Phase-6 commit; legacy path resumes working.

### 9. Out of scope (explicitly deferred)

- Multi-admin user table + admin self-service
- SSO / IdP integration (Okta, Auth0, Keycloak)
- Audit log persistence to Postgres (lives in stdout for this phase)
- Quarterly access review automation
- KMS-backed TOTP secret storage (using local Fernet for prototype)
- MCP tool admin scoping (MCP tools remain session-level; no admin-only MCP tools in this plan)
- WhatsApp audit notifications via WAHA (optional future enhancement)
- Webauthn / passkey MFA
- Account recovery flow beyond the runbook-level reset

### 10. Approval checklist — answer before I touch any code

- [ ] **A1.** Assumption 1 ("admin = open read, super-admin = single env-var-seeded operator") correctly captures your intent?
- [ ] **A2.** Assumption 3 — confirm there is NO regulatory audit requirement (prototype/mock)
- [ ] **A3.** Assumption 4 — confirm `httpOnly` cookie JWT storage is acceptable (no non-browser tooling currently reads `nbfc_admin_key` from localStorage that I don't know about)
- [ ] **A4.** Assumption 5 — confirm feature-flag-gated dual-run cutover is the right rollout model (vs. big-bang cutover in a maintenance window)
- [ ] **A5.** §3 locked-in decisions: HS256 (not RS256), 15-min access / 8-hour refresh / 5-min MFA freshness TTLs — accept as defaults or adjust
- [ ] **A6.** §5 phase sequence: accept as-is or reorder (e.g., do docs earlier, skip audit log, split differently)
- [ ] **A7.** **Operational prerequisite:** confirm the compromised WAHA API key has been rotated (not a plan step but a blocker)
- [ ] **A8.** **Existing `tasks/todo.md` history is preserved** — this plan was prepended, not replacing prior entries

**I will not start Phase 0 until every box above is checked or explicitly waived.**

---

## 2026-04-05 - Phase 0: MCP Service Async Conversion + Safety Fixes

- [x] Step 1: Change rate limiter default from fail_open to fail_closed (config.py)
- [x] Step 2: Rewrite session_store.py to async Redis (redis.asyncio, lazy singleton pool)
- [x] Step 3: Convert auth_api.py to async httpx.AsyncClient + remove hardcoded "crm"/"crm" creds
- [x] Step 4: Convert core_api.py to async (15+ methods, fix direct Redis .set() call)
- [x] Step 5: Convert server.py tools to async + add FastMCP lifespan + delete dead code
- [x] Step 6: Update test_session_store.py to async (pytest_asyncio.fixture + FakeAsyncRedis)
- [x] Verification: ruff clean, mypy clean, 146/146 tests pass

## 2026-04-05 - Frontend Audit Remediation (FE Phases 1-5)

- [x] FE Phase 1: Purged 23 unused shadcn/ui components (47% dead code), cleaned barrel export
- [x] FE Phase 2: Extracted KnowledgeBasePage inline components → 5 files in components/ (StatusBadge, CategoryBadge, FaqRow, EntryForm, AddEditFaqModal)
- [x] FE Phase 3: Extracted GuardrailsPage inline components → 6 files in components/ (TrendTooltip, RiskBadge, DecisionBadge, KpiCard, FailureCard, SortHeader)
- [x] FE Phase 4: Extracted NBFCLandingPage static data → landing-data.ts
- [x] FE Phase 5: Typed 2 Promise<any> endpoints in health.ts → RateLimitMetricsResponse, RateLimitConfigResponse
- [x] Verification: typecheck clean, build clean, 23 test files / 92 tests pass

## 2026-04-05 - Phase 5: Structural Refactor

- [x] 5A: Create features/routing/ package — moved nbfc_router, answerability, question_category, prototypes_nbfc; updated 8 imports
- [x] 5B: Create features/knowledge_base/ package — moved repo, service, milvus_store, faq_classifier, faq_pdf_parser; updated 9 imports
- [x] 5C: Consolidated _valid_session_id — 3 copies → 1 canonical in session_store.py
- [x] 5D: Upgraded swallowed exceptions — log.debug → log.warning + exc_info=True where needed
- [x] 5E: DI migration — added lazy factory functions (get_*) for 4 service singletons with backward-compat aliases
- [x] 5F: ToolNode migration — extracted DedupToolNode class from closure, encapsulates tool execution + dedup + policy
- [x] Verification: ruff clean, 146/146 tests pass

## 2026-04-05 - Phase 4: Dead Code & Cleanup

- [x] Step 1: Delete dead common/logger.py (0 consumers, confirmed orphan)
- [x] Step 2: Remove GraphQL layer — deleted graphql.py, removed strawberry mount from app_factory, removed strawberry-graphql dep from pyproject.toml
- [x] Step 3: Refactor catalog.py gpt-oss string matching → uses infer_model_capabilities(model_id=...) from capabilities.py
- [x] Step 4: Zero unused imports (ruff --select F401), 146/146 tests pass
- Phase 3 (MCP Infrastructure Unification) was already completed during Phase 0's async conversion

## 2026-04-05 - Phase 2: Shadow Eval Decomposition

- [x] Step 1: Create features/eval/ package + collector.py (ShadowEvalCollector) + throttle.py
- [x] Step 2: Create eval/metrics.py (compute_non_llm_metrics, compute_llm_metrics) + eval/persistence.py (_commit_bundle, STORE, EMBEDDER)
- [x] Step 3: Rewrite shadow_eval.py as thin orchestrator (maybe_shadow_eval_commit + re-exports)
- [x] Step 4: Fixed mypy error (meta dict type), verification: ruff clean, mypy clean, 146/146 tests pass
- Original 617-line god object → 5 focused modules: collector (~250), throttle (~50), metrics (~130), persistence (~30), orchestrator (~80)

## 2026-04-05 - Phase 1: Data Layer Extraction (Repository Pattern)

- [x] Step 1: Create admin_analytics/repo.py with AdminAnalyticsRepo class (15 SQL methods)
- [x] Step 2: Wire overview.py + conversations.py to repo, update test mock targets
- [x] Step 3: Wire guardrails.py to repo, delete _load_guardrail_trace_rows, update test mocks
- [x] Step 4: Wire traces.py to repo (9 queries across 4 functions), update test mocks
- [x] Step 5: Consolidate _json_load_maybe to delegate to eval_store/status.py canonical source
- [x] Verification: ruff clean, mypy clean, 146/146 tests pass

## 2026-04-05 - Production mobile redesign

- [ ] Phase 1: Foundation (AdminLayout sidebar overlay, landing nav, chat widget width)
- [ ] Phase 2: High-impact pages (Conversations drawer, Dashboard/Guardrails/Traces table columns)
- [ ] Phase 3: Medium-impact pages (UsersAnalytics, QuestionCategories, Costs, Feedback, KnowledgeBase)
- [ ] Phase 4: Polish (ModelConfig, SystemHealth, MetricsDashboard)
- [ ] Full verification at 375px, 390px, 768px, 1024px

## 2026-04-04 - Code review P0/P1 cleanup

- [x] P0: Create .env.example with dummy values, .env already gitignored
- [x] P0: Fix CORS wildcard → configurable `CORS_ALLOWED_ORIGINS` env var
- [x] P1: Delete dead backend files (graph_utils.py, cost.py→pricing.py, nbfc_taxonomy.py, faqs/)
- [x] P1: Delete dead frontend files (flags.ts, use-mobile.ts)
- [x] P1: Remove backward-compat shims (utils.py deleted, streaming_utils alias removed)
- [x] P1: Add logging to 15+ silent exception handlers (12 files, 30+ handlers)
- [x] P1: Remove console.log from production frontend hooks (3 instances)
- [x] Full verification: 136 backend tests, 87 frontend tests, typecheck + build clean

## 2026-04-04 - P4 External review fixes

- [ ] 4a: Backend dead code + bugs (kb_first, event_bus, sync Redis, config_manager, dual KB tool)
- [ ] 4b: Frontend dead exports (sidebar, toPrettyJson, formatNumber, useLiveSessionFeed, fetchConversations, extractTrace, ChartContainer)
- [ ] 4c: Frontend quality (parseMaybeJson, useEvalStatus fetch, Dashboard filter, refetchInterval, motion mock, localStorage try/catch)
- [ ] Full verification

## 2026-04-04 - P3 Code quality cleanup

- [x] Standardize error responses: `_raise_db_error` → standard `HTTPException(detail=str)` (1 file, 9 callers)
- [x] Convert f-string logs to parameterized: 45 instances across 14 files → zero remaining
- [x] Replace TypeScript `any`: 6 instances across 4 files → zero remaining
- [x] Full verification: 136 backend tests, 87 frontend tests, typecheck + build clean

## 2026-04-04 - P2 Monolith splits + cross-feature decoupling

- [x] P2a: Split `admin_analytics.py` (1,291 LOC) → `admin_analytics/` package (utils, guardrails, traces, conversations, overview)
- [x] P2b: Split `admin.ts` (790 LOC) → 6 domain files (faqs, guardrails, traces, sessions, health, feedback) + barrel re-export
- [x] P2b: Move navigation helpers to `@shared/lib/navigation.ts`, session config to `@shared/api/sessions.ts`
- [x] Full verification: 136 backend tests, 87 frontend tests, typecheck + build clean

## 2026-04-04 - Admin console enhancements (5 items)

- [x] Item 3: Show eval/judge scores in trace viewer (types + viewmodel + TraceInspector + GlobalTraceSheet)
- [x] Item 5: Add sorting arrows on guardrails Events Log table
- [x] Item 4: Inline BYOK key input in model-config (extract KeyInput + ModelConfig)
- [x] Item 1: ChatWidget-style conversation replay with markdown
- [x] Item 2: Context-aware welcome prompts (public vs authenticated)
- [x] Run frontend verification: typecheck clean, build clean, 79/79 tests passed

## 2026-04-04 - Admin transcript tool calls + NVIDIA diagnosis + eval status UI

- [ ] Fix admin conversation transcript: extract toolCalls from LangChain messages in `admin_analytics.py`
- [ ] Diagnose NVIDIA NIM: curl the endpoint, check logs, identify failure
- [x] Diagnose NVIDIA NIM: key empty in .env, added log warning. User will set key manually.
- [x] Add eval status polling endpoint `GET /eval/trace/{trace_id}/eval-status` in eval_read.py.
- [x] Add `useEvalStatus` hook with 5s polling, 10 attempt max, auto-stop on complete/not_found.
- [x] Add eval status badge on chat messages: pending (pulsing), passed (green), failed (amber).
- [x] Fix URL mismatch: hook now correctly calls `/eval/trace/...` matching backend router prefix.
- [x] Run verification: typecheck clean, build clean, 66/66 tests passed.

## 2026-04-04 - Fix eval lifecycle, judge truthfulness, admin replay, and safe HTML rendering

- [x] Phase 0: Update task/lesson docs for eval lifecycle + replay/rendering work.
- [x] Phase 1: Standardize `ENABLE_LLM_JUDGE` parsing and persist eval lifecycle metadata in trace `meta_json`.
- [x] Phase 1: Extend `/eval/trace/{trace_id}/eval-status` with terminal `unavailable` states and reason codes.
- [x] Phase 1: Add backend tests for `disabled`, `sampled_out`, `queued`, `worker_backlog`, `failed`, and `timed_out`.
- [x] Phase 1 verification: `cd backend && uv run mypy --explicit-package-bases --follow-imports=skip --ignore-missing-imports src/agent_service/api/admin.py && uv run ruff check . && uv run python -m pytest tests/ -v`
- [x] Phase 2: Extend frontend eval-status typing and stop indefinite pending UI.
- [x] Phase 2: Enable strict-allowlist HTML rendering in `ChatAssistantMarkdown`.
- [x] Phase 2: Extract `AssistantMessageCard` and finish live chat eval badge behavior for terminal unavailable states.
- [x] Phase 2: Add frontend hook/message/renderer tests for unavailable eval states and safe HTML rendering.
- [x] Phase 2 verification: targeted frontend checks passed for `useEvalStatus`, `ChatAssistantMarkdown`, and `ChatMessage`, plus `npm run typecheck`.
- [x] Phase 3: Separate admin replay from live `ChatMessage` polling/controls.
- [x] Phase 3: Batch-enrich admin session transcript messages with static `evalStatus`.
- [x] Phase 3: Add admin conversations replay tests for no polling, reasoning/raw tool calls, and rendered HTML parity.
- [x] Phase 3 verification: `cd backend && uv run mypy --explicit-package-bases --follow-imports=skip --ignore-missing-imports src/agent_service/api/admin.py && uv run ruff check . && uv run python -m pytest tests/ -v` and `cd "Chatbot UI and Admin Console" && npm run typecheck && npm run build && npm run test`

Review
- Phase 1 is complete and verified. Backend now persists eval lifecycle hints on traces, treats `ENABLE_LLM_JUDGE=1` as enabled, and returns terminal `unavailable` states instead of indefinite `pending` for legacy/non-terminal traces.
- Backend verification after Phase 1: `mypy` clean, `ruff` clean, `pytest` clean (`133 passed`).
- Phase 2 is complete and verified with targeted frontend checks:
  - `npm run test -- --run src/features/chat/hooks/useEvalStatus.test.ts`
  - `npm run test -- --run src/features/chat/components/ChatAssistantMarkdown.test.tsx`
  - `npm run test -- --run src/features/chat/components/ChatMessage.test.tsx`
  - `npm run typecheck`
- Live chat now terminates stale eval polling as `unavailable/timed_out`, renders safe allowlisted inline HTML color styling, and uses the shared `AssistantMessageCard` for assistant-only presentation ahead of admin replay separation.
- Phase 3 is complete and verified. Admin session transcripts now carry optional static `evalStatus`, replay messages no longer invent fallback `traceId` values, and `/admin/conversations` uses a read-only `TranscriptMessage` surface that reuses the shared assistant card without live eval polling or interactive follow-up/feedback behavior.
- Additional verification after Phase 3:
  - Backend: `uv run mypy --explicit-package-bases --follow-imports=skip --ignore-missing-imports src/agent_service/api/admin.py`, `uv run ruff check .`, `uv run python -m pytest tests/ -v` (`136 passed`)
  - Frontend: `npm run typecheck`, `npm run build`, `npm run test` (`23 files, 87 tests passed`)

## 2026-04-04 - Replace Lucide icons with custom tech logos in architecture page

- [x] Move icon files from `/icons/` to `Chatbot UI and Admin Console/public/icons/`.
- [x] Update `DiagramNode` to support `imgSrc` prop alongside `icon`.
- [x] Replace Lucide icons with custom SVGs/PNG in flow diagram nodes (Nginx, FastAPI, LangGraph, MCP Server).
- [x] Replace Lucide icons in data layer nodes (PostgreSQL, Milvus, Redis).
- [x] Run frontend verification: typecheck clean, build clean.

## 2026-04-04 - Landing page updates + architecture page

- [x] Phase 1: Remove "Explore site" button from hero section.
- [x] Phase 2: Make "Admin" nav button orange.
- [x] Phase 3: Replace "Apply Now" nav button with "View Architecture" linking to /architecture.
- [x] Phase 4: Create /architecture page with backend system design showcase.
- [x] Run frontend verification: typecheck clean, build clean, 66/66 tests passed.

## 2026-04-04 - Fix all tool calls displayed twice in chat UI

- [x] Backend: filter nested `on_tool_end` events by `parent_ids` overlap with tracked `tool_start_run_ids` — skips inner MCP adapter runs.
- [x] Frontend: add defensive dedup by `tool_call_id` in `useChatStream.ts` before appending to `toolCalls`.
- [x] Add backend test for `parent_ids` nested tool event filtering.
- [x] Add frontend test for duplicate `tool_call` SSE event dedup.
- [x] Run backend verification: pytest 7/7 passed.
- [x] Run frontend verification: typecheck clean, test 8/8 passed.

## 2026-04-04 - Prevent duplicate side-effect tool executions in a single turn

- [x] Add a shared backend execution-policy registry for side-effect MCP tools.
- [x] Disable automatic reconnect retry for side-effect tools while preserving retries for read-only tools.
- [x] Add same-turn tool dedupe to the LangGraph execution loop using canonical tool-name-plus-args keys.
- [x] Harden agent/tool guidance so side-effect tools are not intentionally repeated in the same turn after success.
- [x] Add focused regression tests for graph dedupe, MCP retry policy, and public stream tool-call behavior.
- [x] Run backend verification: `uv run mypy --explicit-package-bases --follow-imports=skip --ignore-missing-imports src/agent_service/api/admin.py`, `ruff check .`, and `uv run python -m pytest tests/ -v`.

## 2026-04-04 - Fix raw tool-call visibility and unify traces into right-side sheet

- [x] Normalize `tool_call` SSE payloads and preserve tool calls in the chat stream hook.
- [x] Add targeted backend/frontend tests for streamed tool-call propagation.
- [x] Remove the inline trace inspector from `/admin/traces` and rely on the shared right-side sheet.
- [x] Update trace page/sheet tests so `?traceId=` always opens the shared sheet and `Back` clears it.
- [x] Run affected backend and frontend verification commands.

## 2026-04-04 - Upgrade frontend toolchain to Vite 8

- [x] Create a prep checkpoint commit containing all tracked pre-upgrade changes.
- [x] Upgrade frontend toolchain versions to Vite 8 compatible releases.
- [x] Standardize frontend CI and Docker builder on Node 22.22.2-compatible tooling.
- [x] Replace deprecated/removed Vite 7 chunking config with Vite 8 Rolldown chunk grouping.
- [x] Update minimal frontend docs for the new Node baseline.
- [x] Run frontend verification: `npm ci`, `npm run typecheck`, `npm run test`, `npm run build`, `npm run verify:deprecation`, `npm run build:warning-check`.

## 2026-04-04 - Trace back flow, honest latencies, default Groq session pair, and raw tool calls

- [x] Fix trace explorer back/close behavior so `/admin/traces` drops `traceId` and stays unselected.
- [x] Replace the trace explorer `X` with a `Back` button and normalize trace link generation.
- [x] Preserve event timestamps through the trace viewer and replace fake child-node `0.0s` values with real timing or `—`.
- [x] Change new-session defaults to provider `groq` and model `openai/gpt-oss-120b`.
- [x] Add a `Raw tool calls` toggle beside `Reasoning` in assistant chat bubbles.
- [x] Add/update frontend and backend tests for the new behavior.
- [x] Run backend and frontend verification suites.

## 2026-04-03 - Remove kb_first shortcut and rely on graph KB tool

- [x] Remove endpoint-level `kb_first` branching from `/agent/query` and `/agent/stream`.
- [x] Update the default agent prompt to prefer `mock_fintech_knowledge_base` for FAQ/policy-style questions.
- [x] Remove obsolete `kb_first` source/tests and replace them with graph-path endpoint coverage.
- [x] Run backend verification: `mypy`, `ruff check .`, and `uv run python -m pytest tests/ -v`.

## 2026-04-03 - Admin demo hover notice and register keepMeFor selector

- [x] Add an Admin hover/focus explainer on the landing CTA while preserving `/admin` navigation.
- [x] Replace the hardcoded register `keepMeFor` value with a visible `7d` / `30d` / `90d` selector.
- [x] Add frontend tests for the Admin explainer and the register `keepMeFor` flow.
- [x] Run frontend verification: `npm run typecheck`, `npm run build`, `npm run test`.

## 2026-04-03 - Inspect admin trace explorer latency computation

- [x] Identify the backend source of trace-level latency and event timestamps for admin trace detail payloads.
- [x] Verify whether ingestion or persistence drops node/span timing information before the admin explorer reads it.
- [x] Trace the frontend mapping, parsing, and rendering path for node durations and explain why `0.0s` appears.
- [x] Write the investigation review with exact files and likely root causes.

## Review

- Canonicalized the public `tool_call` SSE payload as JSON on the backend so it matches the rest of the stream contract instead of relying on Python-style dict serialization.
- Hardened the chat stream hook to accept both canonical JSON tool-call events and legacy parsed payloads, which restores `message.toolCalls` and makes the `Raw tool calls` toggle actually appear in live chat.
- Added narrow regression coverage for tool-call propagation in the chat stream hook and for the backend public SSE formatter contract.
- Removed the duplicate inline trace inspector from `/admin/traces`, leaving the page as the catalog/tabs surface only.
- Re-enabled the shared `GlobalTraceSheet` on `/admin/traces`, so `?traceId=` now opens the same right-side sheet used elsewhere in admin and `Back` consistently clears the param.
- Updated trace page and trace sheet tests to prove the catalog writes `traceId`, the page no longer renders an inline explorer, and the shared sheet owns close/back behavior on `/admin/traces`.
- Verified the affected scopes with backend `mypy`, `ruff`, and full `pytest`, plus frontend `typecheck`, `build`, and full `test`.
- Removed the endpoint-level `kb_first` bypass from `/agent/query` and `/agent/stream`, so former shortcut questions now use the normal graph and existing local KB tool.
- Created the prep checkpoint commit `5f20507` (`chore: checkpoint current worktree before vite 8 migration`) before starting the toolchain upgrade.
- Upgraded the frontend toolchain to Vite `8.0.3`, `@vitejs/plugin-react` `6.0.1`, `@tailwindcss/vite` `4.2.2`, and Vitest `4.1.2`, and added a frontend Node engine floor of `>=22.12.0`.
- Standardized Node 22.22.2-compatible automation by updating the frontend CI workflow and the production Docker builder image, and removed `--legacy-peer-deps` from the Docker install path.
- Migrated the Vite chunking config from the removed Rollup object-form `manualChunks` to Rolldown `codeSplitting.groups` while preserving the existing named vendor chunk intent for router, query, charts, admin, and Radix dependencies.
- Updated the frontend README to document the Node 22.12+ local runtime expectation.
- Verified the migrated frontend with `npm ci`, `npm run typecheck`, `npm run test`, `npm run build`, `npm run verify:deprecation`, `npm run build:warning-check`, and a successful `docker build -f Dockerfile.prod -t mft-frontend-vite8-test .`.
- Strengthened the default agent prompt to prefer `mock_fintech_knowledge_base` for FAQ and policy-style servicing questions while still allowing normal tool flow when KB results are insufficient.
- Deleted the obsolete `kb_first` module/tests, added graph-path regression coverage for query/stream, and verified the backend with mypy, ruff, and the full pytest suite.
- Added a hover/focus-only Admin demo notice while keeping the CTA as a normal `/admin` link.
- Replaced the hardcoded register `keepMeFor` value with visible `7d`, `30d`, and `90d` options, preserving the selection through OTP request, resend, and verification.
- Added landing-page and register-dialog coverage, then verified the frontend with `npm run typecheck`, `npm run build`, and `npm run test`.
- Investigated the admin trace explorer latency path across runtime trace collection, PostgreSQL persistence, admin analytics retrieval, and frontend rendering; backend persists trace latency plus per-event timestamps, while the explorer currently drops timestamps and hard-codes child-node durations to `0.00`.
- Fixed admin trace back/close routing so removing `traceId` returns to `/admin/traces` without auto-reselecting the first trace, and normalized trace-link generation through a shared helper.
- Replaced the trace explorer `X` with a `Back` button, preserved event timestamps into the trace viewer, and switched child-node latency rendering from fake `0.0s` values to real durations or `—` when unavailable.
- Set the default new-session chat pair to Groq `openai/gpt-oss-120b`, and kept that explicit default pair consistent across session init, session-config fallback, and frontend fallback state.
- Added a `Raw tool calls` toggle beside `Reasoning` in assistant bubbles, with expandable raw tool name, call ID, and output rendering.
- Added regression coverage for trace routing, trace parsing/viewmodel timing, helper-based trace links, raw tool calls, and default session values, then verified backend and frontend with the full repository-native checks.
- Identified that duplicate OTP rows were caused by duplicate real tool executions inside a single graph turn, not by a duplicated UI render.
- Added a shared backend execution-policy registry so side-effect tools have one source of truth for same-turn dedupe and transport-retry safety.
- Updated the LangGraph execution loop to reuse the first result for duplicate same-turn side-effect calls instead of invoking the tool again.
- Updated the MCP wrapper to preserve automatic reconnect retry only for read-only tools; side-effect tools now fail fast instead of silently repeating after a transport error.
- Hardened the main agent prompt plus side-effect tool descriptions so the model is explicitly told not to repeat the same OTP/document/logout action in a single turn after success.
- Added focused backend regression tests for graph dedupe, MCP retry policy, and streamed public tool-call behavior, then verified the backend with `uv run mypy ...`, `uv run ruff check .`, and `uv run python -m pytest tests/ -v` (`118 passed`).

## 2026-04-03 - Inspect frontend trace explorer close and routing behavior

- [x] Identify the shared trace pane component and its close callback behavior.
- [x] Identify the admin traces page selection and close behavior for `traceId`.
- [x] Identify any global trace sheet routing or search-param logic that can own `traceId`.
- [x] Document why closing can leave `?traceId=` in the URL and which code path causes it.
