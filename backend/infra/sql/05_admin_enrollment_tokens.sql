-- ─────────────────────────────────────────────────────────────────────────────
-- admin_enrollment_tokens — single-use, time-limited, email-bound tokens
-- that let a super-admin invite a new admin without handling their password.
--
-- Lifecycle:
--   1. Super-admin POSTs to /agent/admin/enrollment/tokens with {email, role}.
--      The server generates a random plaintext token, stores only its SHA-256
--      hash, and returns the plaintext ONCE in the response. The plaintext is
--      never logged and never retrievable again.
--   2. Super-admin hands the plaintext (or redeem URL) to the new admin via a
--      secure out-of-band channel.
--   3. New admin opens /admin/enroll?token=<plaintext>. The FE calls
--      GET /agent/admin/enrollment/tokens/{plaintext} to display metadata
--      (email, role, expiry). Plaintext never leaves the URL.
--   4. New admin sets their own password + confirms TOTP setup. FE calls
--      POST /agent/admin/enrollment/tokens/{plaintext}/redeem atomically:
--      validates the token → creates admin_users row → marks token consumed.
--
-- Security:
--   - Plaintext is stored only in the issuer's response + the redeem URL.
--     The DB holds only sha256(plaintext), so a DB dump cannot be used to
--     impersonate pending enrollments.
--   - consumed_at is set atomically by consume_token_atomic() to block
--     double-redemption races.
--   - expires_at bounds the window of attack surface (default 24h, max 168h).
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS admin_enrollment_tokens (
    token_hash       TEXT        PRIMARY KEY,                    -- sha256 hex of plaintext
    email            TEXT        NOT NULL,
    role             TEXT        NOT NULL CHECK (role IN ('admin', 'super_admin')),
    created_by       UUID        NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at       TIMESTAMPTZ NOT NULL,
    consumed_at      TIMESTAMPTZ,
    consumed_ip      TEXT,
    CHECK (expires_at > created_at),
    CHECK (consumed_at IS NULL OR consumed_at >= created_at)
);

-- Lookup unconsumed tokens by email (list pending invites in the admin UI).
CREATE INDEX IF NOT EXISTS idx_admin_enrollment_tokens_email_pending
    ON admin_enrollment_tokens (email)
    WHERE consumed_at IS NULL;

-- Sweep expired, unconsumed tokens (periodic cleanup via cron / manual DELETE).
CREATE INDEX IF NOT EXISTS idx_admin_enrollment_tokens_expires_pending
    ON admin_enrollment_tokens (expires_at)
    WHERE consumed_at IS NULL;
