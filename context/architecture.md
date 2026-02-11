# Architecture Detail

## Service Topology

6 Docker containers, single host, Cloudflare tunnel for public access.

### Container Dependencies
```
cloudflared → agent, mcp
agent       → mcp, redis, neo4j
mcp         → redis
router_worker → redis, neo4j
neo4j       → (none)
redis       → (none)
```

### Port Mapping
- **8005 (host localhost)** → agent:8000 — only local access
- **7474, 7687 (host)** → neo4j — exposed for dev/admin
- **Redis, MCP** — no host ports, but tunneled via Cloudflare (security risk)

### Network Flow
1. Public requests → Cloudflare tunnel → `agent:8000`
2. Agent → MCP (`http://mcp:8050/sse`) for tool calls
3. Agent → Neo4j (`bolt://neo4j:7687`) for FAQ/eval
4. Agent → Redis (`redis://redis:6379/0`) for sessions/config/cache
5. Agent → External LLM APIs (Groq, OpenRouter, NVIDIA)
6. MCP → Redis for sessions
7. MCP → CRM backend (`CRM_BASE_URL` from .env) via httpx
8. router_worker → Redis Streams (consume) → Neo4j (write)

### Startup Sequence (agent)
1. `AsyncRedisSaver` for LangGraph checkpointing
2. `model_service.start_background_loop()` — 30-min cache refresh
3. `mcp_manager.initialize()` — SSE connection to MCP server