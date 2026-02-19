# Context: `src/agent_service/security`

## Folder Snapshot
- Path: `src/agent_service/security`
- Role: Security middleware, runtime checks, metrics, and TOR/GeoIP controls.
- Priority: `high`
- Generated (UTC): `2026-02-19 18:37:32Z`
- Regenerate: `make context-docs`

## File Inventory
| File | Type | Purpose | Key Symbols |
| --- | --- | --- | --- |
| `__init__.py` | `python` | Security package for Tor blocking and session risk validation. | - |
| `geoip_resolver.py` | `python` | GeoIP resolvers for session risk analysis. | class MaxMindGeoLiteResolver |
| `metrics.py` | `python` | Prometheus metrics for security controls. | def export_prometheus_metrics |
| `middleware.py` | `python` | HTTP middleware for session risk enforcement. | def _audit, class SessionRiskMiddleware |
| `postgres_pool.py` | `python` | Optional PostgreSQL async pool for security analytics workflows. | class PostgresPoolManager |
| `runtime.py` | `python` | Runtime wiring for security components. | class SecurityRuntime, def build_security_runtime |
| `session_security.py` | `python` | Redis-backed session security risk engine. | class GeoResolverProtocol, class GeoLocation, class SessionSecurityConfig, class RiskAssessment, class SessionSecurityValidator |
| `tor_block.py` | `python` | Tor blocking runtime and FastAPI middleware. | class AnonymizerCheckerProtocol, def _audit_event, class TorExitBlocker, class BlockTorMiddleware |
| `tor_exit_nodes.py` | `python` | Tor exit node source client with retry/backoff semantics. | class TorExitNodes |

## Internal Dependencies
- `src.agent_service.core.config`
- `src.agent_service.security.geoip_resolver`
- `src.agent_service.security.metrics`
- `src.agent_service.security.session_security`
- `src.agent_service.security.tor_block`
- `src.agent_service.security.tor_exit_nodes`

## TODO / Risk Markers
- No TODO/FIXME/HACK markers detected.

## Session Handover Notes
1. Work completed in this folder:
2. Interfaces changed (APIs/schemas/config):
3. Tests run and evidence:
4. Open risks or blockers:
5. Next folder to process:
