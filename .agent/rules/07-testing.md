# Testing Standards

> Applies to `backend/tests/**/*.py` and `Agent UI and Admin Console/src/**/*.test.*`.

## Backend Testing (Pytest)

### Execution
```bash
# From backend/
make test          # → uv run pytest tests/ -v
```

### Test Naming
```
test_<module>_<scenario>_<expected_outcome>
```
Examples:
- `test_session_risk_device_mismatch_step_up`
- `test_agent_stream_guardrail_blocks_dangerous_content`
- `test_router_answerability_below_threshold_falls_back`

### Async Tests
```python
@pytest.mark.asyncio
async def test_stream_emits_done_event():
    ...
```

Every async test needs `@pytest.mark.asyncio`.

### Mocking & Isolation (Non-Negotiable)

| Dependency | Mock Strategy |
|------------|---------------|
| Redis      | `fakeredis.aioredis.FakeRedis(decode_responses=True)` |
| PostgreSQL | `unittest.mock` stubs or `asyncpg` mock |
| HTTP/APIs  | `httpx.MockTransport` or `unittest.mock.patch` |
| LLM calls  | Mock the model client — never call real providers |
| MCP server | Mock `MCPManager` tool list responses |

- Tests must **never** hit live services or require network access.
- Tests must be deterministic and order-independent.

### Assertions
```python
# Floating point (risk scores, etc.)
assert result.score == pytest.approx(0.4)

# Complex objects — check multiple fields
assert result.decision == "step_up"
assert "device_mismatch" in result.reasons
```

### Existing Test Modules (16)
Tests cover: admin guardrails, agent query contract, stream events, stream guardrails, agent utils, inline guard, live dashboards, LLM client (OpenRouter), MCP utils, metrics endpoint, prompts YAML, router answerability, security layers, session store, shadow judge worker, shadow queue.

### Writing New Tests
- Add to `backend/tests/test_<module_name>.py`.
- Reuse existing helper stubs (e.g., `StaticGeoResolver` for security tests).
- If a new module has no test file, create one following the naming pattern above.

## Frontend Testing (Vitest)

### Execution
```bash
# From "Agent UI and Admin Console/"
npm run test       # → vitest run
```

### Stack
- Vitest + jsdom environment
- Testing Library (React + DOM)
- `@testing-library/jest-dom` for extended matchers

### Conventions
- Co-locate test files with components or use `src/test/` for setup.
- Test file naming: `*.test.tsx` or `*.test.ts`.
- Mock API calls — never hit the real backend.
- Test user interactions, not implementation details.
