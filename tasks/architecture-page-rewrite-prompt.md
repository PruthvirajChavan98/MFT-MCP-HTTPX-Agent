# Prompt — Rewrite `/architecture` page so it documents the system at engineering depth, not at marketing depth

## Mission

You are writing the **architecture page** of a real production NBFC fintech AI agent. The current page is a polished landing-style overview (one flow diagram, one data-layer diagram, seven 4-bullet cards). It works as a teaser; it fails as documentation. Rewrite it so that an engineer joining the team — or an external reviewer — could read the page and explain how a user message becomes a CRM call, end to end, without opening the repo.

The page is **public** (no auth), user-facing, linked from the landing CTA. It should feel like a high-quality engineering blog post fused with a system-design doc — dark-mode, dense, scannable, with sequence diagrams, real SSE frames, real container names, real file paths. Treat it as the canonical answer to "how does this thing actually work."

## Where the work lands

- **Replace** `Agent UI and Admin Console/src/features/chat/pages/ArchitecturePage.tsx` (note the spaces in the folder name; quote it in shell).
- **Route** stays `/architecture`, mounted in `Agent UI and Admin Console/src/app/routes.ts:61-79`.
- **No new dependencies** unless you can justify them. The repo already has:
  - React 19 + Vite 8 + TS 5.9
  - Tailwind v4 (dark-mode is the default — `bg-[#0B1121]` is the canonical page background)
  - `motion/react` for animation (use sparingly — content > motion)
  - `lucide-react` for icons
  - `react-router` v7
  - `shadcn/ui` + Radix is already wired — you may use `Accordion`, `Tabs`, `Tooltip`, `Dialog` from there
- If you need Mermaid-style diagrams: render them as **plain inline SVG components you author**. Do not pull a heavyweight diagramming dep just for one page.
- Keep the existing visual language: cyan (`#06b6d4`) primary, indigo + emerald accents, slate-900 surfaces, gradient title headings. Match the polish of the current page; raise only the information density.

## Source of truth (read these first — every fact on the page must trace to one of these)

- `backend/src/main_agent.py`, `backend/src/main_mcp.py` — the two processes
- `backend/src/agent_service/core/app_factory.py:57-159` — DI, AsyncRedisSaver wiring, lifespan
- `backend/src/agent_service/core/config.py` — single source for every env var
- `backend/src/agent_service/core/recursive_rag_graph.py:22-146` — LangGraph state + `DedupToolNode`
- `backend/src/agent_service/api/endpoints/agent_stream.py:414-870` — the stream endpoint, the inline guard at `:467`, the SSE event vocabulary, the cost tracker hook
- `backend/src/agent_service/api/endpoints/sessions.py:21` — `POST /agent/sessions/init`
- `backend/src/agent_service/tools/mcp_manager.py:19-24, 87-150` — `PUBLIC_TOOLS`, `rebuild_tools_for_user`, the `session_id`-omit-from-LLM-schema trick
- `backend/src/mcp_service/server.py:36-178` — all 14 tools and the `_touch()` activity tracker
- `backend/src/mcp_service/tool_descriptions.yaml` — tool catalogue (don't paraphrase; lift the descriptions)
- `backend/src/mcp_service/auth_api.py:59-108` — Basic-Auth bootstrap, `generate_otp` HTTP shape
- `backend/src/mcp_service/core_api.py:62-450` — bearer-token CRM calls for the 8 session-gated tools
- `backend/src/agent_service/eval_store/{embedder,persistence,_bg}.py` — embed-on-commit (PR #7)
- `backend/scripts/{rebuild_eval_results_collection,backfill_trace_embeddings}.py` — the operational ops scripts
- `backend/src/agent_service/api/admin_auth.py` + `Agent UI and Admin Console/src/features/admin/auth/{MfaPromptProvider.tsx,useMfaPrompt.ts}` — the admin MFA flow
- `Agent UI and Admin Console/nginx.conf:13, 42-87` — runtime DNS resolver (PR #20), SSE proxy block, CRM bridge
- `compose.yaml` (root) — the 11-service topology
- `CLAUDE.md` (root) — operational non-negotiables; encode them in the page where relevant (zero deprecation, no patchwork, completion gate)

If you cannot find a fact in code, **omit it**. Do not invent tool names, version numbers, or behaviour.

## Page outline (every section is mandatory unless marked optional)

Each section gets its own anchor + a sticky right-rail TOC at lg+ breakpoints. A subtle "jump to source" link on each section that opens the matching file path on GitHub (use `https://github.com/PruthvirajChavan98/MFT-MCP-HTTPX-Agent/blob/main/<path>`).

### 1. Hero

One paragraph, no fluff. Frame the system in one sentence: "Two FastAPI/FastMCP processes, a LangGraph supervisor, a Postgres-backed checkpointer in Redis, a 14-tool MCP server bridging an external CRM over HTTPS Basic-Auth, all reverse-proxied through Nginx behind a Cloudflare tunnel." Add three at-a-glance stats (tool count: 14, average cold-start latency, request budget per turn — pick honest numbers from `config.py` defaults; if you can't substantiate, drop the stat).

### 2. Topology — the 11-service compose stack

Render the compose stack as a custom inline-SVG topology diagram with:
- Edge: Cloudflare tunnel → Nginx (frontend container) → backend
- Two backend planes: `agent` (port 8000) and `mcp` (port 8050) — show that they are **separate processes** that do not share connection pools (callout from `CLAUDE.md:152`)
- Data plane: `postgres` (with `db-migrate` init container), `redis`, Milvus (external)
- Workers: `shadow_judge_worker`, `geoip_updater`
- Observability: `prometheus`, `alertmanager`, `grafana`
- Networks: `mft_net` and `databases` — show which services live on which

Below the diagram, a `<details>` with a per-service table: image, exposed port, depends_on, healthcheck command, restart policy. Pull every value from `compose.yaml`. No editorialisation.

### 3. Request lifecycle — the canonical sequence diagram

This is the centre of gravity of the page. Render a **vertical sequence diagram** (custom SVG, no Mermaid dep) for one prompt: `"I want to log in. My mobile is 9876543210."`

Lanes (left to right): Browser → Nginx → Agent (FastAPI) → Inline Guard → LangGraph → MCP Server → CRM. For each step, a labelled arrow with the function/file:line that runs it. Annotate every SSE frame the browser receives, in order:

```
event: trace
data: {"trace_id":"cae0c42a4f0e49c2843a75bd1c55a2bf"}

event: reasoning
data: "User wants to log in..."

event: tool_call
data: {"name":"generate_otp","tool_call_id":"...","output":"status,phone_number,message\r\nOTP Sent,9876543210,OTP generated Successfully\r\n"}

event: token
data: " "

event: cost
data: {"total":0.001,"model":"openai/gpt-oss-120b","provider":"groq","usage":{"input_tokens":150,"output_tokens":50}}

event: done
data: {"status":"complete"}
```

These are real frames captured from prod. Reproduce them verbatim in a syntax-highlighted code block (slate-950 surface, monospace, line numbers off, copy button on top-right).

### 4. The inline guard — why some prompts never reach the LLM

`agent_stream.py:467` runs `evaluate_prompt_safety_decision()` **before** the LLM. When `decision="block"`, the stream emits only `trace` + `error: "Prompt violates security policy"` + `done`. Show this alternate trace in a side-by-side comparison with the happy path. Make explicit: this looks identical to a "CRM unreachable" symptom but is a guard decision, not a network failure. (This is exactly the trap one user fell into; documenting it on this page is high-leverage.)

Decision outcomes from code: `pass`, `fail`, `degraded_allow`, `block`. List the 9 high-risk regex patterns from `inline_guard.py` if visible, or link to the file.

### 5. The LangGraph supervisor

A boxed-arrow diagram of the state graph: `llm_step → run_tools → llm_step` looping with `max_iterations=6`. Surface the state shape from `recursive_rag_graph.py:22-28`:

```python
class RecursiveRAGState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int
    max_iterations: int
    tool_execution_cache: dict[str, str]
```

Explain the `DedupToolNode` (line 44-146): same-turn dedupe by tool-name + serialized-args hash, prevents OTPs being re-sent in a single turn. Mention the checkpointer: `AsyncRedisSaver` with 7-day TTL, `thread_id ≡ session_id`.

### 6. The MCP server — tool catalogue

A real table (sortable if you like, but a static `<table>` is fine), one row per tool, columns:

| Tool | Purpose (verbatim from `tool_descriptions.yaml`) | Tier | CRM endpoint hit | Auth |
|---|---|---|---|---|
| `generate_otp` | … | Public | `POST /mockfin-service/otp/generate_new/` | Basic |
| `validate_otp` | … | Public | `POST /mockfin-service/otp/validate_new/` | Basic |
| `is_logged_in` | … | Public | — | — |
| `search_knowledge_base` | … | Public | — (Milvus) | — |
| `dashboard_home` | … | Session-gated | `GET /mockfin-service/home` | Bearer |
| `loan_details` | … | Session-gated | `GET /mockfin-service/loan/details/{app_id}/` | Bearer |
| `foreclosure_details` | … | Session-gated | `GET /mockfin-service/loan/foreclosuredetails/{app_id}/` | Bearer |
| `overdue_details` | … | Session-gated | `GET /mockfin-service/loan/overdue-details/{app_id}/` | Bearer |
| `noc_details` | … | Session-gated | `GET /mockfin-service/loan/noc-details/{app_id}/` | Bearer |
| `repayment_schedule` | … | Session-gated | `GET /mockfin-service/loan/repayment-schedule/{ident}/` | Bearer |
| `download_welcome_letter` | … | Session-gated | `GET /mockfin-service/download/welcome-letter/` | Bearer |
| `download_soa` | … | Session-gated | `POST /mockfin-service/download/soa/` | Bearer |
| `list_loans` | … | Session-gated | … | Bearer |
| `select_loan` | … | Session-gated | … | Bearer |
| `logout` | … | Session-gated | … | Bearer |

(Pull the exact list from `tool_descriptions.yaml`. If 14 isn't the count today, fix the count.)

Below the table, two callout boxes:

- **The `session_id` magic.** `mcp_manager.py:87-111` — Pydantic `create_model()` strips `session_id` from the schema the LLM sees, then the `tool_wrapper` (line 134-150) injects it back before invoking the remote tool. This is *why* the LLM never has to know the session id and *why* tools can't be called cross-session.
- **`PUBLIC_TOOLS` whitelist.** `mcp_manager.py:19-24` — exact set of 4. Everything else requires an `access_token` in the Redis session.

### 7. CRM bridge

Three lines:

1. CRM is **external** at `https://test-mock-crm.pruthvirajchavan.codes`. There is no `crm_api` container in this project's compose.
2. MCP refuses to start without `BASIC_AUTH_USERNAME` and `BASIC_AUTH_PASSWORD` (`auth_api.py:59-68` — `RuntimeError`).
3. Public tools use Basic-Auth; session-gated tools use a Bearer token obtained at `validate_otp` time and stored in the Redis session.

Draw the call as a small swimlane: MCP container → outbound HTTPS:443 → external CRM. Note the `httpx.Timeout(connect=5, read=25, write=10, pool=5)` profile from `auth_api.py:74-98`.

### 8. Frontend flow

Sub-sections:

- **Routing** (`src/app/routes.ts`) — list every top-level route in a two-column table. Mark which require auth.
- **Chat hydration order** (`useChatStream.ts:121-148`) — server checkpointer first, `localStorage` is a write-through cache only, never the reverse. Show the exact hydration sequence as a 4-step list and reference `CLAUDE.md:208`.
- **HTTP layer** (`src/shared/api/http.ts`) — RFC 7807 problem-detail parsing, CSRF double-submit header `X-CSRF-Token`, two custom events: `ADMIN_SESSION_EXPIRED_EVENT` (401) and `ADMIN_MFA_REQUIRED_EVENT` (403 with `detail.code="mfa_required"`).
- **MFA prompt provider** — explain the `withMfa(label, fn)` wrapper in `useMfaPrompt.ts`. When a super-admin mutation returns 403/`mfa_required`, the modal opens, user types TOTP, the original mutation is retried once. Surface the rule from `CLAUDE.md:206`: "Any new admin mutation endpoint chained to `require_mfa_fresh` MUST be called via `withMfa()` on the frontend."

### 9. Three live session walkthroughs

Render each as a horizontally-scrollable card with the request, the SSE transcript, and a one-line outcome. Use real prompts and the actual responses captured below.

**Walkthrough A — Public path: OTP send.** Session `019de474-35f2-7ac2-aabb-684816321519`, prompt `"I want to log in. My mobile is 9876543210."` → `generate_otp` → CRM `OTP Sent`. Outcome: user receives OTP on WhatsApp. *(This was the prompt that proved CRM is reachable end-to-end.)*

**Walkthrough B — Inline-guard block.** Session `019de473-e657-7053-8b27-6b92d8fd3903`, prompt `"Generate an OTP for mobile 9876543210."` → guard `decision=block` → `error: "Prompt violates security policy"`. Outcome: stream ends in three frames; no LLM, no tool, no CRM call. *(The prompt that looks-like-but-isn't a CRM failure.)*

**Walkthrough C — Session-gated path.** Show what `dashboard_home` looks like for an authenticated session: bearer token attached, `_touch(session_id, "dashboard_home")`, `GET /mockfin-service/home`. If you can't get a real bearer-token transcript, mock the SSE frames clearly labelled `// representative` and keep the structure honest.

### 10. Eval store + shadow judge

A short section that lands the recent operational story:

- **PR #7** (`9215882`): unconditional embed-on-commit. Every trace persisted to Postgres now also fires `embed_trace_if_needed()` via the fire-and-forget helper in `eval_store/_bg.py`. Strong-ref set prevents GC of `asyncio.create_task`.
- **PR #6** (`34056fc`): `rebuild_eval_results_collection.py` rebuilds the Milvus collection schema; defensive `id_resolution` in `eval_read.py:eval_vector_search` falls back through `metadata.trace_id` → `metadata.pk` → `doc.id`.
- **`shadow_judge_worker`** consumes the trace queue, scores each trace on Helpfulness / Faithfulness / PolicyAdherence with Groq, mirrors results to `eval_results` for admin trace search.
- Three Milvus collections in play: `kb_faqs`, `eval_traces_emb`, `eval_results_emb`.
- Two operational scripts every operator should know: `make rebuild-eval-results-collection`, `make backfill-trace-embeddings`.

### 11. Security & rate-limiting

A condensed reference card. Six rows max:
- **Inline input guard** (`evaluate_prompt_safety_decision`)
- **Rate limit, fail-closed by default** (`RATE_LIMIT_FAILURE_MODE`, `config.py`)
- **Tor exit-node block** (mention only if confirmed in code)
- **JWT-cookie admin auth + 5-min MFA freshness** (`admin_jwt.py`, `admin_auth.py`)
- **Argon2id password hashes** with the `$$` Compose-escape gotcha from `CLAUDE.md:170-180`
- **Nginx L7 DoS defense** (`limit_req_zone`, `limit_conn_zone`, NAT-safe thresholds)

### 12. Observability

One paragraph + a tiny diagram: agent → Prometheus scrape → Grafana → Alertmanager. List the 4 most useful Grafana panels (only if you can name them from `monitoring/grafana/dashboards/`; otherwise drop this).

### 13. Deployment story

Three lines: `make deploy-prod` rebuilds `agent` and `mcp` images and force-recreates them; nginx uses runtime DNS (`resolver 127.0.0.11 valid=10s`, PR #20) so a recreate doesn't strand stale upstream IPs; Cloudflare tunnel routes `mft-agent.pruthvirajchavan.codes` and `mft-api.pruthvirajchavan.codes` to the frontend and agent containers respectively.

### 14. Operating principles (footer card)

Pull verbatim from `CLAUDE.md` Section 0:
- No patchwork — only permanent solutions.
- Research-backed dependency choices (verified against package registries, not training data).
- Zero deprecation warnings — `make test-deprecation` and `npm run verify:deprecation` must pass.
- End-to-end ownership — fix root causes, not symptoms.

---

## Visual & interaction requirements

- **Right-rail sticky TOC** at `lg:` and above, with active-section highlighting via `IntersectionObserver`.
- **Anchor links** with copy-on-click for every `<h2>` and `<h3>`.
- **Code blocks** rendered with `<pre>` + a hand-rolled syntax highlighter (small Prism setup or `shiki` only if you can prove tree-shaking keeps the bundle under 30 KB gzipped). Each block has a **copy button** that uses `navigator.clipboard.writeText`.
- **SSE-frame blocks** highlight the `event: <name>` line in cyan and the JSON `data:` body in slate.
- **Sequence and topology diagrams**: hand-authored inline SVG components, viewBox-based, accessible (`role="img"`, `<title>`, `<desc>`).
- **`<details>` disclosures** for the long lookup tables (per-service compose detail, full env-var contract).
- **No carousels, no auto-advancing animations.** Motion only on entrance, never on idle.
- **Reduced motion**: respect `prefers-reduced-motion`; skip framer/motion entrance fades when set.
- **Accessibility**: every diagram has a sibling `<details><summary>Text equivalent</summary>…</details>`. Headings are nested correctly; `<main>` wraps content; the back-to-home link is the first focusable element.
- **Print stylesheet** (optional, low priority): hides the TOC and renders sequence diagrams stacked.

## Hard constraints

- **No emojis.** Anywhere. (Repo policy.)
- **No marketing voice.** Write like an engineering blog. "The agent" not "our intelligent assistant." "Two processes" not "a powerful dual-process architecture."
- **No invented facts.** If `tool_descriptions.yaml` lists 14 tools, the table has 14 rows. If you cannot find the version of FastMCP being used, write "FastMCP" without a version, do not guess.
- **No new top-level deps** unless you justify them in a comment block at the top of the file. The bundle for this single page must not exceed +60 KB gzipped over the current page.
- **No `localStorage` reads** from this page. It's stateless documentation.
- **Honour the existing colour tokens** (`#0B1121`, `#111827`, cyan-500, indigo-500, emerald-500, slate-300/400/500/700/800). Don't introduce a new palette.
- **`from __future__ import annotations` is irrelevant here** but the corresponding TS rule is: use TS 5.9 inferred types where reasonable; export only what's used outside the file.
- **Type safety**: zero `any`. Every prop is typed. Every diagram component takes a typed `nodes`/`edges` prop.

## Acceptance criteria

The PR is mergeable when:

1. `npm run typecheck` passes from `Agent UI and Admin Console/`.
2. `npm run test -- --run` passes (add a smoke test that the page renders without errors and that the TOC contains all 14 expected anchor IDs).
3. `npm run build` produces a chunk for the architecture page that is **≤ +60 KB gzipped** vs. the current page's chunk.
4. `npm run verify:deprecation` is green.
5. Lighthouse on the built page: ≥ 95 in Accessibility and Best Practices, ≥ 90 in Performance on a throttled run.
6. Every `<h2>` has a working anchor; every code block has a working copy button; every diagram has an accessible text equivalent.
7. Every external "jump to source" link resolves to a real file in the repo at `main`.
8. The page passes a manual read-through where each numerical claim, tool name, env var, and file path is verifiable in the cited file.
9. **No content was invented.** If something on the page can't be sourced, it's removed.

## Deliverable

A single PR titled `docs(architecture): rewrite /architecture page as engineering-depth system documentation` that touches:

- `Agent UI and Admin Console/src/features/chat/pages/ArchitecturePage.tsx` (rewrite)
- Optional: `Agent UI and Admin Console/src/features/chat/pages/architecture/` for sub-components (diagrams, code-block, TOC, sequence diagram). Co-locate, don't pollute `shared/`.
- `Agent UI and Admin Console/src/features/chat/pages/ArchitecturePage.test.tsx` (smoke test)
- No backend changes, no route changes, no public asset changes beyond any new SVG icons you add to `public/icons/`.

The PR description includes screenshots of the page at sm/md/lg breakpoints and the Lighthouse score.

---

End of prompt. Ground every paragraph in code; if you can't, cut the paragraph.
