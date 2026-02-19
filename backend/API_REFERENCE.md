# MFT Agent Service API Reference

This reference is aligned with the currently mounted routers in `src/main_agent.py`.

## Base URL

- Local: `http://localhost:8000`
- Deployed: your API domain

## Common Headers

- `Content-Type: application/json`
- `X-Admin-Key`: optional; required only if admin key enforcement is enabled
- `X-OpenRouter-Key`: optional per-request key for selected endpoints
- `X-Groq-Key`: optional per-request key for selected endpoints
- `X-Eval-Ingest-Key`: required only if `EVAL_INGEST_KEY` is configured

## Health and Monitoring

### `GET /health`

Basic health check.

Example response:

```json
{
  "status": "healthy",
  "service": "agent",
  "version": "2.0.0",
  "timestamp": 1739836800
}
```

### `GET /health/live`

Liveness probe.

```json
{
  "status": "alive",
  "service": "agent"
}
```

### `GET /health/ready`

Readiness probe with dependency checks (`redis`, optional `postgres`, optional `tor_exit_list`).

### `GET /metrics`

Prometheus metrics endpoint. Returns `404` if metrics are disabled.

## Agent Endpoints

### `POST /agent/query`

Non-streaming agent response.

Request:

```json
{
  "session_id": "sess_123",
  "question": "What are foreclosure charges?"
}
```

Response:

```json
{
  "response": "...",
  "provider": "openrouter",
  "model": "z-ai/glm-5",
  "kb_first": false,
  "router": {}
}
```

Notes:

- `router` is only present when inline router is enabled and exposed.
- `kb_first=true` indicates answer served directly from KB shortcut path.

### `POST /agent/stream`

Server-Sent Events stream.

Request:

```json
{
  "session_id": "sess_123",
  "question": "customer care"
}
```

Public SSE events:

- `reasoning` (optional; controlled by `AGENT_STREAM_EXPOSE_REASONING`)
- `tool_call`
- `token`
- `router` (optional; only if inline router expose is enabled)
- `cost`
- `done`
- `error`

Event payloads:

- `reasoning`:

```text
<string token/chunk>
```

- `tool_call`:

```json
{
  "name": "tool_name",
  "output": "tool output",
  "tool_call_id": "run-id"
}
```

- `token`:

```text
<string token/chunk>
```

- `cost`:

```json
{
  "total_cost": 0.001529,
  "usage": {
    "prompt_tokens": 1519,
    "completion_tokens": 275,
    "total_tokens": 1794,
    "reasoning_tokens": 146
  },
  "model": "z-ai/glm-5",
  "provider": "openrouter",
  "currency": "USD"
}
```

- `done`:

```json
{
  "status": "complete"
}
```

- `error`:

```json
{
  "message": "..."
}
```

Debug-only internal lifecycle events (only when `AGENT_STREAM_EXPOSE_INTERNAL_EVENTS=true`):

- `on_chat_model_start`, `on_chat_model_stream`, `on_chat_model_end`
- `on_tool_start`, `on_tool_end`
- `on_chain_start`, `on_chain_stream`, `on_chain_end`
- `on_llm_start`, `on_llm_stream`, `on_llm_end`
- `on_retriever_start`, `on_retriever_end`
- `on_prompt_start`, `on_prompt_end`

### `POST /agent/follow-up`

Generate follow-up questions (non-streaming).

Request:

```json
{
  "session_id": "sess_123",
  "question": "I want better EMI options"
}
```

Response:

```json
{
  "questions": ["...", "..."],
  "provider": "openrouter"
}
```

### `POST /agent/follow-up-stream`

SSE follow-up generation.

Events:

- `status` (plain text status)
- `token` (JSON string payload: `{"index": <int>, "token": "..."}`)
- `done` (data: `[DONE]`)
- `error`

## Session and Cost Endpoints

### `GET /agent/sessions`

List active sessions.

### `POST /agent/sessions/init`

- **Summary:** Initializes a new session entirely on the backend, returning a time-ordered UUIDv7 identifier and establishing the default BYOK (Bring Your Own Key) configuration state.
- **Success Response (200):**
  ```json
  {
    "session_id": "018e9a5a-6b2a-7c91-a1b2-13c4d5e6f7g8",
    "system_prompt": "- You are a helpful assistant...",
    "model_name": "openai/gpt-4o",
    "provider": "openrouter",
    "reasoning_effort": null,
    "message": "Session initialized with default BYOK configuration."
  }

### `GET /agent/verify/{session_id}`

Verify a session exists.

### `GET /agent/config/{session_id}`

Get effective session config and key-presence flags.

### `POST /agent/config`

Create/update session config.

Request model:

```json
{
  "session_id": "sess_123",
  "system_prompt": "optional",
  "model_name": "optional",
  "reasoning_effort": "optional",
  "provider": "groq | openrouter | nvidia",
  "openrouter_api_key": "optional",
  "nvidia_api_key": "optional",
  "groq_api_key": "optional"
}
```

### `DELETE /agent/logout/{session_id}`

Delete session config.

### `GET /agent/sessions/{session_id}/cost`

Aggregate cost and usage for session.

### `GET /agent/sessions/{session_id}/cost/history`

Chronological cost history (`limit` query param, `1..1000`, default `100`).

### `DELETE /agent/sessions/{session_id}/cost`

Reset session cost data.

### `GET /agent/sessions/summary`

Cross-session cost summary.

### `DELETE /agent/sessions/cleanup`

Admin cleanup for corrupted cost keys.

## Model and Router Endpoints

### `GET /agent/models`

Returns model catalog grouped by provider.

### `POST /agent/router/classify`

Classify query with NBFC router.

Request:

```json
{
  "session_id": "optional",
  "text": "query text",
  "mode": "embeddings | llm | hybrid | compare",
  "openrouter_api_key": "optional"
}
```

### `POST /agent/router/compare`

Compare router backends for same input.

## Admin / FAQ Endpoints

### `GET /agent/all-follow-ups`

Get cached follow-up datasets.

### `POST /agent/admin/faqs/batch-json`

Batch FAQ ingest via JSON.

Headers used by implementation:

- `X-Admin-Key`
- `X-Groq-Key`
- `X-OpenRouter-Key`

### `POST /agent/admin/faqs/upload-pdf`

PDF FAQ ingest with SSE progress events.

### `GET /agent/admin/faqs`

List FAQs (`limit`, `skip`).

### `PUT /agent/admin/faqs`

Edit FAQ.

### `DELETE /agent/admin/faqs`

Delete FAQ by exact `question` query param.

### `DELETE /agent/admin/faqs/all`

Delete all FAQs.

### `POST /agent/admin/faqs/semantic-search`

Semantic FAQ search.

### `POST /agent/admin/faqs/semantic-delete`

Semantic FAQ delete.

Error handling:

- `400` for missing key / invalid request shape
- `503` when Neo4j is unavailable
- `500` for generic KB operation failures

## Evaluation Endpoints (`/eval`)

Mounted endpoints:

- `POST /eval/ingest`
- `GET /eval/search`
- `GET /eval/sessions`
- `GET /eval/trace/{trace_id}`
- `GET /eval/fulltext`
- `POST /eval/vector-search`
- `GET /eval/metrics/summary`
- `GET /eval/metrics/failures`
- `GET /eval/question-types`

### `POST /eval/ingest`

Ingest trace/events/evals.

Response:

```json
{
  "status": "ok",
  "trace_id": "trace_123",
  "events": 5,
  "evals": 2
}
```

### `GET /eval/search`

Supports filters: `session_id`, `status`, `provider`, `model`, `case_id`, `metric_name`, `passed`, score ranges, ordering.

### `GET /eval/sessions`

Session-level summaries for traces.

### `GET /eval/trace/{trace_id}`

Detailed trace with compressed events and eval records.

### `GET /eval/fulltext`

Fulltext search by index kind (`event | trace | result`).

### `POST /eval/vector-search`

Vector similarity search over traces or eval results.

Request model:

```json
{
  "kind": "trace | result",
  "text": "optional if vector provided",
  "vector": [0.1, 0.2],
  "k": 10,
  "min_score": 0.0,
  "provider": "optional",
  "model": "optional",
  "status": "optional",
  "metric_name": "optional",
  "passed": true,
  "session_id": "optional",
  "case_id": "optional"
}
```

Notes:

- If `vector` is omitted, service embeds `text` using OpenRouter and `X-OpenRouter-Key` (or server key).
- Returns `400` when neither `vector` nor `text` is provided.
- Returns `400` when embedding key is unavailable.

### `GET /eval/metrics/summary`

Aggregated pass-rate and score summaries.

### `GET /eval/metrics/failures`

Failure list with provider/model/session context.

### `GET /eval/question-types`

Distribution by router reason class.

Evaluation error body pattern:

```json
{
  "detail": {
    "code": "neo4j_unavailable",
    "operation": "eval_search_items",
    "message": "...",
    "hint": "Verify Neo4j container health and bolt connectivity on neo4j:7687."
  }
}
```

## Rate Limiting Endpoints (`/rate-limit`)

### `GET /rate-limit/metrics`

Returns live limiter metrics.

### `GET /rate-limit/status/{identifier}`

Returns limiter status for an identifier.

### `POST /rate-limit/reset/{identifier}`

Resets limiter state for an identifier.

### `GET /rate-limit/health`

Health probe for rate limit infrastructure.

### `GET /rate-limit/config`

Returns effective rate-limit configuration.

## GraphQL Endpoint

### `GET /graphql`

GraphQL IDE (when enabled by deployment).

### `POST /graphql`

GraphQL query/mutation endpoint.
