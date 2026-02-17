# HFCL Agent Service API Reference

## Introduction

This document provides a reference for the HFCL Agent Service API. The service provides a comprehensive set of endpoints for agent interaction, session management, and system evaluation.

**Base URLs:**
- Development: `http://localhost:8000`
- Docker: `http://localhost:8005`

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
    "response": { ... },
    "router": { ... },
    "provider": "openrouter"
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
  - `cost`: Provides cost information for the request.
  - `router`: Contains the output of the classification router.
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
            "provider": "openrouter"
          }
        ]
      }
    ]
  }
  ```

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

### `POST /agent/config`

- **Summary:** Creates or updates a session's configuration.
- **Request Body:**
  ```json
  {
    "session_id": "sess_12345",
    "system_prompt": "You are a helpful assistant.",
    "model_name": "openai/gpt-4o",
    "provider": "openrouter",
    "openrouter_api_key": "sk-or-..."
  }
  ```

### `DELETE /agent/logout/{session_id}`

- **Summary:** Deletes a session's configuration.

### Costing Endpoints

- **`GET /agent/sessions/{session_id}/cost`**: Get aggregate cost for a session.
- **`GET /agent/sessions/{session_id}/cost/history`**: Get chronological cost history.
- **`DELETE /agent/sessions/{session_id}/cost`**: Reset cost tracking for a session.
- **`GET /agent/sessions/summary`**: Get a cost summary for all sessions.
- **`DELETE /agent/sessions/cleanup`**: Admin endpoint to clean up corrupted cost keys.

---

## Router API

### `POST /agent/router/classify`

- **Summary:** Classifies a query using the NBFC router.

### `POST /agent/router/compare`

- **Summary:** Compares router classifications.

---

## Admin API

### Follow-ups

#### `GET /agent/all-follow-ups`

- **Summary:** Retrieves all cached follow-up questions.

### Knowledge Base (FAQ) Management

- **`POST /agent/admin/faqs/batch-json`**: Ingests a batch of FAQs from a JSON object.
- **`POST /agent/admin/faqs/upload-pdf`**: Ingests FAQs from a PDF file.
- **`GET /agent/admin/faqs`**: Retrieves all FAQs.
- **`PUT /agent/admin/faqs`**: Edits an existing FAQ.
- **`DELETE /agent/admin/faqs`**: Deletes an FAQ by its question.
- **`DELETE /agent/admin/faqs/all`**: Clears all FAQs from the knowledge base.
- **`POST /agent/admin/faqs/semantic-search`**: Performs a semantic search on the FAQs.
- **`POST /agent/admin/faqs/semantic-delete`**: Deletes an FAQ based on a semantic query.

---

## Evaluation API (`/eval` prefix)

### `POST /eval/ingest`

- **Summary:** Ingests evaluation data, including traces, events, and results. Requires `X-Eval-Ingest-Key` header for authentication if configured.

### `GET /eval/live`

- **Summary:** Provides a real-time SSE feed of ingested evaluation traces.

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
