# Docker, Compose & Deployment Standards

> Applies to `docker-compose*.yml`, `**/Dockerfile*`, `Makefile`, `gunicorn.conf.py`, `k8s/**`.

## Environments

| File                         | Purpose                        |
|------------------------------|--------------------------------|
| `docker-compose.local.yml`   | Local dev (profiles for optional services) |
| `docker-compose.uat.yml`     | UAT / staging environment      |
| `docker-compose.prod.yml`    | Production deployment          |

## Service Architecture (Production)

```
                         ┌─ cloudflared ─── Cloudflare Tunnel
                         │
Internet ──► Nginx (frontend) ──► agent (Gunicorn+Uvicorn)
                                      │
                                      ├── mcp (FastMCP SSE)
                                      ├── redis (stack-server)
                                      ├── postgres (16-alpine)
                                      └── router_worker
                         
Observability:  prometheus → alertmanager → grafana
Maintenance:    geoip_updater (daily MaxMind refresh)
```

## Compose Rules

1. **Environment interpolation**: All `.yml` files use root `.env` for secrets. Never hardcode credentials.
2. **Resource limits**: Every service must declare `mem_limit` and `cpus`.
3. **Health checks**: Every stateful service must have an explicit `healthcheck`.
4. **Depends-on with conditions**: Use `condition: service_healthy` for databases, not just `service_started`.
5. **Restart policy**: `unless-stopped` for all prod services.
6. **Network**: All services on `mft_network` bridge. Cloudflared uses `network_mode: host`.

## Dockerfile Standards

- Use **multi-stage builds** where applicable (frontend already does).
- Backend uses `uv` (copied from `ghcr.io/astral-sh/uv:latest`) — never raw `pip install`.
- Set `UV_COMPILE_BYTECODE=1` for production images.
- Never copy `.env` files into images. Mount at runtime or inject via env vars.
- Minimize layer count. Combine `RUN` commands where sensible.

## Gunicorn Production Config (`gunicorn.conf.py`)

- Workers: `cpu_count * 2 + 1` (overridable via `GUNICORN_WORKERS`).
- Worker class: `uvicorn.workers.UvicornWorker`.
- Request recycling: `max_requests=1000`, `max_requests_jitter=50`.
- Timeout: 180s (accommodates LLM streaming latency).
- Prometheus multiprocess directory is reset on `on_starting` and cleaned on `child_exit`.

## Makefile Quick Reference

| Command                | Action                                      |
|------------------------|---------------------------------------------|
| `make install`         | `uv sync` — install prod dependencies       |
| `make dev`             | Uvicorn reload mode on port 8000            |
| `make test`            | `uv run pytest tests/ -v`                   |
| `make format`          | Black + isort + Ruff auto-fix               |
| `make quality`         | CI formatting + linting checks              |
| `make local-up`        | Start core local Docker services            |
| `make localsetup`      | Validate + start + health-check local stack |
| `make localsetup-full` | Full stack including monitoring + edge       |
| `make local-validate`  | Syntax-check compose config                 |
| `make local-env-audit` | Check for duplicate .env keys               |
| `make deploy`          | Build + force-recreate prod stack           |

## Kubernetes

K8s manifests in `k8s/` cover:
- Base deployments and services
- HPA (Horizontal Pod Autoscaler) for agent + MCP
- Ingress with TLS termination
- Network policies (inter-service isolation)
- ConfigMaps and Secrets
- StatefulSets for databases

When modifying K8s manifests, always validate with `kubectl apply --dry-run=client`.
