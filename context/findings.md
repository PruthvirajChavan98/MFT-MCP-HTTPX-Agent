```markdown
# Complete Finding Registry

## Prioritized Action Items

### Immediate (Security)
1. **F17**: Remove `redis.pruthvirajchavan.codes` from cloudflared config. Add Redis AUTH.
2. **F18**: Remove `mcp.pruthvirajchavan.codes` from cloudflared config (or add MCP auth).
3. **F13**: Validate `X-Admin-Key` against a secret in FAQ admin endpoints.

### Next Sprint (Correctness)
4. **F12**: Mount `eval_live.router` in `main_agent.py`: `from src.agent_service.api.eval_live import router as eval_live_router`
5. **F7/F19**: Decommission v1 router. Remove `router_worker` from docker-compose. Delete `router/` directory.
6. **F21**: Fix import in `test_agent_utils.py`: `from src.agent_service.core.utils import ...`

### Tech Debt (Quality)
7. **F9**: Extract `EMBED_MODEL = "openai/text-embedding-3-small"` constant; use everywhere.
8. **F8**: Have `features/nbfc_router.py` import config from `core/config.py`.
9. **F6**: Single `valid_session_id()` in `core/utils.py`; import everywhere.
10. **F10**: Make `graph_rag.py` tool async or use `run_in_threadpool`.
11. **F4**: Use shared `httpx.AsyncClient` in MCP service.
12. **F14**: Set specific CORS origins.
13. **F22**: Add tests for agent flow, router, eval pipeline.
14. **F25**: Move Neo4j password to `.env`.
```