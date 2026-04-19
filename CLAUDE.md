# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 0. Identity & Non-Negotiables

I am an AI Engineer at **Anthropic**. Code produced here is reviewed by Gemini Antigravity and Codex — write accordingly.

These are hard constraints, not preferences:

- **No patchwork.** Only permanent, enterprise-grade, production-ready solutions. Temporary fixes are rejected on sight.
- **Research-backed decisions.** Dependency picks, API usage, framework behavior, migrations, and version selections must be verified against current authoritative sources (package registry + official changelog + migration guide). Training data is not a source.
- **Zero deprecation warnings.** Not "reduced" — zero. The repo has explicit deprecation-gated verifiers (`make test-deprecation`, `npm run verify:deprecation`) and they must pass.
- **Blunt corrections.** If the user asks for something non-standard, call it out without sugar-coating and propose the correct approach.
- **End-to-end ownership.** If a task surfaces adjacent broken behavior, fix the root cause — do not leave a trap for the next person.
- **Use the right skill for the job.** Skills are not decorative. Load the matching skill *before* touching code.

For the full operating philosophy (plan mode, mechanical overrides, dependency intelligence gate, subagent strategy, edit-integrity protocol), see [`AGENTS.md`](./AGENTS.md). Those rules apply to Claude Code identically — **do not duplicate them here, follow them there.**

---

## 1. Monorepo Layout

```
mft-mcp-httpx-agent/
├── backend/                              # Python 3.11 / FastAPI / FastMCP / LangGraph
│   ├── src/
│   │   ├── main_agent.py                 # FastAPI entry — port 8000 (agent_service)
│   │   ├── main_mcp.py                   # FastMCP entry — port 8050 (mcp_service, SEPARATE PROCESS)
│   │   ├── agent_service/                # API, core, features, llm, security, tools, worker, eval_store
│   │   ├── mcp_service/                  # FinTech tools, auth_api, core_api, session_store (Redis)
│   │   └── common/                       # Shared utilities
│   ├── tests/                            # pytest suite, asyncio_mode = "strict"
│   ├── Makefile                          # Canonical command surface — ALWAYS prefer make targets
│   └── pyproject.toml                    # uv-managed, Python 3.11+
├── Chatbot UI and Admin Console/         # React 19 / Vite 8 / TS 5.9 / Tailwind v4 / Vitest v4
│   ├── src/{app,features,shared,components}/
│   ├── nginx.conf                        # Production edge (L7 DoS defense, SSE-safe proxy)
│   └── package.json                      # Node >= 22.12
├── compose.yaml                          # SINGLE compose file — all services run without profiles (prod-only deployment)
├── .env / .env.local                     # Env overlays — .env is source of truth; prod uses the same .env
├── .cursor/rules/*.mdc                   # Project-specific rules (ALSO apply to Claude)
├── tasks/todo.md                         # Active plan (checkable items)
├── tasks/lessons.md                      # Append corrections here after every user rebuke
└── AGENTS.md                             # Shared operating philosophy (read it)
```

**Path gotcha:** `Chatbot UI and Admin Console/` contains spaces. Always quote it in shell:
```bash
cd "Chatbot UI and Admin Console"
```

---

## 2. Quick Start

### Backend (from `backend/`)

```bash
make install           # uv sync — install prod deps (uv is mandatory, never pip)
make install-dev       # + dev deps + pre-commit hooks
make dev               # Uvicorn reload, agent_service on :8000
make test              # uv run pytest tests/ -v
make lint              # ruff + pyright (strict target set)
make format            # black + isort + ruff --fix
make quality           # format-check + lint (CI gate)
```

### Frontend (from `"Chatbot UI and Admin Console"/`)

```bash
npm install
npm run dev            # Vite dev server
npm run typecheck      # tsc --noEmit
npm run test           # Vitest
npm run build          # tsc -b && vite build
npm run verify:quality # typecheck + kb-no-any + test + deprecation gate + build-warning gate
```

### Docker (from repo root or `backend/`)

```bash
make localsetup        # validate + start core local stack + run setup checks
make localsetup-full   # + router + monitoring + geoip + edge profiles
make local-up          # just the core: redis postgres mcp-local agent-local
make local-down
make prod-up / make prod-down   # only deployed environment (Cloudflare tunnel → mft-agent.pruthvirajchavan.codes)
make local-validate    # validate compose config before starting
make local-env-audit   # detect duplicate keys in root .env
```

Raw compose invocation (when make targets are insufficient):
```bash
docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local up -d
```

---

## 3. Verification Commands (MANDATORY before claiming done)

**Never report success based on file edits alone.** Run the appropriate verifiers and paste the passing output.

### Backend (from `backend/`)

```bash
# Lint (matches Makefile target — pyright runs on the pinned strict set)
uv run ruff check .
uv run pyright \
    src/agent_service/api/admin.py \
    src/agent_service/features/knowledge_base/repo.py \
    src/agent_service/features/knowledge_base/service.py \
    src/agent_service/features/knowledge_base/faq_pdf_parser.py \
    src/agent_service/security/admin_crypto.py \
    src/agent_service/security/admin_jwt.py \
    src/agent_service/security/password_hash.py \
    src/agent_service/security/admin_totp.py

# Tests
uv run python -m pytest tests/ -v                                # full suite
uv run python -m pytest tests/test_<file>.py::test_<name> -v     # single test
PYTHONWARNINGS='error::DeprecationWarning,error::PendingDeprecationWarning' \
    uv run python -m pytest tests/ -v                            # deprecation gate (make test-deprecation)
```

### Frontend (from `"Chatbot UI and Admin Console"/`)

```bash
npm run typecheck                          # tsc --noEmit
npm run test                               # Vitest
npm run test -- path/to/file.test.ts       # single file
npm run build                              # production build
npm run verify:deprecation                 # test + build under --throw-deprecation
npm run verify:quality                     # full CI gate — run this before declaring done
```

### Completion Gate
A task is not complete until all apply:
- Change implemented, files re-read before edit, edits re-verified after write
- Type-check + lint + tests passed (or explicit reason given for absence)
- Deprecation gate passed if code touches runtime surfaces
- Rename/reference audit performed on signature changes
- No broken callers, imports, or tests remain

---

## 4. Architecture (Big Picture)

### Two separate Python processes
- **`agent_service`** (`main_agent.py`, port 8000): FastAPI app with REST, SSE streaming (`EventSourceResponse`), admin APIs, knowledge base, eval store, LangGraph agent (`AsyncRedisSaver` checkpointer).
- **`mcp_service`** (`main_mcp.py`, port 8050): FastMCP server exposing ~14 FinTech tools via SSE transport. **Runs as a separate process** — it cannot share `agent_service`'s connection pools. Common mistake: assuming they share DI/containers.

### Cross-service contracts
- LangGraph `thread_id` ≡ user `session_id`. Streaming uses `graph.astream_events(..., version="v2")`.
- MCP tools all accept `session_id: str` (agent injects it; Pydantic `create_model()` omits it from LLM-facing schemas). Every tool calls `_touch(session_id, "tool_name")`.
- Public/unauthenticated tools are whitelisted in `PUBLIC_TOOLS` in `agent_service/tools/mcp_manager.py`.
- Tool descriptions live in `mcp_service/tool_descriptions.yaml`, accessed via `_d("tool_name")` — never hardcode descriptions in decorators.

### Configuration discipline (strict)
- All config lives in `backend/src/agent_service/core/config.py`. `os.getenv()` is called **once** there.
- Business logic imports constants from `core.config` — **never** calls `os.getenv()` directly.
- `RATE_LIMIT_FAILURE_MODE=fail_closed` is the default (protects LLM API budgets).
- Single `REDIS_URL` — `get_redis()` takes **no parameters** (prevents pool contamination).

### Factories & singletons
DI pattern: lazy `get_*()` factory functions + backward-compat module-level aliases. Key singletons:
- `app_factory` (FastAPI construction, router mounting, middleware)
- `mcp_manager` (dynamic tool lifecycle, per-user rebuilds via `rebuild_tools_for_user()`)
- `config_manager` (Redis-backed runtime config)
- `model_service` (LLM catalog)
- `event_bus` (internal async pub/sub)
- `AdminAnalyticsRepo` (all 15 admin SQL queries — route handlers orchestrate only)

### Chat history
Backend LangGraph checkpointer is the **source of truth**. Frontend `localStorage` is a write-through cache only — never load from it without hydrating from the server first.

### Frontend structure
- Feature-sliced: `src/features/{chat,admin}/`, `src/shared/`, `src/components/`.
- Path aliases: `@/` → `src/`, `@features/`, `@shared/`, `@components/`.
- HTTP layer (`src/shared/api/http.ts`) parses RFC 7807 Problem Details.
- Routes are lazy-loaded from `src/app/routes.ts`.
- UI uses shadcn/ui + Radix primitives + Tailwind v4 + TanStack Query v5 + React Router v7.

### Nginx edge (`Chatbot UI and Admin Console/nginx.conf`)
- Layer-7 DoS defense via `limit_req_zone` / `limit_conn_zone` with NAT-safe thresholds.
- SSE-safe proxy for `/api/agent/stream`: `proxy_buffering off`, streaming-friendly timeouts. **`/api/agent/stream` must stay above the generic `/api/` location block.**
- **Do not** move business/tenant quotas to Nginx — those stay in FastAPI `RateLimiterManager`.

---

## 5. Project-Specific Gotchas

These are the traps that keep biting. Read before editing.

1. **`mcp_service` is a separate process.** It has its own Redis/HTTP clients. Do not wire it to `agent_service` DI containers.
2. **pytest-asyncio strict mode.** `asyncio_mode = "strict"` in `pyproject.toml` — async fixtures **must** use `@pytest_asyncio.fixture`, not `@pytest.fixture`.
3. **`from __future__ import annotations`** is required at the top of every Python file.
4. **Python 3.11+ typing only**: `dict[str, Any]`, `list[str]`, `T | None`. Do not import `Dict`/`List`/`Optional` for new code.
5. **No `print()` in backend code.** Use `log = logging.getLogger(__name__)`.
6. **No bare `except:`.** Always `except Exception as e:`, log, and chain with `raise ... from e`.
7. **Rate limiter default is fail_closed.** Do not flip to fail_open without explicit justification.
8. **`get_redis()` takes no parameters.** One `REDIS_URL`, one pool.
9. **SSE event contract** is fixed: `reasoning`, `tool_call`, `token`, `cost`, `done`. Do not leak internal LangGraph lifecycle events unless `AGENT_STREAM_EXPOSE_INTERNAL_EVENTS` is set.
10. **`.env` is the source of truth** for Compose interpolation; runtime `env_file` is the repo-root `./.env`. Run `make local-env-audit` and `make backend-env-audit` to detect duplicate keys.
11. **Admin auth is JWT-cookie + 5-min MFA freshness window, backed by the `admin_users` Postgres table.** JWT `sub` is the admin's UUID; `roles` is `["admin"]` or `["admin", "super_admin"]` based on `is_super_admin`. The env-backed `SUPER_ADMIN_*` vars are bootstrap-only — they seed the table on first boot and are never re-consulted. Non-super-admin accounts are enrolled via one of two flows: (a) **preferred — enrollment token**: super-admin clicks *Generate enrollment link* on `/admin/admins` → `POST /agent/admin/enrollment/tokens` → the new admin visits `/admin/enroll?token=...` (public) → they set their own password + TOTP via `POST /agent/admin/enrollment/tokens/:t/redeem`. Tokens are single-use (atomic `SELECT ... FOR UPDATE`), TTL-bounded, stored as `sha256(plaintext)`. (b) **legacy — direct create**: `/admin/admins` → *Add Admin (direct)* → `POST /agent/admin/admins` returns a one-time TOTP secret for out-of-band handoff. Both are covered in `docs/runbooks/admin-enrollment.md`. Super-admin mutations return `403 detail.code="mfa_required"` when stale — the frontend catches via `MfaPromptProvider` + `useMfaPrompt().withMfa(label, fn)` (in `src/features/admin/auth/`). Any new admin mutation endpoint chained to `require_mfa_fresh` MUST be called via `withMfa()` on the frontend. See `.cursor/rules/admin-auth.mdc` for the full conventions.
12. **Docker Compose `$$`-escape trap for admin env-file.** Argon2 password hashes contain `$` (e.g. `$argon2id$v=19$…`). Compose interpolates `$` in `env_file` values as variable substitutions, silently stripping them. In `.env`, every `$` in `SUPER_ADMIN_PASSWORD_HASH` must be doubled to `$$`. Failure symptom: login always returns `invalid_credentials`. See `docs/runbooks/super-admin-enrollment.md` Step 2.
11. **Chat widget hydration:** server checkpointer first, `localStorage` is cache. Never the reverse.
12. **Test mocking:** Redis → `fakeredis.aioredis.FakeRedis(decode_responses=True)`; HTTP → `httpx.MockTransport`; PostgreSQL → stubs. No live network in unit tests.
13. **Float assertions** use `pytest.approx()`.
14. **Reasoning models** (DeepSeek et al.) emit custom `reasoning_content` / `reasoning` streaming fields — extract them explicitly.

---

## 6. Task & Lessons Management

- **`tasks/todo.md`** — active plan with checkable items. Write the plan here *before* implementing. Add a review section when done.
- **`tasks/lessons.md`** — append after every user correction. Each lesson must include: the mistake, the rule to prevent recurrence, the triggering condition.
- Review `tasks/lessons.md` at the start of any non-trivial session.

---

## 7. Test Counts (reference)
- Backend: ~149 tests across ~23 test files
- Frontend: ~92 tests across ~23 test files

A large drop in either count during your changes is a red flag — investigate before committing.

---

## 8. Where to find what
- Meta-rules, plan mode, dependency gate, mechanical overrides → [`AGENTS.md`](./AGENTS.md)
- Project conventions → [`.cursor/rules/*.mdc`](./.cursor/rules) (all apply to Claude too)
- Monorepo boot instructions → [`README.md`](./README.md)
- Backend targets → [`backend/Makefile`](./backend/Makefile)
- Frontend scripts → [`Chatbot UI and Admin Console/package.json`](./Chatbot%20UI%20and%20Admin%20Console/package.json)

---

## Delivery Footer (REQUIRED on every substantive response)

Every substantive response must end with **exactly** this footer. Do not omit fields. Do not leave fields blank.

```
Is it patch work: yes / no
Did you use skills: Yes (which skill) / no (why?)
Did you write test cases and run them: Yes / no (if no, why?)
Did you document changes: Yes / no (if no, why?)
Sequential-thinking: used / blocked / not required
Web search: used / blocked / not required
Validation run: yes / no (if no, why?)
Blockers: <explicit list or `none`>
Residual risks: <explicit list or `none`>
```

### Footer rules

- **`Is it patch work`** must be `no` by default on code tasks. If `yes`, the response must be rejected and reworked before delivery.
- **`Did you use skills`** — skills must be checked and loaded before any code task begins. `no` requires an explicit reason (e.g., no matching skill exists, task is purely conceptual).
- **`Did you write test cases and run them`** — tests must be written AND executed for every code change. `no` requires a hard blocker reason. "not asked" is **not** acceptable.
- **`Did you document changes`** — public interfaces, config changes, and non-obvious decisions must be documented. `no` requires a hard blocker reason.
- **`Sequential-thinking`** — must reflect whether deliberate stepwise planning was materially used. `not required` is only valid for single-step factual lookups.
- **`Web search`** — must be `used` for dependency selection, version pinning, framework behavior, vendor/API docs, changelogs, release notes, deprecation status, or any claim that may have changed post-training. `not required` is **never** valid for version-sensitive work.
- **`Validation run`** — `yes` only if tests, lint, type-checks, build steps, or runtime verification were actually executed and passed. `no` requires an explicit reason.
- **`Blockers`** — name concrete, specific blockers. Vague statements like "environment unknown" are not acceptable — narrow to what exactly is unknown and what is needed to resolve it.
- **`Residual risks`** — enumerate remaining technical uncertainty, compatibility risk, rollout risk, or verification gaps. `none` is only valid when all paths have been verified end-to-end.
- Footer fields must **never** be left blank — every field requires an explicit value or reason.
