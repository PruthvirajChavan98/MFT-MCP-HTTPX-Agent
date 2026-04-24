# Monorepo Layout

- `backend/`: Python/FastAPI/MCP backend project.
- `Agent UI and Admin Console/`: React 19 + Vite frontend (prod build).
- `compose.yaml`: Single compose file. All services run without profiles — there is one deployed environment (prod).
- `.env`: Base env vars — source of truth; shared by local and prod.
- `.env.local`: Local-dev-only overrides.

## Backend

Run backend application commands from `backend/`.

Compose orchestration is centralized at repo root — use `backend/Makefile` targets:

```bash
make local-up          # start local core stack
make localsetup        # validate + start + run setup checks
make prod-up           # start prod stack (the only deployed environment)
make deploy-prod       # rebuild + force-recreate prod
```

## Frontend

The production frontend lives in `Agent UI and Admin Console/`. It is built by the `frontend-prod` service (profile: prod).

For local frontend development, run directly from the UI directory:

```bash
cd "Agent UI and Admin Console"
npm install
npm run dev
```

## Root Compose

Single `compose.yaml`. All services run without profiles — one deployed environment (prod). Use `backend/Makefile` targets or run directly:

```bash
# Local (core services only)
docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local up -d

# Prod (the only deployed environment)
docker compose --env-file .env -f compose.yaml up -d
```

Frontend calls backend through `/api` proxy:

- Browser → `frontend-prod` (`:80`) → `/api/...`
- Nginx proxy → `agent:8000`

## Cloudflare Tunnel

The tunnel config (`cloudflared/config.yml`) routes public hostnames to the stack:

- `mft-agent.pruthvirajchavan.codes` → `frontend-prod:80`
- `mft-api.pruthvirajchavan.codes` → `agent:8000`
