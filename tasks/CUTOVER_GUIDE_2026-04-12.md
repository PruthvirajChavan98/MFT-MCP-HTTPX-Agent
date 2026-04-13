# Cutover Guide — 2026-04-12

Tomorrow you're landing the admin-auth + Phase M1 work that's already committed. This guide walks you through it linearly. **Do the steps in order.** Don't skip Step 0.

Legend: 🧑 = you do this in a terminal/browser. 🤖 = you tell the agent and it does it.

---

## 🧑 Step 0 — Verify the rollback snapshot (30 seconds)

Before touching anything live, confirm the 2026-04-11 pre-cutover snapshot is still on disk. If it's gone, you can't roll back safely — stop and re-snapshot.

```bash
cd /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent

docker image inspect mft_agent:snapshot-2026-04-11T17-52-52Z         --format '{{.Id}}'
docker image inspect mft_mcp:snapshot-2026-04-11T17-52-52Z           --format '{{.Id}}'
docker image inspect mft_frontend_prod:snapshot-2026-04-11T17-52-52Z --format '{{.Id}}'
ls -la snapshots/2026-04-11T17-52-52Z/SNAPSHOT_INFO.md
```

**Expected:** three `sha256:…` lines + a file listing. **If any errors:** STOP. The snapshot was garbage-collected. Re-snapshot the currently-running containers before proceeding (see `snapshots/2026-04-11T17-52-52Z/SNAPSHOT_INFO.md` for the recipe).

---

## 🧑 Step 1 — Tag the rollback anchor, make sure the stack is up (30 seconds)

```bash
cd /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent
git tag pre-phase-6-cutover HEAD

# If the local stack isn't already up:
cd backend && make local-up && cd ..
```

`git tag pre-phase-6-cutover` is your code-level rollback anchor (separate from the Docker image snapshot). Worst case: `git reset --hard pre-phase-6-cutover` reverts the repo in one command.

---

## 🧑 Step 2 — Run the enrollment script (2 minutes)

This mints the 5 secrets (JWT signing key, Fernet master key, password hash, TOTP secret, email) that the new admin-auth backend requires at boot.

```bash
cd /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent/backend
source .venv/bin/activate
python scripts/enroll_super_admin.py
```

You'll be prompted for:
- **Email** — any real-looking string (it's the JWT `sub` claim; you type it at login)
- **Password** — 12+ chars, entered twice

The script prints:
- A block of 5 env vars (`JWT_SECRET`, `FERNET_MASTER_KEY`, `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD_HASH`, `SUPER_ADMIN_TOTP_SECRET_ENC`)
- An `otpauth://…` URI for your authenticator app
- A raw base32 TOTP secret (fallback if the URI scan fails)

**Register the TOTP now.** Scan the `otpauth://` URI in Google Authenticator / Authy / 1Password / whatever you use, or paste the raw base32 secret manually. You'll need the 6-digit code in Step 5.

**If the script fails on import:** run `make install-dev` and retry. Phase 0 added `pyotp`/`argon2-cffi`/`cryptography.fernet` as direct deps but a partial venv could be missing them.

---

## 🧑 Step 3 — Paste the env vars into `backend/.env` (1 minute)

Open the file in your editor and paste the block the script emitted:

```bash
cd /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent
$EDITOR backend/.env
# Paste the 5 vars. Save.
```

Do **not** add `ADMIN_AUTH_ENABLED=true` — the flag was deleted in Phase 6h and JWT enforcement is now unconditional at the code level. Adding it is harmless but looks confusing on re-reads.

---

## 🧑 Step 4 — Restart the backend containers (1 minute)

```bash
cd /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent

docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local \
    restart agent-local mcp-local

# Watch the first 30 log lines for clean boot
docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local \
    logs --tail 30 agent-local mcp-local
```

**Expected:** agent-local logs show FastAPI starting on `:8000`. mcp-local shows FastMCP starting on `:8050`. **No** `_validate_admin_auth_config` errors, **no** `KeyError: 'JWT_SECRET'`, **no** `Fernet master key missing`.

**If agent-local refuses to boot:** the failure mode is always "missing env var". Re-read the Step 3 paste vs what the script emitted. The names must match exactly.

Also restart the frontend if you built new bundles (not required if you haven't touched the UI since 2026-04-11):

```bash
docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local \
    restart frontend-prod
```

---

## 🧑 Step 5 — Browser verification (2 minutes)

Open `http://localhost:<agent-local-port>/admin/login` in a private/incognito window (to avoid stale cookies from before the cutover).

1. Enter the email + password from Step 2
2. Enter the 6-digit TOTP from your authenticator when prompted
3. You should land on `/admin` with the dashboard rendering
4. Click through: Knowledge Base, Guardrails, Traces — all read paths should load without 401/403
5. **Try a mutation on Knowledge Base** (add an FAQ, edit an FAQ, delete an FAQ)
   - **Expected:** 403 `mfa_required` with a plain error toast
   - **This is correct behavior** until Phase 7a wires the MFA modal
   - If the mutation succeeds, something's wrong — Super Admin MFA freshness is supposed to gate all KB mutations

### If something breaks

| Symptom | Likely cause | Action |
|---|---|---|
| `/admin/login` returns 404 | frontend-prod wasn't restarted, stale bundle | restart `frontend-prod` |
| Login succeeds but redirected back to login | JWT cookie not set — `Secure` flag on localhost without HTTPS | check `backend/.env` for `JWT_COOKIE_SECURE=false` in local profile |
| Login 500s with `Fernet` error | `FERNET_MASTER_KEY` not exactly what the script emitted | re-paste from script output |
| Login 401s with `invalid credentials` | password mismatch between typed and hashed at enrollment | re-run enrollment in fresh terminal |
| Dashboard loads but Knowledge Base page errors | mcp-local not restarted, agent calling stale tool schemas | restart `mcp-local` |
| Any admin page shows `X-Admin-Key required` | browser is on an old frontend bundle | hard-refresh / incognito |

### Rollback if Step 5 reveals a showstopper

```bash
# 1. Revert the code tree
git reset --hard pre-phase-6-cutover

# 2. Revert the runtime (images)
docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local \
    stop agent-local mcp-local frontend-prod
docker tag mft_agent:snapshot-2026-04-11T17-52-52Z         mft_agent:latest
docker tag mft_mcp:snapshot-2026-04-11T17-52-52Z           mft_mcp:latest
docker tag mft_frontend_prod:snapshot-2026-04-11T17-52-52Z mft_frontend_prod:latest
docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local \
    up -d agent-local mcp-local frontend-prod
```

Zero data loss. Redis/Postgres/Milvus volumes are untouched by any of this.

---

## 🤖 Step 6 — Tell the agent to start Phase 7a (MFA modal wiring)

Once Step 5 is green, open a fresh agent session and say:

> **"ops cutover done, start Phase 7a"**

The agent will read `tasks/todo.md` Step 4 and wire 5–6 files for the MFA prompt modal. Before it writes code it will ask you 4 clarifying questions — answer them and it'll execute:

- **Q1**: Use shadcn `<Dialog>` or `<AlertDialog>` for the modal shell?
  - Default recommendation: **`<AlertDialog>`** — semantically matches "you must do this to continue"
- **Q2**: `withMfa` retry count — retry once or allow multiple with backoff?
  - Default recommendation: **once**, no backoff. TOTP is user-entered; retry-loops don't help when the failure mode is "user typed wrong digits"
- **Q3**: Cancel path — reject with a typed `MfaCancelled` error or generic `Error`?
  - Default recommendation: **typed `MfaCancelled`** — lets call sites branch cleanly in TanStack Query error handlers
- **Q4**: Phase 7a file split — approve the 6-file §2 override OR split into 7a-infra + 7a-consume?
  - Default recommendation: **approve the 6-file override**. The provider + consumer split is artificial because the consumer (KB page) can't be validated until the provider is mounted

After Phase 7a: verify the MFA modal works by re-trying the KB mutation from Step 5. The toast should be replaced by a modal, and after TOTP entry the mutation should succeed on retry.

---

## 🤖 Step 7 — Phase 7b (documentation) and Phase M1 follow-up

When Phase 7a is green, say:

> **"proceed to Phase 7b"**

The agent will write 4 markdown files (`CLAUDE.md` update, `.cursor/rules/admin-auth.mdc`, `backend/README.md` admin-auth section, `docs/operations/super-admin-enrollment.md` runbook). All doc-only; no runtime changes.

Then say:

> **"do the M1 follow-up"**

The agent will add a single line to the LangGraph agent system prompt hinting that `search_knowledge_base` is the preferred tool for product/policy questions. Quick sanity-check in a chat session after deploy.

---

## Done criteria (end of tomorrow)

- Step 5 browser verification passes end-to-end
- Phase 7a tests green (`npm run test` shows 137 passed)
- Phase 7b docs merged
- Phase M1 hint in system prompt
- Nothing stale in `backend/src` vs the running containers (build-and-redeploy cycle is natural after Phase 7a touches the frontend)
- `git log --oneline` shows a clean commit trail for the day
- Snapshot images and the `snapshots/2026-04-11T17-52-52Z/` directory still in place

---

## Carry-forward (do NOT start tomorrow)

Tracked for visibility only; each is its own standalone task.

- **WAHA API key rotation** — parked per user instruction. Standing item for pre-production.
- **E2E browser tests for admin auth flow** — no Playwright coverage for login → MFA → mutation → logout. Unit tests cover each piece; full flow is untested in a real browser.
- **`search_knowledge_base` description tuning** — empirical after first real chat sessions reveal under/over-selection.
- **Dev-dep dual system consolidation** — `pyproject.toml [dependency-groups] dev` vs `requirements-dev.txt`. See `tasks/lessons.md` L2. Pre-existing; not admin-auth-related.

---

## Reference — what was already built (no action needed, for context)

- **Phases 0–6h**: full JWT session auth stack with opaque-refresh-token family rotation, argon2id password hashing, TOTP via pyotp, Fernet-encrypted secret-at-rest, CSRF double-submit cookies, Redis-backed rate limits, super-admin MFA freshness gate on KB mutations. ~2,000 backend LOC + ~1,500 frontend LOC across ~30 files, 253 backend tests green, 129 frontend tests green.
- **Phase M1**: moved KB semantic search tool into the mcp_service process (was locally registered in agent_service). New `backend/src/mcp_service/kb_search.py` (~100 lines), registered via `@mcp.tool` with full tool description in `tool_descriptions.yaml`. LangGraph agent auto-discovers it post-restart.
- **Pre-cutover snapshot** (Step 0 above): three Docker images + ~375 MB on-disk copy of `/app` trees, all provenance metadata in `snapshots/2026-04-11T17-52-52Z/SNAPSHOT_INFO.md`.

History lives in `tasks/todo.md` below the pickup plan if you need to dig into any phase's rationale.
