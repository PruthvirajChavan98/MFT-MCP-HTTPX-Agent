# Changelog

All notable changes to the MFT Platform are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased] - 2026-02-22

### Branch: `enterprise-ha-architecture-migration`

Enterprise HA architecture migration addressing four critical production
vulnerabilities: single-point-of-failure orchestration, Gunicorn worker
exhaustion, missing edge-layer rate limiting, and single-replica tunnel ingress.

Current working set includes major backend/frontend hardening, analytics expansion,
and production deployment/runtime updates.

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

### Inline Guard + Guardrails Observatory

#### Inline Prompt Injection/Jailbreak Blocking (Fail-Closed)
- **`backend/src/agent_service/security/inline_guard.py`** -- Added a dual-rail inline safety evaluator combining embedding-similarity prototype checks and provider-side prompt-guard classification, with strict timeout envelopes and fail-closed behavior on timeout/error.
- **`backend/src/agent_service/api/endpoints/agent_stream.py`** -- Added pre-graph prompt safety enforcement that immediately returns an SSE error when a prompt violates policy, preventing unsafe prompts from reaching agent/tool execution.

#### Shadow Trace Queue Durability
- **`backend/src/agent_service/api/endpoints/agent_stream.py`** -- Added asynchronous shadow trace enqueue scheduling on both KB-first and full-stream paths, with bounded enqueue timeout and non-fatal warning logs to preserve response-path resilience.
- **`backend/src/agent_service/eval_store/shadow_queue.py`** + **`backend/src/agent_service/worker/`** -- Added queue-backed trace handoff and worker processing surfaces to decouple online request latency from downstream shadow evaluation workflows.

#### Admin Guardrails Analytics Expansion
- **`backend/src/agent_service/api/admin_analytics.py`** -- Extended `/guardrails` with filterable/paginated queries (`decision`, `min_risk`, `session_id`, `start`, `end`, `offset`, `limit`) while preserving explicit transaction-scoped tenant context.
- Added new guardrails analytics endpoints:
  - `/guardrails/summary` for deny-rate and aggregate risk KPIs,
  - `/guardrails/trends` for hourly decision/risk series,
  - `/guardrails/queue-health` for Redis queue depth/oldest-age observability,
  - `/guardrails/judge-summary` for Neo4j-based evaluation quality rollups + recent failures.

#### Admin Console Guardrails Observatory UI
- **`Chatbot UI and Admin Console/src/shared/api/admin.ts`** -- Added typed client contracts and fetchers for summary, trends, queue health, judge summary, and filtered/paginated guardrail event retrieval.
- **`Chatbot UI and Admin Console/src/app/components/admin/Guardrails.tsx`** -- Upgraded Guardrails view into an observability dashboard with KPI cards, trend visualization, tenant/time filtering, decision filter reset semantics, and paginated event navigation.

#### Validation Coverage
- **`backend/tests/test_inline_guard.py`** -- Added inline guard tests for success path and fail-closed exception behavior.
- **`backend/tests/test_agent_stream_guardrail.py`** -- Added stream endpoint test asserting unsafe prompts are blocked before graph construction.
- **`Chatbot UI and Admin Console/src/app/components/admin/Guardrails.test.tsx`** and **`Chatbot UI and Admin Console/src/shared/api/admin.guardrails.test.ts`** -- Added frontend contract/UI tests for the new guardrails observability surfaces.

---

### Prompt Management Hardening (YAML + Jinja2)

#### Agent Prompt Registry
- **`backend/src/agent_service/core/prompts.yaml`** -- Introduced a centralized hierarchical prompt registry for `agent`, `eval`, `router`, `follow_up`, and `knowledge`, with explicit `description` and `template` fields for each prompt.
- **`backend/src/agent_service/core/prompts.py`** -- Replaced hardcoded prompt constants with a Pydantic-validated `PromptManager` singleton that performs strict schema validation at startup and exposes `get_template(category, prompt_name)`.
- **`backend/src/agent_service/core/app_factory.py`** -- Added one-time prompt loading during FastAPI lifespan (`prompt_manager.load()`), ensuring invalid YAML fails fast during boot/CI rather than at runtime.

#### Jinja2 Prompt Rendering Migration
- **`backend/src/agent_service/eval_store/judge.py`** -- Removed `G_EVAL_POINTWISE_PROMPT` and `PAIRWISE_PROMPT` hardcoded strings; now sourced from registry and rendered with `ChatPromptTemplate.from_messages(..., template_format=\"jinja2\")`.
- **`backend/src/agent_service/router/service.py`** -- Extracted the inline LLM classifier prompt (`classify_llm_glm47`) into registry-backed template rendering using Jinja2 format.
- **`backend/src/agent_service/features/follow_up.py`** -- Removed `BASE_SYSTEM_PROMPT` and `ANGLE_PROMPTS`; follow-up system and angle prompts now come from YAML templates and are rendered with runtime `context`.
- **`backend/src/agent_service/tools/knowledge.py`** -- Moved metadata extraction system prompt to registry and switched to Jinja2-formatted prompt rendering.
- **`backend/src/agent_service/api/endpoints/sessions.py`** -- Replaced direct `SYSTEM_PROMPT` dependency with `prompt_manager.get_default_system_prompt()` for session initialization/default fallback.

#### MCP Prompt Boundary Preservation
- **`backend/src/mcp_service/tool_descriptions.yaml`** -- Replaced JSON descriptions with YAML multiline blocks for prompt-engineering readability and maintainability while keeping MCP descriptions static and service-local.
- **`backend/src/mcp_service/description_utils.py`** -- Migrated description loader from JSON parsing to `yaml.safe_load`, preserving static boot-time registration behavior.
- **`backend/src/mcp_service/tool_descriptions.json`** -- Removed legacy escaped-string JSON descriptor file.

#### CI/CD Guardrail
- **`backend/tests/test_prompts_yaml_valid.py`** -- Added schema-validation unit test that instantiates and loads `PromptManager`, enforcing prompt YAML correctness in CI.

---

### AI/LLM Orchestration Hardening (Topic 4)

#### LangGraph Checkpoint TTL Safety
- **`backend/src/agent_service/core/app_factory.py`** -- Updated `AsyncRedisSaver.from_conn_string(...)` to enforce Redis checkpoint expiry with:
  - `default_ttl: 10080` (7 days in minutes)
  - `refresh_on_read: true`
- This prevents unbounded checkpoint retention and Redis OOM risk from long-lived conversation state.

#### Distributed Semantic Router Cache (Kubernetes-safe)
- **`backend/src/agent_service/features/nbfc_router.py`** -- Replaced filesystem prototype cache with Redis-backed cache via `get_redis()`, removing node-local disk coupling.
- Prototype embeddings are now serialized as JSON-safe float lists before storage and reconstructed for `numpy` usage at read time.
- Cache key pattern standardized to `agent:router:proto:{model}:{fp}` with 30-day TTL to keep warm-start behavior while avoiding stale, immortal cache entries.

#### FastMCP SSE Self-Healing Resiliency
- **`backend/src/agent_service/tools/mcp_manager.py`** -- Added transport recovery path in `tool_wrapper`:
  - on tool invoke exception, perform guarded `shutdown()` + `initialize()`
  - retry invoke exactly once after reconnect
  - use `self.call_lock` to prevent concurrent reconnect stampedes.
- `shutdown()` now resets session/client/exit-stack state to ensure clean reinitialization semantics.

#### Cognee Migration and Legacy Graph Deletion
- **`backend/src/agent_service/tools/mcp_manager.py`** -- Removed legacy `create_graph_tool` integration and introduced async `mock_fintech_knowledge_base` using Cognee graph completion search.
- **`backend/src/agent_service/api/admin.py`** -- Migrated semantic search endpoint to Cognee-backed query path and deprecated legacy FAQ management routes with explicit `410` responses.
- **Removed legacy files**:
  - `backend/src/agent_service/tools/graph_rag.py`
  - `backend/src/agent_service/tools/knowledge.py`
  - `backend/scripts/ingest_faq.py`
  - `backend/src/agent_service/faqs/pdf_parser.py`

#### Research-Backed API Compatibility and Dependency Updates
- **Cognee API alignment**:
  - primary call path uses latest-style `query_text` + `query_type`
  - compatibility fallback supports older `query` + `search_type` signatures.
- **Dependency update**:
  - added Cognee runtime dependency in `backend/pyproject.toml`
  - lockfile updated in `backend/uv.lock`.

#### Stabilization Fixes During Rule-Compliant Test Execution
- **`backend/src/agent_service/core/resource_resolver.py`** -- Replaced removed `SYSTEM_PROMPT` constant usage with `prompt_manager.get_default_system_prompt()`.
- **`backend/src/agent_service/core/streaming_utils.py`** -- Adjusted `tool_call_event` payload shape to preserve public streaming contract expectations.
- **`backend/src/agent_service/llm/client.py`** -- Updated OpenRouter client key handling to satisfy adapter/test compatibility.
- **`backend/src/agent_service/utils.py`** -- Added backward-compatible utility shim for legacy imports and reducer behavior used by existing tests.
- **Validation outcome**:
  - `make test` executed successfully with full suite pass after these adjustments.

---

### Prometheus + SSE Research-Backed Validation (Follow-up Hardening)

#### Documentation-Validated Multiprocess Prometheus Alignment
- **Research basis** -- Re-validated implementation against official `prometheus/client_python` multiprocess guidance (registry pattern, `PROMETHEUS_MULTIPROC_DIR` lifecycle, and Gunicorn dead-worker cleanup semantics).
- **`backend/src/agent_service/security/metrics.py`** -- Refined multiprocess gauge aggregation behavior to `livemax` for Tor gauges so dead workers do not skew current-state metrics.
- **`backend/src/agent_service/security/metrics.py`** -- Added compatibility-safe registry creation path:
  - prefer `CollectorRegistry(support_collectors_without_names=True)` where supported by installed client version,
  - fallback to `CollectorRegistry()` for older `prometheus_client` builds.
- This preserves correctness across dependency versions while keeping per-scrape multiprocess aggregation intact.

#### Documentation-Validated SSE Transport Keepalive
- **Research basis** -- Re-validated against WHATWG SSE authoring notes and `sse-starlette` production guidance.
- **`backend/src/agent_service/api/endpoints/live_dashboards.py`** -- Migrated from manual in-generator heartbeat emission to native `EventSourceResponse` controls:
  - `ping=15` for periodic SSE keepalive comments,
  - `send_timeout=30` to fail hanging socket writes sooner.
- Retained disconnect polling and deterministic Redis pubsub cleanup (`unsubscribe`/`close`) to prevent zombie connection resource leaks.

#### Validation and Test Updates
- **`backend/tests/test_live_dashboards.py`** -- Updated tests to assert configured ping/send-timeout behavior and cleanup guarantees for global/session feeds.
- **`backend/tests/test_metrics_endpoint.py`** -- Existing multiprocess export/normalization validations continue to pass with the compatibility path.
- **Validation outcome** -- Targeted suite and lint re-run successful:
  - `uv run pytest tests/test_metrics_endpoint.py tests/test_live_dashboards.py` -> pass
  - file-scoped `ruff check` for touched Prometheus/SSE files -> pass
  - no new linter diagnostics on touched files.

---

### Frontend Rule Coverage + Governance Traceability

- **`.cursor/rules/frontend-admin-console-nginx.mdc`** -- Added dedicated rule coverage for `Chatbot UI and Admin Console/nginx.conf` so frontend ingress behavior is explicitly governed (SSE proxy safety, NAT-safe volumetric limits, and boundary between edge abuse controls vs FastAPI business quotas).
- Added explicit merge-time validation expectations for frontend Nginx changes:
  - syntax/sanity check required before merge,
  - route precedence protections (`/api/agent/stream` before `/api/`),
  - rationale logging for rate-threshold changes in changelog.
- **Sanity validation executed** -- frontend config validated with containerized Nginx syntax check:
  - `docker run --rm --add-host agent:127.0.0.1 -v \"$PWD/Chatbot UI and Admin Console/nginx.conf:/tmp/site.conf:ro\" nginx:1.27-alpine ... nginx -t -c /tmp/nginx.conf` -> success.
- Cross-rule governance alignment now explicitly references:
  - `.cursor/rules/user-enterprise-nonnegotiables.mdc`
  - `.cursor/rules/docker-and-deployment.mdc`

---

### Frontend Production Hardening (Build/Runtime/Performance)

#### Build Once, Deploy Anywhere (Vite Env Trap Mitigation)
- **`Chatbot UI and Admin Console/src/shared/api/http.ts`** -- Removed runtime dependence on `import.meta.env.VITE_API_BASE_URL`; API base now resolves from `window.__RUNTIME_CONFIG__` with enforced fallback to relative `/api`.
- **`Chatbot UI and Admin Console/index.html`** -- Added `runtime-config.js` bootstrap before app startup.
- **`Chatbot UI and Admin Console/public/runtime-config.js`** -- Added default runtime config artifact for environment-agnostic builds.
- **`Chatbot UI and Admin Console/Dockerfile.prod`** + **`Chatbot UI and Admin Console/docker-entrypoint-runtime-config.sh`** -- Added container startup injection that writes runtime config values before Nginx serves static assets.
- **`docker-compose.prod.yml`** -- Added frontend runtime env keys (`FRONTEND_API_BASE_URL`, `FRONTEND_APP_ENV`) to support deploy-time configuration without image rebuilds.

#### Route-Level Code Splitting + Suspense
- **`Chatbot UI and Admin Console/src/app/routes.ts`** -- Refactored admin route components to `React.lazy` dynamic imports so admin-heavy modules are not loaded on landing page startup.
- **`Chatbot UI and Admin Console/src/app/App.tsx`** -- Wrapped `RouterProvider` in `Suspense` with lightweight fallback to support lazy route loading.

#### Deterministic Vendor Chunking
- **`Chatbot UI and Admin Console/vite.config.ts`** -- Added `build.rollupOptions.output.manualChunks` for:
  - router/runtime vendor (`react-router`),
  - query vendor (`@tanstack/react-query`),
  - charts vendor (`recharts`),
  - admin-heavy dependencies (`react-dnd`, `react-resizable-panels`),
  - UI vendor groups (`MUI`, `Radix`).

#### React Router Dependency/Type Cleanse
- **`Chatbot UI and Admin Console/package.json`** -- Removed `react-router-dom` and legacy `@types/react-router-dom` (v5 type conflict) and standardized on `react-router` v7 exports.
- **`Chatbot UI and Admin Console/src/app/components/admin/AdminLayout.tsx`** and **`Chatbot UI and Admin Console/src/app/components/NBFCLandingPage.tsx`** -- Migrated imports from `react-router-dom` to `react-router`.

#### Validation Outcome
- Frontend dependency refresh executed with `npm install --legacy-peer-deps`.
- Validation gates passed:
  - `npm run typecheck`
  - `npm run build`
- Runtime config wiring verified in production output:
  - `dist/runtime-config.js` present,
  - `dist/index.html` includes `/runtime-config.js`.
- Router cleanup verified:
  - no remaining `react-router-dom` or `@types/react-router-dom` references in `package.json`, `package-lock.json`, or `src`.

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
