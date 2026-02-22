# Changelog

All notable changes to the MFT Platform are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased] - 2026-02-22

### Branch: `enterprise-ha-architecture-migration`

Enterprise HA architecture migration addressing four critical production
vulnerabilities: single-point-of-failure orchestration, Gunicorn worker
exhaustion, missing edge-layer rate limiting, and single-replica tunnel ingress.

34 files changed, 2,286 lines added.

### Database & State Management Hardening

#### Cross-Tenant Data Leakage (PostgreSQL RLS)
- **`backend/src/agent_service/api/admin_analytics.py`** -- Replaced implicit RLS reliance with explicit `async with conn.transaction():` blocks and `set_config('app.tenant_id', $1, true)` to guarantee tenant isolation and preserve `asyncpg` prepared statement caching without resorting to `DISCARD ALL`. Added `tenant_id` query parameter to the `/guardrails` endpoint.

#### Event Loop Starvation (Neo4j)
- **`backend/src/common/neo4j_mgr.py`** -- Completely rewrote `Neo4jManager` from a synchronous singleton using `threading.Lock` to an async instance `neo4j_mgr` using `neo4j.AsyncGraphDatabase` and `AsyncDriver`.
- **`backend/src/agent_service/core/app_factory.py`** -- Bound the new `neo4j_mgr` connection lifecycle (init, verify, close) directly to the FastAPI `@asynccontextmanager` lifespan hook, eliminating module-level `asyncio.Lock()` cross-loop attachment bugs.
- **Multiple Files** -- Upgraded all Neo4j call sites (`admin_analytics.py`, `worker.py`, `answerability.py`, `follow_up.py`, `graph_rag.py`, `knowledge.py`, `embedder.py`, `eval_read.py`, `neo4j_store.py`) to `await` the new async driver, removing legacy `run_in_threadpool` wrappers.

#### "Lost Update" Race Conditions (Redis)
- **`backend/src/mcp_service/session_store.py`** -- Refactored `RedisSessionStore` to eliminate JSON Read-Modify-Write race conditions by migrating to Redis Hashes (`HSET`/`HGETALL`).
- Implemented **Pipelining** to ensure `HSET` and `EXPIRE` commands execute atomically, preventing permanent memory leaks if a worker crashes before TTL application.
- Developed **Hybrid Serialization** to handle nested session payload objects (automatically `json.dumps()` for nested dicts/lists and stringifying primitives) since Redis Hashes are strictly flat.

---

### Critical Fixes

#### Gunicorn Worker Exhaustion (CVE-class severity)

- **`backend/gunicorn.conf.py`** -- Changed `timeout = 0` to `timeout = 180`
  and added `graceful_timeout = 120`. The disabled watchdog allowed silent
  upstream network partitions (e.g., an LLM provider TCP socket open with no
  bytes) to permanently consume Uvicorn workers until the entire pool was
  exhausted.
- **`docker-compose.prod.yml`** -- Changed `--timeout 0` to `--timeout 180` in
  the agent service command, which was overriding `gunicorn.conf.py`.
- **`backend/start.sh`** -- Aligned bare-metal startup script to `--timeout 180`
  (was 120, now consistent with all other surfaces).

#### httpx Client Timeout Hardening

Every `httpx.AsyncClient` and `httpx.Client` in the codebase now uses explicit
per-phase timeouts via `httpx.Timeout(connect=, read=, write=, pool=)` instead
of a single float, preventing silent hangs on any individual TCP phase.

- **`backend/src/agent_service/llm/catalog.py`** -- All three provider clients
  (Groq, OpenRouter, NVIDIA) now use
  `httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)` with
  `httpx.Limits(max_connections=100, max_keepalive_connections=20)` to cap
  connection pool growth under load.
- **`backend/src/mcp_service/core_api.py`** -- CRM API client hardened with
  `httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)`.
- **`backend/src/mcp_service/auth_api.py`** -- All three auth flow clients
  (contact hint, OTP generate, OTP validate) hardened with the same timeout
  profile.
- **`backend/src/agent_service/security/tor_exit_nodes.py`** -- Tor exit list
  fetcher now defaults to `httpx.Timeout(connect=5.0, read=15.0, write=5.0,
  pool=5.0)` while remaining backward-compatible with float-based timeout args.

---

### Added

#### Nginx Edge-Layer Volumetric Defense

Rate limiting at the Nginx layer now drops abusive volumetric traffic before it
reaches the ASGI application, protecting CPU and file descriptors. Thresholds
are set high enough to avoid punishing corporate NAT gateways.

- **`backend/infra/nginx/nginx-tls13.conf`** -- Added three rate-limiting zones:
  - `conn_per_ip` -- 50 concurrent connections per IP (blocks socket exhaustion)
  - `req_per_ip` -- 30 req/s per IP, burst 60 (blocks automated request floods)
  - `stream_new_per_ip` -- 5 new SSE connections/s per IP, burst 10 (limits
    connection establishment rate, not active long-lived streams)
  - Dedicated `/agent/stream` location block with streaming-optimized proxy
    settings (buffering off, 300s read timeout, chunked encoding)
- **`Chatbot UI and Admin Console/nginx.conf`** -- Same volumetric defense
  applied to the frontend reverse proxy:
  - `/api/agent/stream` location with SSE-specific rate zone
  - `/api/` location with general request rate + connection limits
  - FastAPI `RateLimiterManager` continues to enforce per-user/per-session
    business-logic quotas using authenticated identity

#### k3s Kubernetes Manifests (24 new files)

Complete production-grade k8s manifest set in `k8s/`, organized by concern and
composable via Kustomize.

**Base & Configuration:**

- `k8s/base/namespace.yaml` -- `mft` namespace with Pod Security Standards
  (baseline enforce, restricted warn)
- `k8s/base/kustomization.yaml` -- Single entry point referencing all resources
  with common labels
- `k8s/secrets/sealed-secrets.yaml` -- SealedSecrets template for all sensitive
  values (Postgres password, API keys, tunnel token, etc.)
- `k8s/configmaps/app-config.yaml` -- All non-sensitive environment variables
  extracted from `docker-compose.prod.yml` into a single ConfigMap

**Stateful Services:**

- `k8s/stateful/postgres-cluster.yaml` -- CloudNativePG `Cluster` CR with
  2 instances, automated failover, leader election, tuned PostgreSQL parameters,
  and PodMonitor for Prometheus integration
- `k8s/stateful/redis-sentinel.yaml` -- OT-Container-Kit Redis Operator CRs:
  `Redis` primary with Redis Exporter sidecar + `RedisSentinel` with 3 sentinel
  pods for automatic failover. Includes fallback instructions for Bitnami Helm
  chart with `architecture=replication` and Sentinel enabled.
- `k8s/stateful/neo4j-statefulset.yaml` -- Neo4j 5.26.0 StatefulSet with
  10Gi PVC, startup/readiness/liveness probes via `cypher-shell`, and memory
  configuration from ConfigMap

**Application Workloads:**

- `k8s/workloads/agent-deployment.yaml` -- 2 replicas with:
  - Startup probe (150s budget), readiness probe (5s interval), liveness probe
    (15s interval) on `/health`
  - Pod anti-affinity (prefer spreading across nodes)
  - Resource requests 1 CPU / 1Gi, limits 2 CPU / 2Gi
  - `--timeout 180` in Gunicorn command
  - Secrets injected via `secretKeyRef`, config via `configMapRef`
  - GeoIP PVC mount (shared with CronJob)
  - ClusterIP Service on port 8000
- `k8s/workloads/mcp-deployment.yaml` -- MCP server Deployment with TCP probes
  and ClusterIP Service on port 8050
- `k8s/workloads/router-worker-deployment.yaml` -- Background worker Deployment
  with process-level liveness probe
- `k8s/workloads/frontend-deployment.yaml` -- 2 replicas with HTTP probes, pod
  anti-affinity, and ClusterIP Service on port 80
- `k8s/workloads/geoip-cronjob.yaml` -- Daily CronJob (03:00 UTC) replacing
  the infinite-loop `while true; sleep 86400` container pattern. Includes
  `activeDeadlineSeconds: 600` and `backoffLimit: 2`.

**Ingress & Tunnel:**

- `k8s/ingress/cloudflared-deployment.yaml` -- 3-replica Deployment with:
  - Pod anti-affinity across nodes for HA
  - ConfigMap-based tunnel config pointing to k8s Service DNS names
  - Metrics port 2000 with readiness/liveness probes on `/ready`
  - Tunnel token from SealedSecret
  - Cloudflare natively load-balances across all active tunnel connections
- `k8s/ingress/nginx-configmap.yaml` -- Nginx Ingress Controller ConfigMap with
  TLS 1.3, rate limiting HTTP snippet, proxy timeouts, security headers, and
  gzip compression
- `k8s/ingress/ingress-resource.yaml` -- Ingress resource with hostname-based
  routing for `mft-agent.pruthvirajchavan.codes` (frontend + API) and
  `mft-api.pruthvirajchavan.codes` (direct API)

**Monitoring:**

- `k8s/monitoring/prometheus-deployment.yaml` -- Prometheus with:
  - Kubernetes pod service discovery (annotation-based scraping)
  - Security alerts (Tor list staleness, session deny spikes, step-up rate)
  - Infrastructure alerts (crash loops, memory > 85%, agent p99 > 10s)
  - RBAC (ServiceAccount, ClusterRole, ClusterRoleBinding)
  - 10Gi PVC with 15-day retention
- `k8s/monitoring/alertmanager-deployment.yaml` -- Alertmanager with webhook
  receiver pointing to agent service
- `k8s/monitoring/grafana-deployment.yaml` -- Grafana 11.1.4 with provisioned
  Prometheus datasource and dashboard provider
- `k8s/monitoring/servicemonitor.yaml` -- ServiceMonitor CRDs for agent (15s)
  and cloudflared (30s) for Prometheus Operator auto-discovery

**Autoscaling:**

- `k8s/hpa/agent-hpa.yaml` -- HPA scaling 2-6 replicas on CPU (70%) and
  memory (80%) with stabilization windows (60s up, 300s down)
- `k8s/hpa/frontend-hpa.yaml` -- HPA scaling 2-4 replicas on CPU (70%)

**Network Security (Zero-Trust):**

- `k8s/network-policies/default-deny.yaml` -- Default deny all ingress and
  egress for every pod in the namespace
- `k8s/network-policies/allow-ingress.yaml` -- Explicit allow rules:
  cloudflared -> frontend (80), cloudflared -> agent (8000),
  frontend -> agent (8000), cloudflared egress to Cloudflare edge (443, 7844)
- `k8s/network-policies/allow-agent-to-data.yaml` -- 13 granular policies:
  - agent -> redis (6379), postgres (5432), neo4j (7687), mcp (8050)
  - agent -> external LLM providers (443) + DNS (53)
  - mcp -> redis (6379), external CRM (443)
  - router-worker -> redis (6379), neo4j (7687)
  - prometheus -> all scrape targets + k8s API
  - alertmanager <-> prometheus, alertmanager -> agent webhook
  - grafana -> prometheus (9090)
  - Data layer ingress: redis, postgres, neo4j only from authorized app pods

---

### Changed

- **`backend/.pre-commit-config.yaml`** -- Added `--allow-multiple-documents`
  to `check-yaml` hook and excluded `k8s/` directory (multi-document YAML is
  standard for Kubernetes manifests).

### Fixed

- **`backend/src/agent_service/llm/catalog.py`** -- Replaced bare `except:`
  with `except (TypeError, ValueError):` for pricing float conversion (ruff
  E722).
- **`backend/src/mcp_service/core_api.py`** -- Replaced bare `except:` with
  `except Exception:` for JSON parse fallback (ruff E722).
- **`backend/src/mcp_service/auth_api.py`** -- Replaced bare `except:` with
  `except Exception:` for JSON parse fallback (ruff E722).
