# Admin Enrollment Runbook

This runbook covers enrolling **non-super-admin** users (role `admin`, not
`super_admin`). For the one-time bootstrap of the first super-admin, see
[super-admin-enrollment.md](./super-admin-enrollment.md).

Two flows are supported. **Prefer tokens** — the super-admin never handles the
new admin's password.

---

## Flow A — Enrollment token (recommended)

Schema: `backend/infra/sql/05_admin_enrollment_tokens.sql`.
Endpoints: `backend/src/agent_service/api/admin_enrollment/routes.py`.

1. **Super-admin issues a token**
   `/admin/admins` → **Generate enrollment link**. Pick email + role + TTL
   (default 24 h, max 168 h). Modal returns a plaintext token and a redeem URL.
   The server stores only `sha256(token)`; this is the only time the plaintext is
   retrievable.
2. **Hand the redeem URL to the new admin**
   Use a secure channel (Signal, 1Password, signed email). The URL is
   `https://<host>/admin/enroll?token=<plaintext>`.
3. **New admin redeems the link**
   Opens the URL on any device. The page:
   - Shows "Setting up account for \<email\>".
   - Client-side generates a base32 TOTP secret (never leaves the browser until
     redeem), displays the secret + `otpauth://` URI to scan/paste into an
     authenticator.
   - New admin enters their own password + the 6-digit code, submits.
   - Server verifies code vs. secret, Argon2id-hashes password,
     Fernet-encrypts TOTP secret, creates `admin_users` row, marks token
     `consumed_at`, issues JWT cookies — the new admin lands authenticated at
     `/admin`.
4. **Atomic single-use guarantee** — `consume_token_atomic` wraps the check +
   consume + row-create in one Postgres txn with `SELECT … FOR UPDATE`. Two
   concurrent redeems serialize and exactly one wins (other gets `409
   consumed`). Same pattern as `revoke_if_not_last_super`.

### Failure modes

| HTTP | code | meaning |
|------|------|---------|
| 404  | `not_found`  | token doesn't match any row (bad paste, or never issued)  |
| 410  | `expired`    | `expires_at` elapsed; ask super-admin for a fresh token  |
| 409  | `consumed`   | already redeemed, or an active admin already exists for that email |
| 400  | `invalid_totp` | submitted code doesn't match submitted secret — rescan |

### Rate limits

- **Issue** (super-admin): `0.083 rps` (5/min) per caller. `RATE_LIMIT_ADMIN_ENROLLMENT_ISSUE_RPS`.
- **Public lookup + redeem**: `0.033 rps` (2/min) per IP. `RATE_LIMIT_ADMIN_ENROLLMENT_PUBLIC_RPS`.
  Tight limits + SHA-256 preimage resistance are the only barriers to token
  enumeration on the public surface.

---

## Flow B — Direct create (legacy, still supported)

Use only when the token flow is unavailable (e.g. air-gapped onboarding where
the new admin can't reach the public `/admin/enroll` URL).

## Background

Since the admin-users migration (`backend/infra/sql/03_admin_users.sql`):

- All admin identities — super-admin included — live in the `admin_users`
  Postgres table.
- The env-backed super-admin (`SUPER_ADMIN_EMAIL` /
  `SUPER_ADMIN_PASSWORD_HASH` / `SUPER_ADMIN_TOTP_SECRET_ENC`) is seeded
  into the table on first boot and is never re-consulted afterward. The
  env vars stay in `.env` purely as the bootstrap source.
- JWT `sub` is the admin's UUID, not the literal `"super_admin"` string.
  Roles (`["admin"]` or `["admin", "super_admin"]`) come from the row's
  `is_super_admin` column.

## Who can enroll

Only an authenticated super-admin with a **fresh MFA session** (last TOTP
verified within 5 minutes) can create or revoke admin accounts.

## Enrollment flow — step by step

### 1. Super-admin opens the enrollment UI

Log in at `https://mft-agent.pruthvirajchavan.codes/admin/login`,
complete TOTP challenge, and navigate to **Admin Users** in the sidebar
(the link only renders when your session holds the `super_admin` role).

### 2. Click **Add Admin**

A modal opens asking for:

- **Email** — must be unique among active (non-revoked) admins.
- **Initial password** — minimum 12 characters. Click **Generate** for a
  crypto-random 20-character alphanumeric one.

Submit. The UI wraps the call in `withMfa(...)` — if your MFA is stale,
the MFA prompt modal appears; verify and the create call auto-retries.

### 3. Secret pane — copy these three values once

On success the modal switches to a **one-time** pane with three copy rows:

1. **Initial password** — the value you just submitted.
2. **TOTP secret (base32)** — raw 32-character base32 secret.
3. **TOTP otpauth URI** — `otpauth://totp/mft-agent-admin:<email>?secret=...&issuer=mft-agent-admin`.
   Paste into any authenticator app or render as a QR code.

> **The server will never show these again.** If the super-admin closes
> the modal before copying them, the only recovery is to revoke the admin
> and re-enroll with a fresh password + secret.

A warning `window.confirm` guards the close button if nothing has been
copied yet.

### 4. Hand the credentials to the new admin out of band

Recommended channels (pick whichever matches your threat model):

- 1Password / Bitwarden shared vault entry.
- Signal message (auto-deletes).
- In-person handoff.

**Do not** paste the secrets into email, Slack, or any issue tracker.

### 5. New admin completes their first login

They open `/admin/login`, enter the email + initial password, then the
current TOTP code from their authenticator. On success they land on the
admin dashboard. Their sidebar **will not** show "Admin Users" (that nav
entry is super-admin-only).

MFA-gated operations (`require_mfa_fresh` on the backend) reject plain
admins with `403 code=not_super_admin`, so they cannot escalate.

## Revocation flow

1. In **Admin Users**, click the trash icon on the row to revoke.
2. `window.confirm` surfaces the email + a note that in-flight sessions
   will die on the next refresh cycle.
3. Confirm. The UI optimistically removes the row; on backend success the
   admin is soft-deleted (`revoked_at = now()`).

Constraints the backend enforces:

- **Cannot revoke yourself** — `400 code=cannot_revoke_self`.
- **Cannot revoke the last active super-admin** — `400 code=last_super_admin`.
  (Reach this state only if you have multiple super-admins and are
  deleting them all; the self-guard usually fires first.)

The row remains in the table with `revoked_at` set, so the audit trail
stays intact. A future admin with the same email can be enrolled
immediately — the partial unique index is on active rows only.

## FAQ

### How do I reset a plain admin's password or TOTP?

You cannot. Revoke the admin, then re-enroll them with a fresh password
and TOTP secret. A "rotate credentials for existing admin" endpoint is
deliberately out of scope for now — it would require either:

- A recovery link flow (one-time enrollment token), or
- Super-admin typing the new password / holding the new TOTP secret.

Either adds threat-model surface that is not justified for the current
user count.

### What happens to active sessions when I revoke an admin?

- Their access token (15 min TTL) continues to work until it expires.
- Their next refresh attempt is rejected with `401 code=invalid_refresh`
  because `/admin/auth/refresh` re-fetches the user row and detects
  `revoked_at IS NOT NULL`.
- So the maximum window between revoke and full lockout is ~15 minutes.
  Acceptable for this threat model; tune by shortening `JWT_ACCESS_TTL_SECONDS`.

### Can I create another super-admin?

Not through the UI. `POST /agent/admin/admins` always sets
`is_super_admin=false`. If you genuinely need a second super-admin
(recommended for bus-factor), run the seed script against the DB directly
or SQL-upgrade an existing admin:

```sql
UPDATE admin_users
SET is_super_admin = TRUE, updated_at = now()
WHERE id = '<admin-uuid>' AND revoked_at IS NULL;
```

### The POST response contained secrets — is the request body logged?

The server logs `admin_users.create: admin=<id> created by=<caller_id>`
— no email, no password, no TOTP secret. `requestJson` on the frontend
does not log request/response bodies either. The raw secrets live only
in the super-admin's browser tab during the modal's lifetime.

## Related reading

- Backend migration: `backend/infra/sql/03_admin_users.sql`
- Repo: `backend/src/agent_service/api/admin_users/repo.py`
- Routes: `backend/src/agent_service/api/admin_users/routes.py`
- Frontend page: `Chatbot UI and Admin Console/src/features/admin/pages/AdminUsersPage.tsx`
- Frontend modal: `Chatbot UI and Admin Console/src/features/admin/pages/AdminUsersCreateModal.tsx`
- Project-wide admin-auth conventions: `.cursor/rules/admin-auth.mdc`
