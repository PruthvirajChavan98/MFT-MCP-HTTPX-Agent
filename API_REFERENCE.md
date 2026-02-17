# HFCL Agent Service API Reference

## Introduction

This document provides a reference for the HFCL Agent Service API. The service provides a comprehensive set of endpoints for agent interaction, session management, and system evaluation.

**Base URLs:**
- Development: `http://localhost:8000`
- Docker: `http://localhost:8005`

---

## Data Structures

### TokenUsage

Token consumption breakdown for LLM requests.

```json
{
  "prompt_tokens": 150,
  "completion_tokens": 75,
  "total_tokens": 225,
  "reasoning_tokens": 50,        // Optional: For DeepSeek R1, O1, Qwen reasoning models
  "cached_tokens": 100            // Optional: Cache hits for Claude/Gemini prompt caching
}
```

### CostBreakdown

Complete cost breakdown with pricing details.

```json
{
  "prompt_cost": 0.00015,
  "completion_cost": 0.00020,
  "reasoning_cost": 0.00010,      // Optional: Cost of reasoning tokens (when applicable)
  "cached_cost": 0.00005,         // Optional: Cost of cached tokens (usually 50% discount)
  "total_cost": 0.00050,
  "model": "openai/gpt-4o",
  "provider": "openrouter",
  "currency": "USD",
  "free_tier": false,             // Whether this request used free tier (Groq/NVIDIA)
  "usage": { /* TokenUsage object */ },
  "pricing_rates": {              // Per-token pricing rates
    "prompt_per_token": 0.000001,
    "completion_per_token": 0.0000027,
    "prompt_per_1m": 1.00,
    "completion_per_1m": 2.70
  }
}
```

### RouterResult

Classification router output.

```json
{
  "backend": "llm_glm_4.7",       // Backend used: "embeddings", "llm_glm_4.7", "hybrid"
  "sentiment": {
    "label": "positive",
    "score": 0.85,
    "top": [["positive", 0.85], ["neutral", 0.12]]
  },
  "reason": {                     // Optional: Classification reason/category
    "label": "loan_inquiry",
    "score": 0.92
  },
  "embeddings": { /* ... */ },    // Optional: Embeddings-based result
  "llm": { /* ... */ },           // Optional: LLM-based result
  "disabled": false               // Optional: Whether router is disabled
}
```

---

## Core Agent API

### Agent Interaction

#### `POST /agent/query`

- **Summary:** Submits a query to the agent and receives a complete, non-streamed response.
- **Request Body:**
  ```json
  {
    "session_id": "sess_12345",
    "question": "What is the capital of France?"
  }
  ```
- **Success Response (200):**
  ```json
  {
    "response": { /* Agent response object */ },
    "router": { /* RouterResult object (optional) */ },
    "provider": "openrouter",
    "kb_first": false                          // Optional: true if response from KB guardrail
  }
  ```
- **Alternative Response (KB-First Cached):**
  ```json
  {
    "response": "Answer from knowledge base",
    "kb_first": true,
    "router": { /* ... */ }
  }
  ```

#### `POST /agent/stream`

- **Summary:** Submits a query and receives a streamed response using Server-Sent Events (SSE). The stream includes tokens, tool calls, and cost information.
- **Request Body:**
  ```json
  {
    "session_id": "sess_12345",
    "question": "What is the capital of France?"
  }
  ```
- **SSE Events:**
  - `token`: A text token from the response.
  - `reasoning_token`: A token related to the agent's reasoning process.
  - `tool_start`: Indicates the start of a tool call.
  - `tool_end`: Indicates the end of a tool call.
  - `cost`: Provides detailed cost information for the request.
    ```json
    {
      "total_cost": 0.002,
      "usage": {
        "prompt_tokens": 150,
        "completion_tokens": 75,
        "total_tokens": 225,
        "reasoning_tokens": 20,              // Optional: for reasoning models
        "cached_tokens": 50                  // Optional: for cache hits
      },
      "model": "openai/gpt-4o",
      "provider": "openrouter",
      "currency": "USD",
      "cached": false                        // Whether prompt caching was used
    }
    ```
  - `router`: Contains the output of the classification router (RouterResult object).
  - `done`: Indicates the end of the stream.
  - `error`: Sent if an error occurs during the stream.

### Follow-Up Questions

#### `POST /agent/follow-up`

- **Summary:** Generates a list of suggested follow-up questions based on the conversation history.
- **Request Body:**
  ```json
  {
    "session_id": "sess_12345",
    "question": "What was the previous topic?"
  }
  ```
- **Success Response (200):**
  ```json
  {
    "questions": [
      "Can you elaborate on that?",
      "What are the alternatives?"
    ],
    "provider": "openrouter"
  }
  ```

#### `POST /agent/follow-up-stream`

- **Summary:** Generates and streams follow-up questions as they are created.
- **Request Body:**
  ```json
  {
    "session_id": "sess_12345",
    "question": "What was the previous topic?"
  }
  ```
- **SSE Events:**
  - `question`: A suggested follow-up question.
  - `done`: Indicates the end of the stream.
  - `error`: Sent if an error occurs.

---

## System & Configuration

### `GET /health`

- **Summary:** A simple health check endpoint.
- **Success Response (200):**
  ```json
  {
    "status": "healthy",
    "service": "agent",
    "version": "2.0.0"
  }
  ```

### `GET /agent/models`

- **Summary:** Lists all available models from the catalog, grouped by provider.
- **Success Response (200):**
  ```json
  {
    "count": 132,
    "categories": [
      {
        "name": "openrouter",
        "models": [
          {
            "id": "openai/gpt-4o",
            "name": "gpt-4o",
            "provider": "openrouter",
            "context_length": 128000,
            "pricing": {
              "prompt": 5.0,              // USD per 1M tokens
              "completion": 15.0,
              "unit": "1M tokens"
            },
            "supported_parameters": ["temperature", "max_tokens", "top_p"],
            "modality": "text",           // "text", "multimodal", etc.
            "type": "chat"                // "chat", "reasoning", etc.
          }
        ]
      }
    ]
  }
  ```

**Note**: The GraphQL endpoint at `/graphql` provides access to additional model metadata including `parameter_specs` and `architecture` details.

### `POST /graphql`

- **Summary:** A GraphQL endpoint for querying model information.
- **Query Example:**
  ```graphql
  query {
    models(provider: "openrouter") {
      name
      models {
        id
        name
        provider
      }
    }
  }
  ```

---

## Session Management & Costing

### `GET /agent/sessions`

- **Summary:** Lists all active session IDs.

### `GET /agent/verify/{session_id}`

- **Summary:** Checks if a session exists.

### `GET /agent/config/{session_id}`

- **Summary:** Retrieves the configuration for a specific session.
- **Success Response (200):**
  ```json
  {
    "session_id": "sess_xxx",
    "system_prompt": "string",
    "model_name": "string",
    "reasoning_effort": "string or null",               // Reasoning effort level
    "has_openrouter_key": false,                        // Whether OpenRouter key configured
    "has_nvidia_key": false,                            // Whether NVIDIA key configured
    "has_groq_key": false,                              // Whether Groq key configured
    "provider": "string or null",
    "is_customized": true                               // Whether session has custom config
  }
  ```

### `POST /agent/config`

- **Summary:** Creates or updates a session's configuration.
- **Request Body:**
  ```json
  {
    "session_id": "sess_12345",
    "system_prompt": "You are a helpful assistant.",    // Optional
    "model_name": "openai/gpt-4o",                      // Optional
    "reasoning_effort": "high",                         // Optional: For O1/DeepSeek reasoning models
    "provider": "openrouter",                           // Optional: "groq", "openrouter", "nvidia"
    "openrouter_api_key": "sk-or-...",                  // Optional: Bring your own key
    "nvidia_api_key": "nvapi-...",                      // Optional: NVIDIA API key
    "groq_api_key": "gsk_..."                           // Optional: Groq API key
  }
  ```

### `DELETE /agent/logout/{session_id}`

- **Summary:** Deletes a session's configuration.

### Costing Endpoints

#### `GET /agent/sessions/{session_id}/cost`

Get aggregate cost for a session with detailed breakdown.

- **Success Response (200):**
  ```json
  {
    "session_id": "sess_xxx",
    "total_cost": 0.025,
    "total_requests": 15,
    "total_tokens": 12500,
    "total_prompt_tokens": 8000,
    "total_completion_tokens": 4000,
    "total_reasoning_tokens": 500,              // Reasoning tokens across all requests
    "total_cached_tokens": 2000,                // Cache hits across all requests
    "by_model": {
      "openai/gpt-4o": {
        "cost": 0.015,
        "requests": 10,
        "tokens": 10000,
        "prompt_tokens": 6000,
        "completion_tokens": 3500,
        "reasoning_tokens": 500
      }
    },
    "by_provider": {
      "openrouter": {
        "cost": 0.015,
        "requests": 10,
        "tokens": 10000,
        "free_tier": false
      },
      "groq": {
        "cost": 0.0,
        "requests": 5,
        "tokens": 2500,
        "free_tier": true                      // Groq free tier usage
      }
    },
    "first_request_at": "2024-01-15T10:30:00Z",
    "last_request_at": "2024-01-15T14:45:00Z",
    "version": "1.0",
    "average_cost_per_request": 0.00167       // Computed average
  }
  ```

#### `GET /agent/sessions/{session_id}/cost/history`

Get chronological cost history for a session.

- **Parameters:**
  - Query: `limit` (int, 1-1000, default=100) - Maximum entries to return

- **Success Response (200):**
  ```json
  {
    "session_id": "sess_xxx",
    "history": [
      {
        "timestamp": "2024-01-15T10:30:00Z",
        "cost": 0.002,
        "model": "openai/gpt-4o",
        "provider": "openrouter",
        "usage": {
          "prompt_tokens": 150,
          "completion_tokens": 75,
          "total_tokens": 225,
          "reasoning_tokens": 20,            // Present if > 0
          "cached_tokens": 50                // Present if > 0
        },
        "metadata": {}
      }
    ],
    "count": 15
  }
  ```

#### `DELETE /agent/sessions/{session_id}/cost`

Reset cost tracking for a session.

- **Success Response (200):**
  ```json
  {
    "session_id": "sess_xxx",
    "status": "reset",
    "message": "Cost tracking reset successfully"
  }
  ```

#### `GET /agent/sessions/summary`

Get a cost summary for all sessions.

- **Success Response (200):**
  ```json
  {
    "active_sessions": 10,
    "total_cost": 0.125,
    "total_requests": 150,
    "sessions": [
      {
        "session_id": "sess_xxx",
        "total_cost": 0.025,
        "total_requests": 15,
        "last_request_at": "2024-01-15T14:45:00Z"
      }
    ]
  }
  ```

#### `DELETE /agent/sessions/cleanup`

Admin endpoint to clean up corrupted cost keys.

- **Success Response (200):**
  ```json
  {
    "status": "cleanup_complete",
    "deleted_keys": 5,
    "keys": ["key1", "key2"]
  }
  ```

---

## Router API

### `POST /agent/router/classify`

- **Summary:** Classifies a query using the NBFC router.

### `POST /agent/router/compare`

- **Summary:** Compares router classifications.

---

## Admin API

### Authentication Headers

Admin endpoints support optional authentication headers:

- **`X-Admin-Key`**: Admin authentication key (required if `ADMIN_KEY` environment variable is set)
- **`X-OpenRouter-Key`**: OpenRouter API key for embedding/LLM operations
- **`X-Groq-Key`**: Groq API key for embedding/LLM operations
- **`X-Eval-Ingest-Key`**: Evaluation ingest authentication key (required if `EVAL_INGEST_KEY` is set)

**Example:**
```bash
curl -X POST /agent/admin/faqs/batch-json \
  -H "X-Admin-Key: your-admin-key" \
  -H "X-OpenRouter-Key: your-or-key" \
  -d '{"items": [...]}'
```

### Follow-ups

#### `GET /agent/all-follow-ups`

- **Summary:** Retrieves all cached follow-up questions.

### Knowledge Base (FAQ) Management

#### `POST /agent/admin/faqs/batch-json`

Ingests a batch of FAQs from a JSON object.

- **Headers:**
  - `X-Admin-Key` (optional, required if admin key configured)
  - `X-Groq-Key` (optional, for embeddings)
  - `X-OpenRouter-Key` (optional, for embeddings)

#### `POST /agent/admin/faqs/upload-pdf`

Ingests FAQs from a PDF file.

- **Headers:**
  - `X-Admin-Key` (optional, required if admin key configured)
  - `X-Groq-Key` (optional, for embeddings)
  - `X-OpenRouter-Key` (optional, for embeddings)

#### `GET /agent/admin/faqs`

Retrieves all FAQs.

- **Parameters:**
  - Query: `limit` (int, 1-1000, default=100) - Maximum FAQs to return
  - Query: `skip` (int, >=0, default=0) - Number of FAQs to skip (pagination)

#### `PUT /agent/admin/faqs`

Edits an existing FAQ.

- **Headers:**
  - `X-Admin-Key` (optional, required if admin key configured)
  - `X-OpenRouter-Key` (optional, for embeddings)

#### `DELETE /agent/admin/faqs`

Deletes an FAQ by its question.

- **Headers:**
  - `X-Admin-Key` (optional, required if admin key configured)
- **Parameters:**
  - Query: `question` (string, required) - Exact question text to delete

#### `DELETE /agent/admin/faqs/all`

Clears all FAQs from the knowledge base.

- **Headers:**
  - `X-Admin-Key` (optional, required if admin key configured)

#### `POST /agent/admin/faqs/semantic-search`

Performs a semantic search on the FAQs.

- **Headers:**
  - `X-OpenRouter-Key` (optional, for embeddings)

#### `POST /agent/admin/faqs/semantic-delete`

Deletes an FAQ based on a semantic query.

- **Headers:**
  - `X-Admin-Key` (optional, required if admin key configured)
  - `X-OpenRouter-Key` (optional, for embeddings)

---

## Evaluation API (`/eval` prefix)

### `POST /eval/ingest`

- **Summary:** Ingests evaluation data, including traces, events, and results.
- **Headers:**
  - `X-Eval-Ingest-Key` (required if `EVAL_INGEST_KEY` environment variable is set)

- **Request Body:**
  ```json
  {
    "trace": {
      "trace_id": "trace_abc123",         // Required
      "status": "completed",              // Optional: "completed", "failed", "running"
      "started_at": "2024-01-15T10:30:00Z",
      "provider": "openrouter",
      "model": "openai/gpt-4o",
      "endpoint": "/agent/query",
      "session_id": "sess_12345",
      "case_id": "test_case_001"
    },
    "events": [
      {
        "trace_id": "trace_abc123",
        "seq": 1,
        "ts": "2024-01-15T10:30:01Z",
        "event_type": "llm_request",
        "name": "query_start",
        "text": "User asked: What is the capital?",
        "payload": {},                   // Additional data
        "meta": {}                       // Metadata
      }
    ],
    "evals": [
      {
        "eval_id": "eval_xyz789",
        "trace_id": "trace_abc123",
        "metric_name": "accuracy",
        "score": 0.95,
        "passed": true,
        "reasoning": "Response was factually correct",
        "evaluator_id": "gpt-4o-judge",
        "evidence": [],
        "meta": {}
      }
    ]
  }
  ```

- **Success Response (200):**
  ```json
  {
    "status": "ok",
    "trace_id": "trace_abc123",
    "events": 5,
    "evals": 2
  }
  ```

- **Error Codes:**
  - `400`: Missing required trace_id
  - `401`: Invalid or missing X-Eval-Ingest-Key

### `GET /eval/live`

- **Summary:** Provides a real-time SSE feed of ingested evaluation traces.
- **Parameters:**
  - Query: `cursor` (string, default="$") - Redis stream cursor. Use "$" for only new events, "0-0" to replay all.
  - Header: `Last-Event-ID` (optional) - Resume from last received event ID

- **SSE Events:**
  - `hello`: Connection confirmation
    ```json
    {
      "stream": "eval:live",
      "cursor": "1234567890-0"
    }
    ```
  - `trace`: New trace ingested
    ```json
    {
      "id": "1234567890-0",
      "trace_id": "trace_abc123",
      "status": "completed",
      "provider": "openrouter",
      "model": "openai/gpt-4o",
      "endpoint": "/agent/query",
      "session_id": "sess_12345",
      "case_id": "test_case_001",
      "event_count": 5,
      "eval_count": 2,
      "pass_count": 2,
      "pass_rate": 1.0
    }
    ```
  - `error`: Error occurred

### Evaluation Data Retrieval

- **`GET /eval/search`**: Searches for evaluation traces with various filters.
- **`GET /eval/sessions`**: Lists sessions that have evaluation traces.
- **`GET /eval/trace/{trace_id}`**: Retrieves a specific trace by its ID.
- **`GET /eval/fulltext`**: Performs a full-text search on evaluation data.
- **`POST /eval/vector-search`**: Performs a vector-based search on traces or results.

### Evaluation Metrics

- **`GET /eval/metrics/summary`**: Get a summary of evaluation metrics.
- **`GET /eval/metrics/failures`**: Get a list of failed evaluations.
- **`GET /eval/question-types`**: Get statistics on the types of questions evaluated.