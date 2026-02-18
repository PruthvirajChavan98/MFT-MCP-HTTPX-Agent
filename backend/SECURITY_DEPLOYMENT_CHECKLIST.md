# Security Deployment Checklist

## 1) Core Security Controls
- [ ] Enable `SECURITY_ENABLED=true`.
- [ ] Set trusted proxy handling:
  - [ ] `SECURITY_TRUST_PROXY_HEADERS=true`
  - [ ] `SECURITY_PREFER_IP_HEADER=x-forwarded-for` (or `cf-connecting-ip`)
- [ ] Configure Tor refresh/staleness:
  - [ ] `TOR_REFRESH_SECONDS=1800`
  - [ ] `TOR_STALE_AFTER_SECONDS=7200`
  - [ ] `TOR_NEGATIVE_CACHE_TTL_SECONDS=300`
- [ ] Configure session risk thresholds:
  - [ ] impossible travel `+0.6` @ `>900 km/h`
  - [ ] concurrent IP `+0.5` (`>3 IPs / 5 min`)
  - [ ] device mismatch `+0.4`
  - [ ] geographic anomaly `+0.3`
  - [ ] thresholds: `<0.4 allow`, `0.4-0.7 step-up`, `>0.7 deny`

## 2) Database and Data Protection
- [ ] Apply `infra/sql/session_security.sql` to PostgreSQL.
- [ ] Set `app.tenant_id` and `app.column_key` on each DB connection.
- [ ] Verify row-level security policies for tenant isolation.
- [ ] Verify encrypted columns are populated for sensitive IP fields.

## 3) Rate Limiting and Input Safety
- [ ] Keep endpoint rate limiting enabled (`RATE_LIMIT_ENABLED=true`).
- [ ] Validate endpoint-specific RPS values.
- [ ] Require valid `X-Session-ID` and sanitize ingress headers upstream.

## 4) TLS and Edge Hardening
- [ ] Enforce TLS 1.3 at ingress/reverse proxy/load balancer.
- [ ] Enable HSTS and secure headers at edge + app.
- [ ] Block direct plaintext traffic except internal trusted networks.

## 5) Monitoring and Alerting
- [ ] Start stack: `prometheus`, `alertmanager`, `grafana`.
- [ ] Verify `/metrics` scraping from agent service.
- [ ] Import/verify Security dashboard.
- [ ] Alert rules active:
  - [ ] `TorListStale`
  - [ ] `TorBlocksSpike`
  - [ ] `SessionDenySpike`
  - [ ] `HighStepUpRate`

## 6) GeoIP / IP2Proxy Updates (Free-Only)
- [ ] Run `scripts/update_free_geoip.sh` via `geoip_updater` service.
- [ ] Keep `GEOIP_FREE_ONLY=true`.
- [ ] Provide free-tier credentials/URLs only.
- [ ] Verify `data/geoip/GeoLite2-City.mmdb` exists and is fresh.

## 7) Testing Requirements
- [ ] Unit: `tests/test_security_layers.py`.
- [ ] Integration: validate middleware decisions on critical vs monitored paths.
- [ ] Load: confirm p95 under target for security checks.
- [ ] Security: simulate Tor, proxy/VPN, impossible travel, and concurrent IP bursts.

## 8) Incident Response Playbook (Short)
- [ ] Detect: alert fires (`critical` or repeated `warning`).
- [ ] Triage: inspect logs/metrics (`tor_blocks_total`, `session_decisions_total`).
- [ ] Contain: tighten critical-path policy and rate limits; block abusive source ranges at edge.
- [ ] Eradicate: rotate compromised keys, invalidate high-risk sessions.
- [ ] Recover: return thresholds to baseline after stabilization.
- [ ] Review: publish postmortem with timeline, root cause, and control improvements.
