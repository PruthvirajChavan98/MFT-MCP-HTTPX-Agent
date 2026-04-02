# Monorepo Layout

- `backend/`: Python/FastAPI/MCP backend project.
- `Chatbot UI and Admin Console/`: React 19 + Vite frontend (prod build).
- `compose.yaml`: Single compose file for all environments (profiles: local, deployed, uat, prod, monitoring).
- `.env`: Base env vars — source of truth.
- `.env.local` / `.env.uat` / `.env.prod`: Environment overlays.

## Backend

Run backend application commands from `backend/`.

Compose orchestration is centralized at repo root — use `backend/Makefile` targets:

```bash
make local-up          # start local core stack
make localsetup        # validate + start + run setup checks
make uat-up            # start UAT stack
make prod-up           # start prod stack
```

## Frontend

The production frontend lives in `Chatbot UI and Admin Console/`. It is built by the `frontend-prod` service (profile: prod).

For local frontend development, run directly from the UI directory:

```bash
cd "Chatbot UI and Admin Console"
npm install
npm run dev
```

## Root Compose

Single `compose.yaml` with environment profiles. Use `backend/Makefile` targets or run directly:

```bash
# Local
docker compose --env-file .env --env-file .env.local -f compose.yaml --profile local up -d

# UAT
docker compose --env-file .env --env-file .env.uat -f compose.yaml --profile deployed --profile uat --profile monitoring up -d

# Prod
docker compose --env-file .env --env-file .env.prod -f compose.yaml --profile deployed --profile prod --profile monitoring up -d
```

Frontend calls backend through `/api` proxy:

- Browser → `frontend-prod` (`:80`) → `/api/...`
- Nginx proxy → `agent:8000`

## Cloudflare Tunnel

The tunnel config (`cloudflared/config.yml`) routes public hostnames to the agent. `cloudflared-prod` (profile: prod) handles production traffic via `cloudflared-local` (profile: edge) for local tunnelling.
