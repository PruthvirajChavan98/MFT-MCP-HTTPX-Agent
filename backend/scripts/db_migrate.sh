#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# db_migrate.sh — Idempotent Postgres bootstrap for the MFT agent service.
#
# Creates the application user, database, and runs all schema migrations.
# Safe to run repeatedly — every statement uses IF NOT EXISTS.
#
# Required env vars (all supplied via compose):
#   POSTGRES_DSN          — admin DSN  (e.g. postgresql://postgresadmin:localpass@postgres:5432/app)
#   MFT_POSTGRES_USER     — app user   (default: mft)
#   MFT_POSTGRES_PASSWORD — app pass   (default: mft_password)
#   MFT_POSTGRES_DB       — app db     (default: mft_security)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

: "${POSTGRES_ADMIN_DSN:?POSTGRES_ADMIN_DSN is required}"
: "${MFT_POSTGRES_USER:=mft}"
: "${MFT_POSTGRES_PASSWORD:=mft_password}"
: "${MFT_POSTGRES_DB:=mft_security}"

SQL_DIR="/app/infra/sql"

echo "==> Waiting for Postgres to accept connections..."
for i in $(seq 1 30); do
    if psql "$POSTGRES_ADMIN_DSN" -c "SELECT 1" >/dev/null 2>&1; then
        break
    fi
    echo "    attempt $i/30..."
    sleep 2
done

echo "==> Creating user '$MFT_POSTGRES_USER' (if not exists)..."
psql "$POSTGRES_ADMIN_DSN" -v ON_ERROR_STOP=0 <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${MFT_POSTGRES_USER}') THEN
        CREATE USER ${MFT_POSTGRES_USER} WITH PASSWORD '${MFT_POSTGRES_PASSWORD}';
    END IF;
END
\$\$;
SQL

echo "==> Creating database '$MFT_POSTGRES_DB' (if not exists)..."
psql "$POSTGRES_ADMIN_DSN" -v ON_ERROR_STOP=0 -tc \
    "SELECT 1 FROM pg_database WHERE datname = '${MFT_POSTGRES_DB}'" \
    | grep -q 1 \
    || psql "$POSTGRES_ADMIN_DSN" -c "CREATE DATABASE ${MFT_POSTGRES_DB} OWNER ${MFT_POSTGRES_USER};"

echo "==> Granting privileges..."
psql "$POSTGRES_ADMIN_DSN" -c "GRANT ALL PRIVILEGES ON DATABASE ${MFT_POSTGRES_DB} TO ${MFT_POSTGRES_USER};"

# Build the app DSN for running migrations as the app user
APP_DSN="postgresql://${MFT_POSTGRES_USER}:${MFT_POSTGRES_PASSWORD}@$(echo "$POSTGRES_ADMIN_DSN" | sed 's|.*@||')"
APP_DSN="${APP_DSN%/*}/${MFT_POSTGRES_DB}"

echo "==> Running schema migrations..."
for sql_file in "$SQL_DIR"/*.sql; do
    [ -f "$sql_file" ] || continue
    echo "    applying $(basename "$sql_file")..."
    psql "$APP_DSN" -f "$sql_file"
done

echo "==> Database migration complete."
