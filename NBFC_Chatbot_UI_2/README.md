# NBFC Chatbot UI

Production-grade React 18 + Tailwind CSS v4 + shadcn/ui frontend for the TrustFin NBFC chatbot.

## Running locally

```bash
npm install
npm run dev
```

## Building for production

```bash
npm run build
npm run preview
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_PROXY_TARGET` | `http://localhost:8000` | Backend agent service URL |
| `VITE_API_BASE_URL` | `/api` | API base path |
