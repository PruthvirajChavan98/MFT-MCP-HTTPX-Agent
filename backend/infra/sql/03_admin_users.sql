-- =============================================================================
-- 03_admin_users.sql — Admin identity table
--
-- Backs the /admin login flow. Before this migration, the single super-admin
-- lived in env vars (SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD_HASH /
-- SUPER_ADMIN_TOTP_SECRET_ENC). After this migration, all admins — including
-- the super-admin — live in this table. The app seeds the env-backed super-
-- admin into this table on startup (idempotent).
--
-- Idempotent: every statement uses IF NOT EXISTS. Safe to re-run.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS admin_users (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email                   TEXT        NOT NULL CHECK (email = lower(email)),
    password_hash           TEXT        NOT NULL,
    totp_secret_enc         TEXT        NOT NULL,
    is_super_admin          BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at              TIMESTAMPTZ NULL,
    created_by_admin_id     UUID        NULL REFERENCES admin_users(id) ON DELETE SET NULL
);

-- Partial unique index on active (non-revoked) rows only. Revoked rows keep
-- their email so the audit trail stays intact, and a new admin can re-use
-- the email after revocation.
CREATE UNIQUE INDEX IF NOT EXISTS ux_admin_users_email_active
    ON admin_users (email)
    WHERE revoked_at IS NULL;

-- Index for fast "is there still at least one active super-admin?" checks,
-- used by the revoke endpoint to prevent locking the system out.
CREATE INDEX IF NOT EXISTS ix_admin_users_super_active
    ON admin_users (is_super_admin)
    WHERE revoked_at IS NULL AND is_super_admin = TRUE;

-- ── updated_at trigger ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION admin_users_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_admin_users_updated_at ON admin_users;
CREATE TRIGGER trg_admin_users_updated_at
    BEFORE UPDATE ON admin_users
    FOR EACH ROW
    EXECUTE FUNCTION admin_users_touch_updated_at();
