# Super-Admin Enrollment

**Audience:** ops / operator setting up a new deployment or rotating the super-admin credential
**Estimated time:** 5 minutes (the `$$`-escape step is where people get stuck — read carefully)

---

## Prerequisites

1. Repo cloned at `/path/to/mft-mcp-httpx-agent`
2. Backend venv installed: `cd backend && uv sync`
3. Docker stack up: `docker compose --env-file .env -f compose.yaml up -d` (containers `mft_agent`, `mft_mcp`, `mft_frontend_prod`)
4. Root `.env` file exists (copy from `.env.example` if not)
5. An authenticator app ready on your phone (Google Authenticator, Authy, 1Password, Bitwarden)

---

## Step 1 — Run the enrollment script

```bash
cd backend
source .venv/bin/activate
python scripts/enroll_super_admin.py
```

The script will prompt for:

- **Email** — any real-looking email. Becomes the JWT `sub` claim; you type this at login.
- **Password** — 12+ characters, entered twice via `getpass` (no shell history leak).

It prints:

1. An `otpauth://` URI for your authenticator app
2. The raw base32 TOTP secret (fallback if QR scan fails)
3. A block of 6 env-var assignments (5 required + 1 legacy `ADMIN_AUTH_ENABLED` line that should be **ignored** — the flag was retired in Phase 6h)

**Register the TOTP now.** Scan the `otpauth://` URI or paste the raw base32 secret into your authenticator. Verify 6-digit codes are appearing before you move on.

---

## Step 2 — Paste the env vars into `.env`

**This is where people break things.** Argon2 password hashes contain `$` characters — Docker Compose's `env_file` processor treats `$` as variable substitution and silently consumes them. If you paste the hash as-is, the container will load a mangled hash and every login will return `invalid_credentials`.

**Fix: double every `$` in the `SUPER_ADMIN_PASSWORD_HASH` line.**

Enrollment output:
```
SUPER_ADMIN_PASSWORD_HASH=$argon2id$v=19$m=65536,t=3,p=4$SALT$HASH
```

What goes into `.env`:
```
SUPER_ADMIN_PASSWORD_HASH=$$argon2id$$v=19$$m=65536,t=3,p=4$$SALT$$HASH
```

One-liner for quick transformation (adjust the raw line):

```bash
# Replace the line in .env after enrollment
sed -i 's|^SUPER_ADMIN_PASSWORD_HASH=.*|SUPER_ADMIN_PASSWORD_HASH=<your-hash-with-$$-escaped>|' .env
```

Or edit `.env` in your editor and do a find-replace of `$` → `$$` within the hash line only. Don't touch any other `$` in the file.

The other 4 vars (`JWT_SECRET`, `FERNET_MASTER_KEY`, `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_TOTP_SECRET_ENC`) do **not** contain `$` — paste them as-is.

**Do not paste `ADMIN_AUTH_ENABLED=true`.** The flag was retired in Phase 6h; adding it is harmless but misleading.

### Sanity-check

```bash
# The container should see the full hash literal after Docker Compose interpolation:
docker exec mft_agent printenv SUPER_ADMIN_PASSWORD_HASH
# Expected: $argon2id$v=19$m=65536,t=3,p=4$SALT$HASH  (single $, not $$ — that's the interpolation output)
```

If you see something like `=19=65536,t=3,p=4/SALT+/HASH` (stripped), you forgot the `$$`-escape. Go back and fix the `.env` line.

---

## Step 3 — Restart the containers

```bash
docker compose --env-file .env -f compose.yaml up -d --force-recreate agent mcp
```

`--force-recreate` is required — plain `restart` does **not** re-read `env_file` for existing containers.

Watch the first 30 s of agent logs for a clean boot:

```bash
docker compose --env-file .env -f compose.yaml logs --tail 30 agent
```

Expected last lines:
- `[src.agent_service.core.app_factory] INFO: ✅ PostgreSQL pool initialized`
- `[src.agent_service.core.app_factory] INFO: ✅ Security runtime initialized`
- `[INFO] Application startup complete.`

If you see a `ValueError: admin auth config missing required env vars: [...]` — you missed a var. Paste it from the enrollment output and re-run Step 3.

If you see a `ValueError: JWT_ALGORITHM=... is not in the allowed set` — someone set `JWT_ALGORITHM` to something other than HS256/HS384/HS512 in `.env`. Unset it (the default HS256 is correct) and re-run Step 3.

---

## Step 4 — Browser verification

Open your admin URL in an **incognito / private window** (stale cookies from any prior session will interfere):

1. Navigate to `<your-admin-url>/admin/login`
2. Email: the value you typed in Step 1
3. Password: the value you typed in Step 1
4. The frontend signals MFA is required — the TOTP modal opens automatically
5. Enter the 6-digit code from your authenticator app
6. You should land on `/admin` with the dashboard rendering

Test a super-admin mutation (add/delete/edit an FAQ on the Knowledge Base page). Since you just verified MFA, it should succeed immediately. Wait 5+ minutes and try again — the mutation will return `403 mfa_required` and the TOTP modal will reopen automatically. Enter the code and the mutation retries.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `{"code": "invalid_credentials"}` on every login | `$` not escaped to `$$` in `.env` password hash | Step 2: double every `$` in `SUPER_ADMIN_PASSWORD_HASH` |
| `ValueError: admin auth config missing required env vars` at boot | Missed one of the 5 vars | Step 2: paste all 5 from enrollment output |
| `ValueError: JWT_ALGORITHM=... not in allowed set` at boot | Operator override misconfigured | Unset `JWT_ALGORITHM` in `.env` (default HS256 is correct); only HS256/HS384/HS512 allowlisted |
| Login succeeds but no TOTP prompt appears | Frontend cached stale JS bundle from before Phase 7a | Hard refresh the browser (Cmd+Shift+R / Ctrl+Shift+R) or open incognito |
| `{"code": "mfa_locked_out"}` | 5 consecutive bad TOTP attempts in < 5 min | See `docs/runbooks/admin_auth_mfa_recovery.md` |
| `Fernet: InvalidToken` at TOTP verify | `FERNET_MASTER_KEY` mismatch between enrollment and `.env` | Re-paste `FERNET_MASTER_KEY` from enrollment output; restart containers |
| Cloudflared tunnel returns 502 | Stale upstream cache | `docker restart mft_cloudflared_prod` |

---

## Rotation

To rotate any single credential without re-enrolling from scratch:

- **Password only:** re-run the enrollment script, replace only the `SUPER_ADMIN_PASSWORD_HASH` line in `.env` (with `$$`-escape), restart.
- **TOTP secret only:** re-run enrollment, replace only `SUPER_ADMIN_TOTP_SECRET_ENC` in `.env`, register the new QR in your authenticator, restart. Old TOTP codes stop working immediately.
- **JWT signing secret:** replace `JWT_SECRET` in `.env` (any 32+ byte `secrets.token_urlsafe(32)` value), restart. All existing admin sessions invalidate immediately — admins must re-login.
- **Fernet master key:** do NOT rotate in-place; it invalidates `SUPER_ADMIN_TOTP_SECRET_ENC`. Full re-enrollment required.
- **Email (`sub`) change:** re-run enrollment with the new email; replace `SUPER_ADMIN_EMAIL` + `SUPER_ADMIN_PASSWORD_HASH` + `SUPER_ADMIN_TOTP_SECRET_ENC` (all depend on the new email); restart. Existing sessions invalidate on next refresh.

Any rotation is an audit-log-worthy event. Record: timestamp, which credential rotated, reason.

---

## Related docs

- `docs/runbooks/admin_auth_mfa_recovery.md` — post-lockout recovery (3 options)
- `.cursor/rules/admin-auth.mdc` — implementation conventions for new admin endpoints
- `CLAUDE.md` §5 — project-level admin-auth gotchas
- `tasks/lessons.md` L24 — the `$$`-escape bug this runbook exists to prevent
