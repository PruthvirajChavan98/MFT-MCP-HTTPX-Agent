# HFCL FastMCP Agent — Project Context

> **Last updated**: 2025-02-10 | **Auditor**: Principal Architect (7-zone discovery)
> **Codebase root**: `/home/pruthvi/projects/h-ai/HFCL-FastMCP-server-httpx-tools`

## One-Sentence Summary

A dual-service NBFC customer-support AI: a **FastMCP tool server** proxying a fintech CRM behind Redis-backed sessions, and a **FastAPI + LangGraph agent** that orchestrates multi-provider LLMs, a Neo4j knowledge graph, sentiment routing, follow-up generation, and a full shadow evaluation pipeline — all deployed via Docker Compose behind a Cloudflare tunnel.

---

## Architecture at a Glance

```
                    Cloudflare Tunnel
                          │
              ┌───────────┴───────────┐
              │                       │
        agent:8000              mcp:8050
        (FastAPI+LangGraph)     (FastMCP SSE)
              │                       │
    ┌─────────┼─────────┐            │ httpx
    │         │         │            ▼
  Neo4j    Redis    LLM APIs    CRM Backend
  :7687    :6379    (Groq,      /mockfin-service/*
                    OpenRouter,
                    NVIDIA)
```

**Services** (docker-compose): `redis`, `neo4j`, `mcp`, `agent`, `cloudflared`, `router_worker`

→ [context/architecture.md](context/architecture.md)

---

## Service Boundaries

| Service | Entry Point | Port | Role |
|---|---|---|---|
| **MCP Server** | `src/main_mcp.py` | 8050 (SSE) | 12 loan-servicing tools. Session-per-call via `session_id`. Redis session state. CRM proxy. |
| **Agent Service** | `src/main_agent.py` | 8000 (HTTP) | 28 REST/SSE/GraphQL endpoints. LangGraph ReAct agent. Multi-provider LLM routing. |
| **Router Worker** | `src/agent_service/router/worker.py` | None | Redis Streams consumer. Classifies traces via v1 embeddings router. Writes to Neo4j. |

→ [context/mcp-service.md](context/mcp-service.md)
→ [context/agent-service.md](context/agent-service.md)

---

## Critical Request Flow (`POST /agent/stream`)

```
Request(session_id, question)
  │
  ├─ resolve config (Redis) → get_llm() → rebuild_tools (auth-gated)
  ├─ asyncio.create_task(nbfc_router.classify)      ← background
  ├─ kb_first_payload(question)
  │    └─ regex match? → stream KB answer, skip LLM
  │
  ▼
  create_react_agent(model, tools, checkpointer)
  agent.astream_events() → SSE (reasoning/token/tool_start/tool_end)
  │
  finally:
    ├─ await router_task → log to collector
    └─ fire-and-forget: maybe_shadow_eval_commit()
```

→ [context/request-flow.md](context/request-flow.md)

---

## Data Stores

### Redis Key Map

| Pattern | Owner | Content |
|---|---|---|
| `{session_id}` | MCP session_store | Auth tokens, app_id, phone_number |
| `agent:config:{session_id}` | ConfigManager | System prompt, model_name, API keys |
| `agent:models:cache_all` | ModelService | Cached model catalog (30-min TTL) |
| `eval:live` | eval_ingest | Redis Stream — live dashboard SSE |
| `router:jobs` | shadow_eval → worker | Redis Stream — async classification |

### Neo4j Graph Schema

```
FAQ:  (Question)─[:HAS_ANSWER]→(Answer)
                ─[:ABOUT]→(Topic)
                ─[:RELATES_TO]→(Product)

Eval: (EvalTrace)─[:HAS_EVENT]→(EvalEvent)
                 ─[:HAS_EVAL]→(EvalResult)─[:EVIDENCE]→(EvalEvent)

Cache: (FollowUpContext)─[:HAS_SUGGESTION]→(SuggestedQuestion)

Orphaned: (GroundingQuestion) — created by script, not queried by app
```

**Vector Indexes** (all 1536-d cosine, `text-embedding-3-small`):
`question_embeddings`, `evaltrace_embeddings`, `evalresult_embeddings`, `followup_context_embeddings`, `grounding_embeddings`

→ [context/data-stores.md](context/data-stores.md)

---

## LLM Provider Routing

`get_llm()` in `llm/client.py` implements a priority chain:

```
1. NVIDIA  — if nvidia_api_key + model matches (nvidia/, moonshot, gpt-oss, deepseek-r1)
2. Groq    — if bare model name or groq/ prefix; round-robin key cycling
3. OpenRouter — fallback for everything else; via ChatDeepSeek
```

**BYOK**: Users can supply `openrouter_api_key` and `nvidia_api_key` per-request. Cascade: `request → saved_config → env`.

→ [context/llm-routing.md](context/llm-routing.md)

---

## Key Subsystems

| Subsystem | Module | Summary |
|---|---|---|
| **NBFC Router** | `features/nbfc_router.py` (v2) | Hybrid embeddings+LLM sentiment/reason classifier. Tone overrides, reason boosts, disk-cached prototypes. |
| **KB-First** | `features/kb_first.py` | Regex short-circuit for stolen vehicle / stop EMI. Skips LLM entirely. |
| **Follow-up Gen** | `features/follow_up.py` | Neo4j-cached → generate 5 Qs (streaming) → explain why → judge score ≥ 7.0 → cache. |
| **Shadow Eval** | `features/shadow_eval.py` | Probabilistic (rate + throttle). Non-LLM metrics + G-Eval LLM judge. Commits to Neo4j + embeddings. |
| **Eval Dashboard** | `api/eval_read.py` | Search, fulltext, vector search, sessions, metrics summary, failures, question types. |
| **KB Management** | `tools/knowledge.py` | Full CRUD + streaming ingest + LLM metadata extraction. |
| **Model Catalog** | `llm/catalog.py` + `api/graphql.py` | 3-provider fetch → Redis cache → Strawberry GraphQL with rich filters. |

→ [context/nbfc-router.md](context/nbfc-router.md)
→ [context/eval-pipeline.md](context/eval-pipeline.md)
→ [context/follow-up.md](context/follow-up.md)

---

## Known Issues — Priority Ordered

### 🔴 Critical

| # | Issue | Location |
|---|---|---|
| **F17** | **Redis exposed via Cloudflare tunnel with zero auth.** Anyone with `redis.pruthvirajchavan.codes` has full R/W to all sessions, tokens, API keys. | `cloudflared/config.yml` |

### ⚠️ High

| # | Issue | Location |
|---|---|---|
| **F2/F18** | MCP server has no auth; also tunneled publicly. Any caller can invoke any tool with any session_id. | `mcp_service/server.py`, `cloudflared/config.yml` |
| **F13** | Admin FAQ endpoints (`/agent/admin/faqs/*`) accept `X-Admin-Key` header but **never validate it**. Anyone can wipe the KB. | `main_agent.py` |
| **F12** | `/eval/live` SSE endpoint defined in `eval_live.py` but **never mounted** in the app. Dead code. | `main_agent.py` imports |
| **F7/F19** | **Two NBFC routers coexist**: v1 (`router/service.py`, deployed as `router_worker`) vs v2 (`features/nbfc_router.py`, used by agent). Both write to `EvalTrace.router_*` — potential data conflicts. | `router/`, `features/`, `docker-compose.yml` |
| **F22** | Test coverage ~5%. 14 unit tests. Zero tests for agent flow, router, eval, KB, streaming. | `tests/` |

### ⚡ Medium

| # | Issue | Location |
|---|---|---|
| **F9** | `"openai/text-embedding-3-small"` hardcoded in 8+ files instead of using `OPENROUTER_EMBED_MODEL_DEFAULT` constant. | Multiple |
| **F8** | `features/nbfc_router.py` re-parses all `NBFC_ROUTER_*` env vars instead of importing from `core/config.py`. | `features/nbfc_router.py` |
| **F10** | `graph_rag.py` tool function is sync — blocks the async event loop during Neo4j I/O. | `tools/graph_rag.py` |
| **F4** | MCP creates a new `httpx.Client()` per API call. No connection pooling. | `mcp_service/core_api.py`, `auth_api.py` |
| **F1** | MCP uses `transport="sse"` (legacy). FastMCP recommends `streamable-http`. | `mcp_service/server.py` |
| **F14** | CORS `allow_origins=["*"]` + `allow_credentials=True` — contradictory per spec. | `main_agent.py` |
| **F21** | `test_agent_utils.py` imports from wrong path (`src.agent_service.utils` instead of `src.agent_service.core.utils`). Fails on import. | `tests/test_agent_utils.py` |
| **F25** | Neo4j password `password` hardcoded in docker-compose instead of `.env`. | `docker-compose.yml` |

### ℹ️ Low / Info

| # | Issue |
|---|---|
| F3 | `image_store.py` implemented but unused |
| F5 | Inconsistent error formats (CSV vs TOON vs dict) |
| F6 | `_valid_session_id()` duplicated 4× |
| F11 | Shadow eval captures full trace then may discard (sampling at commit) |
| F15 | Per-call Redis connection in `_get_app_id_for_session` |
| F16 | Duplicate config resolution in `/agent/stream` |
| F20 | `requirements.txt` stale — `pyproject.toml` is authoritative |
| F23 | `ingest_grounding.py` creates orphaned `GroundingQuestion` data |
| F24 | `scripts/ingest_faq.py` duplicates `knowledge.py` logic |

→ [context/findings.md](context/findings.md)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Package mgr | `uv` (astral) with lockfile |
| Web frameworks | FastAPI (agent), FastMCP (MCP), Strawberry (GraphQL) |
| Agent framework | LangGraph `create_react_agent` + LangChain |
| LLM providers | Groq, OpenRouter, NVIDIA (via LangChain adapters) |
| Database | Neo4j 5.26 Community (graph + vector + fulltext) |
| Cache / Queue | Redis Stack (sessions, config, model cache, Streams) |
| Checkpointing | `langgraph-checkpoint-redis` (AsyncRedisSaver) |
| Tunnel | Cloudflare `cloudflared` |
| Container | Docker + docker-compose |
| Serialization | TOON format, CSV (VSC), JSON |
| PDF parsing | pdfplumber |
| Testing | pytest + fakeredis (**minimal**) |

---

## File Ownership Quick Reference

```
src/
├── main_agent.py          ← FastAPI app, route wiring, streaming orchestrator
├── main_mcp.py            ← MCP server entry (trivial)
├── common/
│   └── neo4j_mgr.py       ← Shared Neo4j singleton
├── mcp_service/           ← Self-contained MCP tool server
│   ├── server.py          ← Tool registration (12 active)
│   ├── auth_api.py        ← OTP flow against CRM
│   ├── core_api.py        ← Authenticated loan APIs
│   ├── session_store.py   ← Redis session CRUD
│   └── utils.py           ← JSON→CSV/TOON serializers
└── agent_service/
    ├── core/              ← Config, schemas, prompts, utils
    ├── data/              ← Session config manager (Redis)
    ├── llm/               ← get_llm() factory + model catalog
    ├── tools/             ← MCP bridge + graph_rag + KB CRUD
    ├── features/          ← nbfc_router, kb_first, follow_up, shadow_eval
    ├── eval_store/        ← Neo4j persistence + embedder + judge
    ├── router/            ← v1 router (⚠️ deprecated, still deployed)
    └── api/               ← GraphQL + eval endpoints
```