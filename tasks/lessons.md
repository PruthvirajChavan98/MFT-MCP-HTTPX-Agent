# Lessons Learned

## 2026-04-11 (Phase 5c — Vitest v4 gotchas)

### L6. `vi.mock()` is hoisted — factory cannot reference top-level `const`
**Trigger:** Phase 5c's `AdminAuthProvider.test.tsx` declared `const requestJsonMock = vi.fn()` + `class TestApiError` at the top of the file, then passed them to `vi.mock('@/shared/api/http', () => ({ requestJson: requestJsonMock, ApiError: TestApiError }))`. First test run failed with `ReferenceError: Cannot access 'TestApiError' before initialization` because Vitest hoists `vi.mock()` calls to the top of the file, ABOVE `const` / `class` declarations.
**Rule:** Any symbol referenced inside a `vi.mock()` factory must be declared via `vi.hoisted(() => ({ ... }))` which runs in the hoisted slot. Pattern:
```typescript
const { requestJsonMock, TestApiError } = vi.hoisted(() => {
  class TestApiError extends Error { /* ... */ }
  return { requestJsonMock: vi.fn(), TestApiError }
})

vi.mock('@/shared/api/http', () => ({
  requestJson: requestJsonMock,
  ApiError: TestApiError,
}))
```
**Why:** Vitest's module transformer moves `vi.mock(...)` calls to the top of the file during transform, so the factory runs before the rest of the module body. Only `vi.hoisted()` is guaranteed to run before `vi.mock()` factories.

### L7. `vi.fn()` without a generic is not assignable to typed props
**Trigger:** Phase 5c's `MfaChallenge.test.tsx` used `let onVerified = vi.fn()` to mock a `() => void` prop. `npm run typecheck` failed with `error TS2322: Type 'Mock<Procedure | Constructable>' is not assignable to type '() => void'` even though the tests passed at runtime. Vitest v4 infers `vi.fn()` as a broader callable-or-constructable type that TypeScript's structural checking rejects for simple function-type slots.
**Rule:** When assigning a Vitest mock to a typed function prop, use an explicit generic: `vi.fn<() => void>()` or `vi.fn<(arg: string) => Promise<void>>()`. The type variable matches the function signature being mocked. Reset line: `onVerified = vi.fn<() => void>()`.
**Why:** Vitest v4's type definitions made `vi.fn()` broader to support both callable and class-mock scenarios. Without a generic, the inferred type is too wide to satisfy specific `onVerified: () => void` prop contracts. Explicit generic narrows the mock type back to the target shape.

## 2026-04-11 (admin auth plan, Phase 3b — integration test gotchas)

### L4. httpx.Cookies.set(name, value, domain=..., path=...) stores but does NOT send
**Trigger:** Phase 3b integration tests for the admin auth router needed to reset the client jar and rebuild it with specific cookies (tampered refresh, replayed old refresh, etc.). Using `client.cookies.set("mft_admin_rt", value, domain="test", path="/admin/auth")` stored the cookie in the jar (visible via `dict(client.cookies)`) but httpx refused to SEND it on subsequent requests — the server saw "no cookie" and returned 403 csrf_mismatch.
**Rule:** When rebuilding an `httpx.AsyncClient` cookie jar manually, call `client.cookies.set(name, value)` WITHOUT `domain=`/`path=` kwargs. Specifying `domain="test"` triggers `http.cookiejar`'s domain-match check which then fails for `base_url="http://test"` (the domain-specified flag marks the cookie as "sent only to explicit subdomain matches"). Defaults work; explicit domain/path arguments break things.
**Why:** `httpx.Cookies.set` wraps stdlib `http.cookiejar.Cookie` which has `domain_specified=True` when you pass `domain=`. The cookie-jar matching algorithm then requires the request host to match the stored domain per RFC 6265 §5.1.3 — and "test" vs "test" may fail because of initial-dot handling or the request URL's effective host. Omitting the kwarg puts the cookie in "accept-always" mode.
**How to apply:** When writing httpx-based FastAPI integration tests that need to manipulate the cookie jar directly, do:
```python
client.cookies = httpx.Cookies()
client.cookies.set("mft_admin_at", access_value)       # no domain/path
client.cookies.set("mft_admin_rt", refresh_value)      # no domain/path
client.cookies.set("mft_admin_csrf", csrf_value)       # no domain/path
response = await client.post("/some/path", headers={"X-CSRF-Token": csrf_value})
```
Diagnose cookie-not-sent issues with a standalone `python -c "..."` script that prints `dict(client.cookies)` after the rebuild and calls an endpoint that echoes what it sees.

### L5. Deprecation gate will fail on httpx per-request `cookies=dict`
**Trigger:** First-pass tests used `await client.post(path, cookies=cookies)` which worked functionally but emitted `DeprecationWarning: Setting per-request cookies=<...> is being deprecated`. The deprecation gate (`PYTHONWARNINGS='error::DeprecationWarning'`) turned this into an error — 20 warnings across one test file.
**Rule:** For `httpx.AsyncClient` in tests, use the client-level cookie jar (`client.cookies`) exclusively. Never pass `cookies=` as a per-request kwarg. Login writes cookies to the jar automatically via response handling; subsequent requests read from the jar automatically.
**How to apply:** Helper functions return only the CSRF token (captured from the jar after login); per-request code only needs the CSRF header. For tests that need to simulate a specific cookie state (tampering, replay), assign a fresh `client.cookies = httpx.Cookies()` and rebuild.

## 2026-04-10 (admin + super-admin auth plan, Phase 0)

### L1. PyJWT 2.12.x enforces ≥32-byte HS256 keys via `InsecureKeyLengthWarning`
**Trigger:** Phase 0 smoke test used `'secret'` (6 bytes) for HS256 round-trip and pyjwt 2.12.1 emitted `InsecureKeyLengthWarning: The HMAC key is 6 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.` This warning is NEW in 2.12.x (it wasn't emitted by 2.10.x in the repo's transitive state).
**Rule:** Any `JWT_SECRET` config value must be validated at app startup to be ≥32 bytes. The enrollment runbook MUST specify secret generation via `python -c "import secrets; print(secrets.token_urlsafe(32))"` (which produces a 43-char URL-safe string ≈ 32 bytes of entropy). Phase 2's `admin_jwt.py` must add a length assertion in the module-load sanity check and the Phase 1 config module must reject short secrets on boot, not at first-use.
**Why:** RFC 7518 §3.2 requires HS256 keys to be at least the hash output size (256 bits = 32 bytes). Weak keys are brute-forceable. Letting a short secret into prod would violate the "zero deprecation warnings" rule and create a real security weakness.

### L2. Don't run `uv sync` without knowing the dev-dep dual-system trap in `backend/`
**Trigger:** Ran `uv sync` and it pruned ruff, black, isort, fakeredis, pytest-cov, mkdocs, etc. — because those live in `requirements-dev.txt` (fuller set) while `pyproject.toml` `[dependency-groups] dev` only has mypy, pytest, pytest-asyncio, pre-commit (minimal set). `make test` and `make lint` broke until `make install-dev` was re-run.
**Rule:** In `backend/`, always follow `uv sync` with `make install-dev` OR skip `uv sync` entirely and use `make install-dev` (which runs `uv pip install -r requirements-dev.txt` on top). Better long-term fix is to consolidate the two lists into `pyproject.toml` `[dependency-groups] dev` so `uv sync` alone is sufficient — that's a pre-existing cleanup I should propose to the user separately.
**Why:** The two-system setup is a pre-existing repo design bug. My task is admin auth, not dev-dep cleanup, so the fix is to recognize the trap and not trigger it, not to refactor it here.

### L3. `uv run` falls back to a different Python env when run outside the project directory
**Trigger:** After session resume, my cwd was at repo root (not `backend/`). Running `uv run python -c "..."` from repo root picked up some stale/system Python env and reported `pyjwt 2.11.0` / `cryptography 46.0.4` / no `argon2-cffi` — none of which matched the lockfile state in `backend/`.
**Rule:** Every `uv run` command in this repo MUST be prefixed with `cd /path/to/backend && ` or equivalent. Never trust `uv run` at repo root because there's no `pyproject.toml` there and uv's env discovery silently falls back to a different interpreter.
**Why:** The Makefile's `make` targets all `cd` to `backend/` implicitly, but ad-hoc `uv run` commands don't. Using `make` targets whenever possible avoids this entire category of bug.

## 2026-04-02

### 1. ALWAYS re-read after editing
**Trigger:** Broke `TraceTree.tsx` JSX by removing elements without verifying closing tags survived.
**Rule:** After EVERY edit, re-read the file. No exceptions. The Edit Integrity Protocol exists for a reason.

### 2. Don't assume user intent — ask
**Trigger:** Interpreted "agent kill switch" as admin toggle. User meant the red stop button + backend cancellation. Interpreted "groq is openai compatible" as "skip guardrails-ai". User meant "yes, use it — Groq is compatible."
**Rule:** When the user's answer is ambiguous, ask a follow-up. Don't project meaning onto short responses.

### 3. Database migrations must be automated
**Trigger:** Created `mft` user and `mft_security` database manually, then forgot about schema migrations. Admin pages showed "relation eval_traces does not exist."
**Rule:** Any infrastructure dependency must be automated in compose (init containers, migration scripts). If a teammate can't `docker compose up` and have everything work, it's broken.

### 4. Understand nginx proxy behavior before setting endpoint paths
**Trigger:** Registered download endpoint as `/api/download/{token}`. Nginx strips `/api/` prefix. Agent received `/download/{token}` — 404.
**Rule:** Read the nginx config BEFORE deciding endpoint paths. The proxy layer changes what the backend sees.

### 5. Streaming tokens can't be un-sent
**Trigger:** FOLLOW_UPS tag leaked into chat because tokens stream incrementally. Backend `extract_follow_ups()` runs after streaming — too late.
**Rule:** If you need to suppress content from a stream, either buffer it or handle it on the frontend when the structured event arrives.

### 6. Run ALL verification commands, not just some
**Trigger:** Skipped `npm run test`, `mypy`, or `ruff` on multiple changes.
**Rule:** CLAUDE.md specifies exact verification commands. Run all of them. Every time. No shortcuts.

### 7. Update this file after every correction
**Trigger:** User corrected me multiple times in one session and I never captured the lessons until called out.
**Rule:** The moment a correction happens, add it here. Don't batch.

## 2026-04-03

### 8. Lock interaction semantics before implementing CTA behavior
**Trigger:** The user narrowed the Admin CTA behavior from click-popup to hover-only notice with normal navigation.
**Rule:** For CTA changes, explicitly lock hover, click, and focus behavior before implementation. Do not assume a popup should intercept navigation unless the user says so.

### 9. Use tasks/todo.md and tasks/lessons.md — not just TodoWrite
**Trigger:** Used the floating TodoWrite widget instead of writing plans to `tasks/todo.md`. Never updated `tasks/lessons.md` after the session.
**Rule:** CLAUDE.md mandates: (1) Write plans to `tasks/todo.md` with checkable items. (2) Update `tasks/lessons.md` after every correction. The TodoWrite widget is supplementary — it does NOT replace the repo files. Both must be kept in sync.

### 10. Do not infer provider from an ambiguous model ID when setting product defaults
**Trigger:** The product default needed to be Groq `openai/gpt-oss-120b`, but the existing model-name inference logic would classify that ID as OpenRouter.
**Rule:** For product defaults and first-run session bootstrapping, store an explicit provider/model pair. Keep string-based provider inference only as a fallback for legacy or partially saved configs, not for default UX.

## 2026-04-04

### 11. Verify end-to-end event delivery, not just component toggles
**Trigger:** I added a `Raw tool calls` UI toggle and component test, but the live chat still never showed it because the backend/front-end SSE contract was not canonical for `tool_call`.
**Rule:** For streamed UI features, verify the full producer -> parser -> state -> render path. A component-only test is not enough when the real failure surface is the event contract.

### 12. Avoid duplicate owners for the same detail UI
**Trigger:** The traces experience stayed broken because `/admin/traces` rendered its own inline inspector while the admin shell also owned a global trace sheet keyed off the same `traceId`.
**Rule:** When a route param drives a shared detail view, there must be exactly one component responsible for fetching and rendering that detail. Do not split ownership between page-local and global containers.

### 13. Distinguish duplicate execution from duplicate external delivery
**Trigger:** The raw tool-call panel showed `generate_otp` twice, but the user received only one OTP. I needed to separate agent-side duplicate execution from downstream delivery dedupe/rate limiting before choosing the fix.
**Rule:** For side-effect bugs, verify whether the duplication is in agent execution, transport retry, or downstream delivery. Fix the execution layer first; do not assume a single external side effect means the upstream call only happened once.

### 16. Trace the full data path before changing a type
**Trigger:** Changed `_utc_iso_now()` from returning `str` to `datetime` to fix asyncpg. Didn't check that the same value flows into `json.dumps(r)` two lines later — which crashes on `datetime`. Required a second fix.
**Rule:** When changing a return type, grep for ALL consumers of that value. A type change in one place breaks every downstream consumer that assumed the old type. Trace the full path: creation → storage → serialization → API response.

### 15. Write tests for new code — passing old tests means nothing
**Trigger:** Added eval status endpoint, useEvalStatus hook, and eval badge without writing a single test. Claimed "66/66 tests passed" as if that proved correctness — it only proves I didn't break existing code.
**Rule:** New code gets new tests. Period. "Existing tests pass" is not a verification of new functionality.

### 16. Frontend spinners need a terminal backend contract
**Trigger:** `Evaluating...` stayed on screen because the backend exposed an open-ended `pending` state with no terminal unavailable/skipped/failed lifecycle, while the frontend rendered a completion-oriented spinner.
**Rule:** If the UI shows progress for async backend work, the backend contract must include terminal non-success states. Never leave product UX dependent on an unbounded `pending`.

### 17. Reuse visual primitives, not live behavior, in admin replay surfaces
**Trigger:** `/admin/conversations` reused the live `ChatMessage` component and inherited eval polling, feedback controls, and other live-only behavior that broke transcript replay.
**Rule:** Admin replay/read-only views may share rendering primitives, but they must not inherit live hooks, polling, or interaction semantics from production chat widgets.

### 18. Boolean env parsing must be consistent across the repo
**Trigger:** `.env` used `ENABLE_LLM_JUDGE=1`, but one config path parsed booleans as `== "true"` while the rest of the repo accepted `1/true/yes`, silently disabling the inline judge.
**Rule:** Use one truthy parsing convention everywhere for environment booleans. A flag that looks enabled in `.env` must not be disabled by parser inconsistency.

### 14. LangGraph astream_events fires nested tool events from adapter wrappers
**Trigger:** MCP tools wrapped by `mcp_manager.py` create nested Runnables (outer StructuredTool wrapper → inner MCP adapter tool). `astream_events(v2)` fires `on_tool_end` for BOTH, each with a different `run_id` and potentially different `data` shapes. A `hash(output)` dedup failed because `extract_tool_output()` produced different strings from each level.
**Rule:** When deduplicating LangGraph stream events for wrapped/nested Runnables, use `parent_ids` to identify inner runs — skip `on_tool_end` events whose `parent_ids` overlap with tracked `on_tool_start` run_ids. Do not rely on output string equality across hierarchy levels.

## 2026-04-05

### 19. Validate audit claims before acting on them
**Trigger:** Received two comprehensive architectural audits. Every claim was confirmed, but the severity and fix approach differed from what the audit suggested (e.g., FastMCP wraps sync tools in thread pool, not directly on event loop).
**Rule:** Always validate audit claims against the actual codebase before planning remediation. Audit severity often depends on runtime details (like FastMCP's `asyncio.to_thread()` for sync tools) that change the urgency and approach.

### 20. Separate-process services cannot share in-process singletons
**Trigger:** Plan initially assumed mcp_service could reuse agent_service's async Redis pool and HTTP client. Investigation showed mcp_service runs as a separate process via `main_mcp.py`.
**Rule:** Before planning infrastructure unification, verify whether services share a process or run independently. Check entrypoints (`main_*.py`), Procfiles, and docker-compose.

### 21. pytest-asyncio strict mode requires @pytest_asyncio.fixture for async fixtures
**Trigger:** Rewrote test_session_store.py with `@pytest.fixture async def` — all 7 tests errored with `PytestRemovedIn9Warning` about async fixtures not being handled.
**Rule:** When `asyncio_mode = "strict"` in pyproject.toml, async fixtures MUST use `@pytest_asyncio.fixture`, not `@pytest.fixture`.
