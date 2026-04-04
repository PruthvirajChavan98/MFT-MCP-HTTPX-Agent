# NBFC Chatbot UI

Production-grade React 19 + Tailwind CSS v4 + shadcn/ui frontend for the Mock FinTech NBFC chatbot.

## Running locally

```bash
node --version # 22.12.0 or newer
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
