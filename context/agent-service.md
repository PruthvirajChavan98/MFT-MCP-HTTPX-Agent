# Agent Service

## 28 Endpoints

### Core Agent (5)
- `POST /agent/query` — non-streaming ReAct agent
- `POST /agent/stream` — SSE streaming ReAct agent (**primary endpoint**)
- `POST /agent/follow-up` — non-streaming follow-up generation
- `POST /agent/follow-up-stream` — SSE streaming follow-ups
- `GET /agent/all-follow-ups` — cached follow-up list

### Session Management (7)
- `GET /agent/sessions`, `/verify/{sid}`, `/config/{sid}`
- `POST /agent/config/groq`, `/openrouter`, `/nvidia`
- `DELETE /agent/logout/{sid}`

### NBFC Router (2)
- `POST /agent/router/classify`, `/compare`

### KB Admin (7)
- `POST /admin/faqs/batch-json`, `/upload-pdf`
- `GET /admin/faqs`
- `PUT /admin/faqs`, `DELETE /admin/faqs`, `DELETE /admin/faqs/all`
- `POST /admin/faqs/semantic-search`, `/semantic-delete`

### Eval (7 — mounted from sub-routers)
- `POST /eval/ingest`
- `GET /eval/search`, `/sessions`, `/trace/{id}`, `/fulltext`
- `POST /eval/vector-search`
- `GET /eval/metrics/summary`, `/metrics/failures`, `/question-types`
- ⚠️ `GET /eval/live` — **NOT MOUNTED** (F12)

### Catalog (2)
- `GET /agent/models`
- `/graphql` — Strawberry GraphQL

## Auth-Gated Tool System
`mcp_manager.rebuild_tools_for_user(session_id)` checks Redis for `access_token`:
- **Unauthenticated**: only `generate_otp`, `validate_otp`, `is_logged_in`, `mock_fintech_knowledge_base`
- **Authenticated**: all 12 MCP tools + graph_rag
