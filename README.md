# Monorepo Layout

- `backend/`: Existing Python/FastAPI/MCP backend project.
- `frontend/`: SolidJS + TypeScript + Tailwind CSS v4 frontend project.
- `docker-compose.yml`: Root production-style orchestration for backend + frontend.
- `docker-compose.local.yml`: Root local orchestration for backend + frontend.

## Backend

Run all backend commands from `backend/`.

## Frontend

Run all frontend commands from `frontend/`:

```bash
npm install
npm run dev
```

## Root Compose

Run the full local stack from repo root:

```bash
docker compose -f docker-compose.local.yml up -d
```

Run the full production-style stack from repo root:

```bash
docker compose -f docker-compose.yml up -d
```

Frontend calls backend through `/api` proxy:

- Browser -> `frontend` (`/api/...`)
- Frontend proxy -> `agent:8000`

## Cloudflare Tunnel

The root tunnel config (`cloudflared/config.yml`) exposes only the frontend hostname.
Backend stays private and is reached internally via frontend proxy.
