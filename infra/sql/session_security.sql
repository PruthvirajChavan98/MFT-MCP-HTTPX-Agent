-- Session Security Schema (PostgreSQL 15+)
-- Features:
-- 1) Time-series optimized IP telemetry (partitioned + BRIN + hot-path indexes)
-- 2) Multi-tenant row-level security
-- 3) Encrypted sensitive columns via pgcrypto

CREATE SCHEMA IF NOT EXISTS security;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Application helpers
CREATE OR REPLACE FUNCTION security.current_tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
    SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid;
$$;

CREATE OR REPLACE FUNCTION security.current_column_key()
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT NULLIF(current_setting('app.column_key', true), '');
$$;

-- Raw event stream (time-series)
CREATE TABLE IF NOT EXISTS security.session_ip_events (
    tenant_id uuid NOT NULL,
    session_id text NOT NULL,
    user_id text,
    event_time timestamptz NOT NULL DEFAULT now(),

    ip inet NOT NULL,
    ip_encrypted bytea,

    device_fingerprint_hash bytea,
    country_code text,
    latitude double precision,
    longitude double precision,

    distance_km double precision,
    velocity_kmh double precision,

    risk_score numeric(4,3) NOT NULL,
    risk_decision text NOT NULL,
    risk_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,

    request_path text,
    user_agent text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,

    PRIMARY KEY (tenant_id, event_time, session_id, ip)
) PARTITION BY RANGE (event_time);

-- Current + next month partitions (rotate with cron or migration runner)
CREATE TABLE IF NOT EXISTS security.session_ip_events_2026_02
    PARTITION OF security.session_ip_events
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE TABLE IF NOT EXISTS security.session_ip_events_2026_03
    PARTITION OF security.session_ip_events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- Time-series and hot-path indexes
CREATE INDEX IF NOT EXISTS idx_session_ip_events_tenant_session_time
    ON security.session_ip_events (tenant_id, session_id, event_time DESC);

CREATE INDEX IF NOT EXISTS idx_session_ip_events_tenant_user_time
    ON security.session_ip_events (tenant_id, user_id, event_time DESC);

CREATE INDEX IF NOT EXISTS idx_session_ip_events_risk_high
    ON security.session_ip_events (tenant_id, risk_score DESC, event_time DESC)
    WHERE risk_score >= 0.7;

CREATE INDEX IF NOT EXISTS brin_session_ip_events_time
    ON security.session_ip_events USING BRIN (event_time);

-- Session latest snapshot (fast read for validator)
CREATE TABLE IF NOT EXISTS security.session_security_state (
    tenant_id uuid NOT NULL,
    session_id text NOT NULL,
    user_id text,

    last_seen_at timestamptz NOT NULL,
    last_ip inet,
    last_ip_encrypted bytea,

    last_country_code text,
    last_latitude double precision,
    last_longitude double precision,

    canonical_device_fingerprint_hash bytea,
    last_risk_score numeric(4,3) NOT NULL DEFAULT 0,
    last_decision text NOT NULL DEFAULT 'allow',

    updated_at timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (tenant_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_session_security_state_tenant_user
    ON security.session_security_state (tenant_id, user_id);

-- Optional helper trigger to refresh updated_at
CREATE OR REPLACE FUNCTION security.touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_session_security_state_updated_at ON security.session_security_state;
CREATE TRIGGER trg_session_security_state_updated_at
BEFORE UPDATE ON security.session_security_state
FOR EACH ROW EXECUTE FUNCTION security.touch_updated_at();

-- Row-level security for multi-tenancy
ALTER TABLE security.session_ip_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE security.session_security_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_session_ip_events_tenant_iso ON security.session_ip_events;
CREATE POLICY p_session_ip_events_tenant_iso ON security.session_ip_events
USING (tenant_id = security.current_tenant_id())
WITH CHECK (tenant_id = security.current_tenant_id());

DROP POLICY IF EXISTS p_session_security_state_tenant_iso ON security.session_security_state;
CREATE POLICY p_session_security_state_tenant_iso ON security.session_security_state
USING (tenant_id = security.current_tenant_id())
WITH CHECK (tenant_id = security.current_tenant_id());

-- Least privilege role example
-- CREATE ROLE app_rw NOINHERIT;
-- GRANT USAGE ON SCHEMA security TO app_rw;
-- GRANT SELECT, INSERT, UPDATE ON security.session_ip_events TO app_rw;
-- GRANT SELECT, INSERT, UPDATE ON security.session_security_state TO app_rw;

-- Encryption helper example for app writes:
-- INSERT ... ip_encrypted = pgp_sym_encrypt(ip::text, security.current_column_key());
