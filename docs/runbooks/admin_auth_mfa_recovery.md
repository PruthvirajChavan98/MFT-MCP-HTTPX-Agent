# Admin MFA Lockout Recovery

**Audience:** on-call operator / super-admin holder
**Trigger:** super-admin cannot log in; `/admin/auth/mfa/verify` returns `403 mfa_locked_out`
**Estimated time:** 2–3 minutes

---

## When this runbook applies

The admin console enforces a 5-strike TOTP lockout. After 5 consecutive failed MFA attempts against a given `sub`, Redis stores an `admin_auth:locked:<sub>` marker with a 15-minute TTL. During that window, every further `POST /admin/auth/mfa/verify` (even with a correct TOTP) returns:

```json
{"code": "mfa_locked_out", "message": "account locked due to failed MFA attempts"}
```

Use this runbook when:

- You are the legitimate super-admin and you locked yourself out (e.g., typed the TOTP wrong 5 times on a stale authenticator clock)
- A security event triggered the lockout (attacker burned the 5 attempts) and you need to restore admin access **after** confirming the threat is contained

Do **not** use this runbook to skip MFA entry. The lockout is the policy; this is the escape hatch when the policy fires on the operator.

---

## Option A — Wait the TTL out (preferred, 15 minutes)

The lockout marker expires automatically. If nothing else is going wrong and you can tolerate a 15-minute wait:

1. Put down the authenticator app.
2. Re-sync your device time (settings → date/time → auto).
3. Wait 15 minutes.
4. Retry login + TOTP.

No runbook action needed. Skip to "After recovery" below.

---

## Option B — Immediate reset via Redis (requires shell access)

Use only when downtime is unacceptable. Requires SSH to the host running `agent-local` (or equivalent), or `docker exec` onto the Redis container.

### Step 1 — identify the locked sub

The `sub` is the super-admin identifier from `SUPER_ADMIN_EMAIL` in `backend/.env`. If you have multiple admins, you may need to check which one is locked.

```bash
# From repo root, discover which admins have lockout marks
docker exec redis redis-cli KEYS 'admin_auth:locked:*'
```

Expected output: one line per locked sub, e.g. `admin_auth:locked:super_admin`.

### Step 2 — clear the lockout keys

```bash
# Replace <sub> with the identifier from step 1 (without the admin_auth:locked: prefix)
SUB=super_admin
docker exec redis redis-cli DEL "admin_auth:locked:${SUB}" "admin_auth:lockout:${SUB}"
```

Both keys should be deleted:
- `admin_auth:locked:<sub>` — the 15-minute absolute-lockout marker
- `admin_auth:lockout:<sub>` — the 5-min sliding failure counter (delete so the next genuine failed attempt starts from 0, not wherever it left off)

Expected output: `(integer) 2` (two keys deleted). If the output is `0` or `1`, the lockout has already expired or was already partially cleared — verify no other operator already ran this step.

### Step 3 — confirm unlock

```bash
docker exec redis redis-cli EXISTS "admin_auth:locked:${SUB}"
# → (integer) 0
```

Retry login + TOTP in the admin console. It should work on the first correct attempt.

---

## Option C — Rotate the TOTP secret (only if the TOTP device is compromised)

Use only when the authenticator device itself is lost, stolen, or suspected compromised. This invalidates the old secret and generates a new one — all prior TOTP codes are immediately worthless.

### Step 1 — re-run enrollment

```bash
cd /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent/backend
source .venv/bin/activate
python scripts/enroll_super_admin.py
```

The script prompts for email + password and emits a fresh env var block including a new `SUPER_ADMIN_TOTP_SECRET_ENC`. Register the emitted `otpauth://` URI in a new authenticator.

### Step 2 — paste the new env vars into `backend/.env`

Replace at minimum the `SUPER_ADMIN_TOTP_SECRET_ENC` line. You can preserve `JWT_SECRET`, `FERNET_MASTER_KEY`, `SUPER_ADMIN_EMAIL`, and `SUPER_ADMIN_PASSWORD_HASH` if only the authenticator device was compromised (not the credentials).

### Step 3 — restart agent-local

```bash
cd /home/pruthvi/projects/mock-ai/mft-mcp-httpx-agent
docker compose --project-directory "$PWD" --env-file .env -f compose.yaml --profile local \
    restart agent-local
```

### Step 4 — also clear the lockout per Option B

The old lockout marker can persist in Redis and block login even with the new TOTP secret. Run Option B's Step 2 to clear it.

---

## After recovery

**Log the event.** Write one line to an incident log with: timestamp, sub, recovery option used (A / B / C), and root cause (user error / device issue / security event).

**If this was a security event** (attacker burned the attempts): also rotate the `JWT_SECRET`, invalidate all existing admin sessions by restarting agent-local, and audit the last 24 hours of admin actions via the trace store.

**Consider enabling an audit-log hook.** The current MFA failure logging is `log.warning` only — not structured, not durable. If MFA lockout events happen more than once a quarter, the answer is probably to add a persistent audit table, not to run this runbook more often.

---

## Why there is no `POST /admin/auth/mfa/reset-lockout` endpoint

We deliberately did not ship a self-service reset endpoint. Reasons:

- An endpoint gated on JWT session would defeat the lockout (the user can't get a session without MFA).
- An endpoint gated on Fernet master key knowledge would need its own threat model, RBAC, and durable audit log — scope creep that didn't fit the 2026-04-13 remediation cycle.
- The Option B / C paths above require shell access, which is already a stronger credential than an API endpoint would be. The operational friction is a feature, not a bug.

If MFA lockout events start happening weekly, reconsider. Track as a follow-up sprint item rather than a line to hot-patch under pressure.

---

## Implementation references

- `backend/src/agent_service/security/admin_totp.py` — TOTP verification + lockout increment (WATCH/MULTI/EXEC since 2026-04-13, commit `e1a20f9`)
- `backend/src/agent_service/security/admin_totp.py::reset_lockout` — Python-side equivalent of Option B Step 2, called by the enrollment flow
- `tasks/todo.md` — full history of the admin-auth buildout
- `tasks/lessons.md` — operator traps that have bitten us before
