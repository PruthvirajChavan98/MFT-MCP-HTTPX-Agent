## Backend Workspace

Use this directory for backend code, tests, and Python tooling.

### Common Commands

```bash
make help
make dev
make test
make lint
make format
```

### Docker Compose

Compose files are maintained at repository root as the single source of truth:

- `../docker-compose.yml`
- `../docker-compose.local.yml`

`make docker-*` and `make local-*` from this directory are wired to those root compose files and root `.env`.

### Admin Authentication

The admin console is gated by JWT session cookies. Legacy `X-Admin-Key` and the
`ADMIN_AUTH_ENABLED` flag were retired in Phase 6g/6h. JWT is now the only path.

**Required env vars** (fail-closed validation at boot — server refuses to start if any is missing):

- `JWT_SECRET` — ≥32 bytes (RFC 7518 §3.2). HS256 only.
- `FERNET_MASTER_KEY` — Fernet-generated key for TOTP secret at-rest encryption.
- `SUPER_ADMIN_EMAIL` — the JWT `sub` claim; typed at login.
- `SUPER_ADMIN_PASSWORD_HASH` — argon2id hash. **In `.env`, every `$` must be `$$`-escaped** to dodge Docker Compose's env_file variable-interpolation. See `docs/runbooks/super-admin-enrollment.md` for the gotcha.
- `SUPER_ADMIN_TOTP_SECRET_ENC` — Fernet-encrypted base32 TOTP secret.

Generate all five via `python scripts/enroll_super_admin.py` (interactive; uses `getpass` so the password never enters shell history).

**Dependency chain** (declared in `src/agent_service/api/admin_auth.py`):

- `require_admin` — valid access JWT + `admin` role.
- `require_super_admin` — above + `super_admin` role.
- `require_mfa_fresh` — above + `mfa_verified_at` within 5 min (`JWT_MFA_FRESHNESS_SECONDS`).

All admin endpoints use at least `require_admin`. Super-admin mutations use `require_mfa_fresh`, which returns `403 {detail: {code: "mfa_required"}}` when the JWT is MFA-stale — the frontend's `MfaPromptProvider` catches that response and prompts the user for a fresh TOTP code.

**Rate limits** (per-IP, fail-closed on Redis outage):

- `POST /admin/auth/login` — 5 req/min
- `POST /admin/auth/mfa/verify` — 5 req/min (separate from the 5-strike TOTP lockout in `admin_totp.py`, which revokes access for 15 min on 5 consecutive bad codes)

**Testing admin endpoints.** Use `httpx.ASGITransport` + `AsyncClient` + `fakeredis.aioredis.FakeRedis(decode_responses=True)`. See `tests/test_admin_auth_endpoints.py` for the full pattern (including the rate-limiter stub fixture needed to avoid event-loop leaks across tests).

**Related runbooks:**

- `../docs/runbooks/super-admin-enrollment.md` — initial setup / credential rotation
- `../docs/runbooks/admin_auth_mfa_recovery.md` — post-lockout recovery
- `../.cursor/rules/admin-auth.mdc` — implementation conventions for adding new admin endpoints
