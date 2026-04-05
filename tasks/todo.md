# Task Plan

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
