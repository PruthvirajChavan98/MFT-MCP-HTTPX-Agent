# Task Plan

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
