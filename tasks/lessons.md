# Lessons Learned

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
