# Main Context Handover

## Snapshot
- Generated (UTC): `2026-02-19 18:37:32Z`
- Leaf folders tracked: `23`
- Files indexed in leaf folders: `94`
- Generation command: `make context-docs`

## Context-Constrained Session Strategy
1. Read this file first to choose scope.
2. Open only the relevant leaf `_context.md` files for touched folders.
3. Open raw source files only inside those touched leaf folders.
4. After each folder is completed, rerun `make context-docs`.
5. Append a concise delta summary to your master context artifact.

## Master Context Build Plan
1. Process one leaf folder at a time (see index below).
2. For each folder, capture: changed files, interface impact, test proof, open risks.
3. Re-run `make context-docs` immediately after folder completion.
4. Fold each folder delta into a running `MASTER_CONTEXT.md` summary.
5. Keep `MASTER_CONTEXT.md` under a strict token budget by storing links, not code.

## Leaf Folder Index
| Folder | Priority | Role | Files | Context |
| --- | --- | --- | --- | --- |
| `.github/workflows` | `low` | CI workflow definitions and code-quality gate configuration. | `1` | `.github/workflows/_context.md` |
| `cloudflared` | `low` | Cloudflare tunnel configuration for edge ingress. | `1` | `cloudflared/_context.md` |
| `data/geoip` | `low` | GeoIP data directory populated by updater jobs or setup scripts. | `0` | `data/geoip/_context.md` |
| `infra/monitoring/grafana/dashboards` | `medium` | Grafana dashboard JSON assets. | `1` | `infra/monitoring/grafana/dashboards/_context.md` |
| `infra/monitoring/grafana/provisioning/dashboards` | `medium` | Grafana dashboard provisioning config. | `1` | `infra/monitoring/grafana/provisioning/dashboards/_context.md` |
| `infra/monitoring/grafana/provisioning/datasources` | `medium` | Grafana datasource provisioning config. | `1` | `infra/monitoring/grafana/provisioning/datasources/_context.md` |
| `infra/monitoring/prometheus` | `medium` | Prometheus scrape and alert rule configuration. | `2` | `infra/monitoring/prometheus/_context.md` |
| `infra/nginx` | `medium` | Nginx edge/TLS configuration. | `1` | `infra/nginx/_context.md` |
| `infra/sql` | `medium` | PostgreSQL security/session schema and policy scripts. | `1` | `infra/sql/_context.md` |
| `scripts` | `medium` | Operational scripts for ingestion, local setup, and endpoint validation. | `6` | `scripts/_context.md` |
| `src/agent_service/api/endpoints` | `high` | Public FastAPI endpoint handlers for agent-facing APIs. | `9` | `src/agent_service/api/endpoints/_context.md` |
| `src/agent_service/core` | `high` | Core runtime orchestration, config, schemas, and shared service logic. | `15` | `src/agent_service/core/_context.md` |
| `src/agent_service/data` | `medium` | Data-access configuration helpers. | `2` | `src/agent_service/data/_context.md` |
| `src/agent_service/eval_store` | `medium` | Evaluation storage, embedding, and judge integration modules. | `3` | `src/agent_service/eval_store/_context.md` |
| `src/agent_service/faqs` | `medium` | FAQ parsing artifacts and ingest support assets. | `2` | `src/agent_service/faqs/_context.md` |
| `src/agent_service/features` | `medium` | Feature flags/prototypes and answerability/follow-up behavior modules. | `7` | `src/agent_service/features/_context.md` |
| `src/agent_service/llm` | `high` | Model catalog and provider client orchestration. | `3` | `src/agent_service/llm/_context.md` |
| `src/agent_service/router` | `medium` | NBFC router taxonomy, schemas, service, and worker runtime. | `5` | `src/agent_service/router/_context.md` |
| `src/agent_service/security` | `high` | Security middleware, runtime checks, metrics, and TOR/GeoIP controls. | `9` | `src/agent_service/security/_context.md` |
| `src/agent_service/tools` | `high` | Graph/tool adapters for knowledge and MCP integration. | `4` | `src/agent_service/tools/_context.md` |
| `src/common` | `medium` | Shared logging and Neo4j management primitives. | `2` | `src/common/_context.md` |
| `src/mcp_service` | `high` | MCP service APIs, session store, tool descriptions, and server runtime. | `9` | `src/mcp_service/_context.md` |
| `tests` | `high` | Contract/unit coverage for API, streaming, router, MCP, and security behavior. | `9` | `tests/_context.md` |

## Non-Leaf Files (Covered Here)
These directories have both files and child folders, so they do not receive leaf `_context.md` files.
| Directory | Files |
| --- | --- |
| `.github` | `CONTRIBUTING.md` |
| `infra/monitoring` | `alertmanager.yml` |
| `src` | `main_agent.py`, `main_mcp.py` |
| `src/agent_service/api` | `__init__.py`, `admin.py`, `admin_analytics.py`, `admin_auth.py`, `eval_ingest.py`, `eval_live.py`, `eval_read.py`, `feedback.py`, `graphql.py` |

## Session Handover Template
1. Scope for next session:
2. Folder(s) completed this session:
3. Interfaces changed:
4. Tests/lint/type checks run:
5. Risks, debt, and immediate next step:
