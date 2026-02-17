Here are the plain cURL calls for the **HFCL Agent Service** (Port 8000).

**Note:**

1. Port `8000` is used based on `Makefile` (`make dev`) and `gunicorn.conf.py`. If running via Docker Compose, check if you mapped it to `8005`.
2. Replace placeholders like `YOUR_SESSION_ID`, `YOUR_API_KEY`, etc. with actual values.

### 1. Health & System

```bash
# Health Check
curl -X GET "http://localhost:8000/health"

```

### 2. Agent Interaction (Chat)

**Note:** First, configure your session using the `/agent/config` endpoint. Then, use the following endpoints for queries.

```bash
# Non-Streaming Query (Standard Chat)
curl -X POST "http://localhost:8000/agent/query" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_12345",
    "question": "What are the foreclosure charges for my loan?"
  }'

# Streaming Query (Server-Sent Events)
curl -N -X POST "http://localhost:8000/agent/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_12345",
    "question": "Generate an OTP for 9000000001"
  }'

```

### 3. Session Management

```bash
# List Active Sessions
curl -X GET "http://localhost:8000/agent/sessions"

# Verify Session Exists
curl -X GET "http://localhost:8000/agent/verify/sess_12345"

# Get Session Configuration
curl -X GET "http://localhost:8000/agent/config/sess_12345"

# Update/Set Session Configuration
curl -X POST "http://localhost:8000/agent/config" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_12345",
    "system_prompt": "Reply in Hindi only.",
    "model_name": "deepseek/deepseek-r1",
    "reasoning_effort": "high",
    "provider": "openrouter",
    "openrouter_api_key": "sk-or-...",
    "nvidia_api_key": null,
    "groq_api_key": null
  }'

# Logout (Clear Session)
curl -X DELETE "http://localhost:8000/agent/logout/sess_12345"

```

### 4. Cost Tracking

```bash
# Get Session Cost Summary
curl -X GET "http://localhost:8000/agent/sessions/sess_12345/cost"

# Get Session Cost History
curl -X GET "http://localhost:8000/agent/sessions/sess_12345/cost/history?limit=50"

# Reset Session Cost
curl -X DELETE "http://localhost:8000/agent/sessions/sess_12345/cost"

# Global Cost Summary (All Sessions)
curl -X GET "http://localhost:8000/agent/sessions/summary"

# Cleanup Corrupted Cost Keys (Admin)
curl -X DELETE "http://localhost:8000/agent/sessions/cleanup"

```

### 5. NBFC Router (Classification)

```bash
# Classify Text (Determine Sentiment & Intent)
# Modes: embeddings | llm | hybrid
curl -X POST "http://localhost:8000/agent/router/classify" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I want to foreclose my loan immediately, you guys are charging too much penalty!",
    "mode": "hybrid",
    "openrouter_api_key": "sk-or-..."
  }'

# Compare Classifiers (Embeddings vs LLM)
curl -X POST "http://localhost:8000/agent/router/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Where can I download my statement?",
    "openrouter_api_key": "sk-or-..."
  }'

```

### 6. Follow-Up Question Generation

```bash
# Generate Follow-Ups (Batch)
curl -X POST "http://localhost:8000/agent/follow-up" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_12345",
    "question": "dummy_trigger", 
    "openrouter_api_key": "sk-or-..."
  }'

# Generate Follow-Ups (Stream)
curl -N -X POST "http://localhost:8000/agent/follow-up-stream" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_12345",
    "question": "dummy_trigger",
    "openrouter_api_key": "sk-or-..."
  }'

# Admin: Get Stored Follow-Up Contexts
curl -X GET "http://localhost:8000/agent/all-follow-ups"

```

### 7. Models Catalog

```bash
# List All Available Models
curl -X GET "http://localhost:8000/agent/models"

```

### 8. Admin & Knowledge Base (FAQ)

```bash
# Ingest JSON FAQs (Streaming)
curl -N -X POST "http://localhost:8000/agent/admin/faqs/batch-json" \
  -H "Content-Type: application/json" \
  -H "X-OpenRouter-Key: sk-or-..." \
  -d '{
    "items": [
      {
        "question": "How do I pay my EMI?",
        "answer": "You can pay via the mobile app or website using UPI."
      },
      {
        "question": "What is the customer care number?",
        "answer": "Call us at 1800-123-4567."
      }
    ]
  }'

# Upload PDF for FAQ Ingestion (Streaming)
curl -N -X POST "http://localhost:8000/agent/admin/faqs/upload-pdf" \
  -H "X-OpenRouter-Key: sk-or-..." \
  -F "file=@/path/to/your_document.pdf"

# List Existing FAQs
curl -X GET "http://localhost:8000/agent/admin/faqs?limit=100&skip=0"

# Edit FAQ
curl -X PUT "http://localhost:8000/agent/admin/faqs" \
  -H "Content-Type: application/json" \
  -H "X-OpenRouter-Key: sk-or-..." \
  -d '{
    "original_question": "How do I pay my EMI?",
    "new_question": "How can I clear my dues?",
    "new_answer": "Use the Pay Now button on the dashboard."
  }'

# Delete Specific FAQ
curl -X DELETE "http://localhost:8000/agent/admin/faqs?question=How%20do%20I%20pay%20my%20EMI?" \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"

# Delete ALL FAQs
curl -X DELETE "http://localhost:8000/agent/admin/faqs/all" \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"

# Semantic Search (Test RAG)
curl -X POST "http://localhost:8000/agent/admin/faqs/semantic-search" \
  -H "Content-Type: application/json" \
  -H "X-OpenRouter-Key: sk-or-..." \
  -d '{
    "query": "Can I pay via GPay?",
    "limit": 3
  }'

# Semantic Delete (Delete by similarity)
curl -X POST "http://localhost:8000/agent/admin/faqs/semantic-delete" \
  -H "Content-Type: application/json" \
  -H "X-OpenRouter-Key: sk-or-..." \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -d '{
    "query": "How to make payment?",
    "threshold": 0.92
  }'

```

### 9. Evaluation & Tracing (Read)

```bash
# Search Traces (Advanced Filter)
curl -X GET "http://localhost:8000/eval/search?limit=50&offset=0&order=desc&status=success&min_score=0.5"

# List Eval Sessions
curl -X GET "http://localhost:8000/eval/sessions?limit=25&offset=0"

# Get Single Trace Details
curl -X GET "http://localhost:8000/eval/trace/YOUR_TRACE_ID"

# Full Text Search on Traces
curl -X GET "http://localhost:8000/eval/fulltext?q=error&kind=trace&limit=20"

# Vector Search on Traces/Results
curl -X POST "http://localhost:8000/eval/vector-search" \
  -H "Content-Type: application/json" \
  -H "X-OpenRouter-Key: sk-or-..." \
  -d '{
    "kind": "trace",
    "text": "User asked about loan closure",
    "k": 10,
    "min_score": 0.7
  }'

# Metrics Summary
curl -X GET "http://localhost:8000/eval/metrics/summary?metric_name=Correctness"

# Failure Analysis
curl -X GET "http://localhost:8000/eval/metrics/failures?limit=50"

# Question Type Statistics
curl -X GET "http://localhost:8000/eval/question-types?limit=200"

```

### 10. Evaluation (Ingest & Live)

```bash
# Ingest Trace Data (System-to-System)
curl -X POST "http://localhost:8000/eval/ingest" \
  -H "Content-Type: application/json" \
  -H "X-Eval-Ingest-Key: YOUR_INGEST_KEY" \
  -d '{
    "trace": {
      "trace_id": "trace_001",
      "session_id": "sess_123",
      "inputs": {"question": "Hi"},
      "final_output": "Hello!",
      "status": "success"
    },
    "events": [
      {"seq": 1, "event_type": "token", "text": "Hello"}
    ],
    "evals": [
      {"metric_name": "Helpfulness", "score": 1.0, "passed": true}
    ]
  }'

# Connect to Live Trace Feed (Browser/SSE Client)
curl -N -X GET "http://localhost:8000/eval/live?cursor=$"

```

### 11. GraphQL

```bash
# Query Models via GraphQL
curl -X POST "http://localhost:8000/graphql" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { models(provider: \"openrouter\") { name models { id name contextLength pricing { prompt completion } } } }"
  }'

```