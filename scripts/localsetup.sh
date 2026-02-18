#!/usr/bin/env bash
set -euo pipefail

cd /app

echo "[localsetup] starting preflight checks"

if [[ ! -f ".env" ]]; then
  echo "[localsetup] .env file is missing"
  exit 1
fi

mapfile -t duplicate_keys < <(
  awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/{print $1}' .env | sort | uniq -d
)

if [[ ${#duplicate_keys[@]} -gt 0 ]]; then
  echo "[localsetup] duplicate keys found in .env:"
  printf '  - %s\n' "${duplicate_keys[@]}"
  exit 1
fi

if [[ ! -f "infra/sql/session_security.sql" ]]; then
  echo "[localsetup] missing schema file: infra/sql/session_security.sql"
  exit 1
fi

mkdir -p /app/data/geoip

python - <<'PY'
import http.client
import os
import socket
import sys
import time

timeout = float(os.getenv("LOCALSETUP_WAIT_SECONDS", "40"))
interval = float(os.getenv("LOCALSETUP_WAIT_INTERVAL_SECONDS", "0.5"))


def tcp_ready(host: str, port: int) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True, ""
    except OSError as exc:
        return False, str(exc)


def http_ready(host: str, port: int, path: str) -> tuple[bool, str]:
    conn = http.client.HTTPConnection(host, port, timeout=1.5)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        if 200 <= resp.status < 300:
            return True, ""
        return False, f"HTTP {resp.status}"
    except OSError as exc:
        return False, str(exc)
    finally:
        conn.close()


checks: dict[str, tuple[str, int, str | None]] = {
    "redis:6379": ("redis", 6379, None),
    "postgres:5432": ("postgres", 5432, None),
    "neo4j:7687": ("neo4j", 7687, None),
    "mcp:8050": ("mcp", 8050, None),
    "agent:/health/ready": ("agent", 8000, "/health/ready"),
}

deadline = time.monotonic() + timeout
last_errors: dict[str, str] = {}

while checks and time.monotonic() < deadline:
    remaining: dict[str, tuple[str, int, str | None]] = {}
    for label, (host, port, path) in checks.items():
        ok, err = http_ready(host, port, path) if path else tcp_ready(host, port)
        if not ok:
            remaining[label] = (host, port, path)
            last_errors[label] = err
    checks = remaining
    if checks:
        time.sleep(interval)

if checks:
    print("[localsetup] dependency readiness checks failed:")
    for label in checks:
        print(f"  - {label} ({last_errors.get(label, 'timeout')})")
    sys.exit(1)
PY

echo "[localsetup] all checks passed"
