# Project Architecture & Global Conventions

> Production enterprise AI agent service — modular, async-first, multi-provider.

## Monorepo Layout

```
├── backend/
│   └── src/
│       ├── agent_service/          # FastAPI agent — API, LLM, security, eval, features
│       │   ├── api/                # REST + GraphQL endpoints
│       │   │   └── endpoints/      # Streaming, sessions, health, rate-limit, admin
│       │   ├── core/               # App factory, config, schemas, singletons
│       │   ├── features/           # NBFC router, answerability, shadow eval, follow-up
│       │   ├── llm/                # Multi-provider LLM client (OpenRouter, Anthropic, etc.)
│       │   ├── router/             # NBFC semantic routing with worker
│       │   ├── security/           # Middleware, session security, GeoIP, Tor, rate-limit
│       │   ├── tools/              # MCP manager & tool lifecycle
│       │   └── worker/             # Background worker processes
│       ├── mcp_service/            # FastMCP server — FinTech tools via SSE on port 8050
│       └── common/                 # Shared utilities and data structures
│   └── tests/                      # Pytest suite (16 test modules)
├── Chatbot UI and Admin Console/   # Vite 7 + React 19 + TypeScript frontend
│   └── src/
│       ├── app/components/         # Chat widget, admin console, trace viewer
│       ├── hooks/                  # Custom React hooks
│       ├── shared/                 # API service, utilities
│       └── styles/                 # TailwindCSS 4 + custom styles
├── k8s/                            # Kubernetes manifests (HPA, ingress, network policies)
├── docker-compose.local.yml        # Local dev stack
├── docker-compose.uat.yml          # UAT environment
├── docker-compose.prod.yml         # Production stack
└── backend/Makefile                # All build, test, and deploy commands
```

## Entry Points

| Service          | File                       | Port | Server             |
|------------------|----------------------------|------|---------------------|
| Agent API        | `backend/src/main_agent.py`| 8000 | Gunicorn + Uvicorn  |
| MCP Server       | `backend/src/main_mcp.py`  | 8050 | Uvicorn             |
| Frontend (prod)  | `nginx.conf`               | 80   | Nginx               |

## Key Singletons & Factories

- `app_factory` — Creates and configures the FastAPI app, mounts all routers
- `mcp_manager` — Manages MCP connections, dynamic tool rebuilds per-user
- `config_manager` — Redis-based runtime config management
- `model_service` — LLM provider catalog and cost tracking
- `event_bus` — Internal async pub/sub
- `rate_limiter_manager` — Per-identity rate limiting (Redis-backed)

## Configuration (Critical Pattern)

All config lives in `backend/src/agent_service/core/config.py`. Variables are read from `os.getenv()` **once** and exported as module-level constants.

```python
# ✅ Always import constants
from src.agent_service.core.config import REDIS_URL, PORT

# ❌ Never call os.getenv() in business logic
```

## Dependency Management

- **Package manager**: `uv` (Astral) — never raw `pip`
- **Install**: `uv sync`
- **Run commands**: `uv run <command>`
- **Lock file**: `uv.lock` (committed to repo)
- **Python**: 3.11+

## Code Quality Toolchain

| Tool   | Purpose          | Config Location    |
|--------|------------------|--------------------|
| Black  | Formatting       | `pyproject.toml`   |
| isort  | Import sorting   | `pyproject.toml`   |
| Ruff   | Linting + fixes  | `pyproject.toml`   |
| mypy   | Type checking    | `pyproject.toml`   |

Line length: **100 chars**. Target: **Python 3.11**.
