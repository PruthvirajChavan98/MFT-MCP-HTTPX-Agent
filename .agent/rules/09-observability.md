# Observability & Monitoring

> Applies to metrics, health checks, and monitoring infrastructure.

## Prometheus Metrics

- Instrumented via `prometheus-client` Python library.
- Multi-process mode enabled: `PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc`.
- Gunicorn hooks manage shard lifecycle (see `gunicorn.conf.py`).
- Metrics exposed at `/metrics` endpoint.

### Adding New Metrics

```python
from prometheus_client import Counter, Histogram

request_count = Counter(
    "agent_request_total",
    "Total agent requests",
    ["endpoint", "status"]
)
request_latency = Histogram(
    "agent_request_duration_seconds",
    "Request latency",
    ["endpoint"]
)
```

- Use consistent naming: `<service>_<metric>_<unit>`.
- Always include relevant labels (endpoint, status, etc.).
- Register metrics at module level, not inside functions.

## Health Checks

- `GET /health` — basic liveness (returns 200 if the process is alive).
- Health endpoint in `backend/src/agent_service/api/endpoints/health.py`.
- Docker Compose and K8s both use health checks for readiness gates.

## Monitoring Stack (Production)

```
agent ──► prometheus ──► alertmanager ──► (webhook/email)
                │
                └──► grafana (dashboards)
```

- **Prometheus config**: `backend/infra/monitoring/prometheus/prometheus.yml`
- **Alert rules**: `backend/infra/monitoring/prometheus/alerts.yml`
- **Alertmanager config**: `backend/infra/monitoring/alertmanager.yml`
- **Grafana dashboards**: `backend/infra/monitoring/grafana/dashboards/`
- **Grafana datasources**: `backend/infra/monitoring/grafana/provisioning/datasources/`

### Ports (localhost-bound in prod)

| Service       | Port |
|---------------|------|
| Prometheus    | 9090 |
| Alertmanager  | 9093 |
| Grafana       | 3001 |

## Shadow Evaluation (`shadow_eval.py`)

- Production sampling: `SHADOW_EVAL_SAMPLE_RATE=0.1` (10% of requests).
- Capture mode: `light` (metadata only) or `full` (with payloads).
- Results stored in eval store and queryable via admin analytics.
- Shadow eval must never impact request latency — runs async post-response.
