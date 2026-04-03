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
