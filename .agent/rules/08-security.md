# Security Architecture

> Applies to `backend/src/agent_service/security/**` and all endpoints handling user data.

## Security Middleware Stack

The security middleware is applied globally via `app_factory`. Execution order matters:

1. **Security Headers Middleware** — HSTS, CSP, X-Frame-Options, etc.
2. **Inline Guard** — Request-level threat detection and blocking
3. **Session Security** — Session validation, device fingerprinting, impossible travel detection
4. **Rate Limiting** — Per-identity Redis-backed rate limits

## Session Security (`session_security.py`)

Multi-signal risk scoring system:

| Signal               | Risk Weight | Description                              |
|----------------------|-------------|------------------------------------------|
| Impossible travel    | 0.6         | Location change faster than 900 km/h     |
| Concurrent IPs       | 0.5         | >3 distinct IPs within 5-minute window   |
| Device mismatch      | 0.4         | User-agent fingerprint change            |
| Geo anomaly          | 0.3         | Country/region deviation from baseline   |

Decisions based on composite score:
- `< 0.4` → **allow**
- `0.4 – 0.7` → **step_up** (additional verification)
- `> 0.7` → **deny**

All thresholds are configurable via env vars (`SECURITY_RISK_*`).

## GeoIP Resolution

- Uses MaxMind GeoLite2 database (`GeoLite2-City.mmdb`).
- Updated daily by the `geoip_updater` container.
- Fallback: free GeoIP databases when MaxMind keys unavailable.
- Database path: `/app/data/geoip/` (volume-mounted).

## Tor Exit Node Blocking (`tor_block.py`)

- Exit node list refreshed every 1800 seconds (`TOR_REFRESH_SECONDS`).
- Stale lists expire after 7200 seconds.
- Negative cache TTL: 300 seconds.
- Applied only to critical paths defined in `SECURITY_CRITICAL_PATHS`.

## Rate Limiting

- **Nginx layer**: Volumetric/L7 defense — IP-based, NAT-safe thresholds.
- **FastAPI layer**: Identity-based quotas via `RateLimiterManager` (Redis-backed).
- Never move per-user/per-tenant quotas to Nginx.
- Stream endpoints have dedicated rate limit buckets.

## Proxy Trust

- Production runs behind Cloudflare Tunnel.
- `SECURITY_TRUST_PROXY_HEADERS=true` — trusts `X-Forwarded-For`.
- `SECURITY_PREFER_IP_HEADER=x-forwarded-for` — uses this header for client IP extraction.
- Never trust proxy headers in environments without a trusted reverse proxy.

## Rules for Security Changes

1. Never weaken rate limits without documented operational rationale.
2. Never expose session internals (risk scores, device fingerprints) to API consumers.
3. Always test security changes with the dedicated test suite (`test_security_layers.py`, `test_inline_guard.py`).
4. Log security events but never log sensitive data (tokens, passwords, raw IPs in debug mode).
