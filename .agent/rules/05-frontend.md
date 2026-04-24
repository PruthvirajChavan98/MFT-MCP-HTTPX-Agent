# Frontend Standards — Chatbot UI & Admin Console

> Applies to `Agent UI and Admin Console/src/**`.

## Tech Stack

| Layer       | Technology                                        |
|-------------|---------------------------------------------------|
| Framework   | React 19 + TypeScript 5.9                         |
| Build       | Vite 7 + `@vitejs/plugin-react`                   |
| Styling     | TailwindCSS 4 (`@tailwindcss/vite`)               |
| Components  | Radix UI primitives + MUI (icons, data display)   |
| State       | TanStack React Query v5 (server state)            |
| Routing     | React Router v7                                   |
| Animations  | motion (framer-motion successor)                  |
| Charts      | Recharts                                          |
| Testing     | Vitest + Testing Library + jsdom                   |

## Project Structure

```
src/
├── app/
│   ├── App.tsx              # Root component
│   ├── routes.ts            # Route definitions (React Router v7)
│   └── components/          # All UI components
│       ├── admin/           # Admin console pages
│       ├── chat/            # Chat widget & conversation UI
│       └── ...
├── hooks/                   # Custom React hooks
├── shared/                  # API service layer, utilities
│   └── api.ts               # Backend API client (fetch + SSE)
├── styles/                  # Global CSS + TailwindCSS config
├── test/                    # Test setup
└── main.tsx                 # Entry point
```

## Conventions

### Imports
- Use `@/` path alias for absolute imports (resolves to `./src/`).
- Prefer named exports. Default exports only for page-level components.

### API Layer
- All API calls go through `shared/api.ts`.
- Backend base URL: `/api` in dev (Vite proxy), runtime-injected in prod (Nginx).
- Use `@tanstack/react-query` for all server state — never `useState` + `useEffect` for data fetching.
- SSE streaming uses `@microsoft/fetch-event-source`.

### Component Patterns
- Use Radix UI primitives for accessible, unstyled base components.
- MUI is used selectively for icons (`@mui/icons-material`) and complex data components.
- Style with TailwindCSS utility classes — use `class-variance-authority` for variant patterns.
- Use `tailwind-merge` (`cn()` helper) to merge conditional classnames.

### Routing
- Routes defined in `app/routes.ts`.
- Use React Router v7 data patterns (loaders/actions) where applicable.

## Production Build

- **Build**: `npm run build` → TypeScript check + Vite build
- **Serving**: Nginx (multi-stage Docker build via `Dockerfile.prod`)
- **Runtime config**: Injected via `docker-entrypoint-runtime-config.sh` at container startup
- **Chunk splitting**: Manual chunks defined in `vite.config.ts` for vendor optimization

## Nginx Integration

- `/api/*` requests are reverse-proxied to the `agent` service.
- `/api/agent/stream` has special SSE-safe proxy settings (`proxy_buffering off`).
- Rate limiting at Nginx is for volumetric defense only — per-user quotas stay in FastAPI.
- Route precedence: streaming routes **above** generic `/api/` catch-all.
