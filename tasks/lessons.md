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

### 14. LangGraph astream_events fires nested tool events from adapter wrappers
**Trigger:** MCP tools wrapped by `mcp_manager.py` create nested Runnables (outer StructuredTool wrapper → inner MCP adapter tool). `astream_events(v2)` fires `on_tool_end` for BOTH, each with a different `run_id` and potentially different `data` shapes. A `hash(output)` dedup failed because `extract_tool_output()` produced different strings from each level.
**Rule:** When deduplicating LangGraph stream events for wrapped/nested Runnables, use `parent_ids` to identify inner runs — skip `on_tool_end` events whose `parent_ids` overlap with tracked `on_tool_start` run_ids. Do not rely on output string equality across hierarchy levels.
