# Context: `src/agent_service/api/endpoints`

## Folder Snapshot
- Path: `src/agent_service/api/endpoints`
- Role: Public FastAPI endpoint handlers for agent-facing APIs.
- Priority: `high`
- Generated (UTC): `2026-02-19 18:37:32Z`
- Regenerate: `make context-docs`

## File Inventory
| File | Type | Purpose | Key Symbols |
| --- | --- | --- | --- |
| `__init__.py` | `python` | API Endpoints Package | - |
| `agent_query.py` | `python` | Agent query endpoint (non-streaming). | def _message_content_to_text, def _extract_final_response, async def query_agent |
| `agent_stream.py` | `python` | Agent streaming endpoint with SSE. | def _truncate_text, def _message_content_to_text, def _safe_json, def _summarize_messages, def _summarize_io_payload |
| `follow_up.py` | `python` | Follow-up question generation endpoints. | async def generate_follow_up, async def generate_follow_up_stream |
| `health.py` | `python` | Health checks and monitoring endpoints. | async def health_check, async def liveness_check, async def readiness_check, async def metrics |
| `models.py` | `python` | Model catalog and listing endpoints. | async def list_models |
| `rate_limit_metrics.py` | `python` | Rate Limiting Metrics and Monitoring Endpoints. | async def get_rate_limit_metrics, async def get_identifier_status, async def reset_identifier_limit, async def rate_limit_health_check, async def get_rate_limit_config |
| `router_endpoints.py` | `python` | NBFC router classification endpoints. | def _resolve_tools_for_request, async def router_classify, async def router_compare |
| `sessions.py` | `python` | Session management and cost tracking endpoints. | async def list_active_sessions, async def verify_session, async def get_session_config, async def config_session, async def logout_session |

## Internal Dependencies
- `src.agent_service.core.config`
- `src.agent_service.core.cost`
- `src.agent_service.core.prompts`
- `src.agent_service.core.rate_limiter_manager`
- `src.agent_service.core.recursive_rag_graph`
- `src.agent_service.core.resource_resolver`
- `src.agent_service.core.schemas`
- `src.agent_service.core.session_cost`
- `src.agent_service.core.session_utils`
- `src.agent_service.core.streaming_utils`
- `src.agent_service.data.config_manager`
- `src.agent_service.features.follow_up`
- `src.agent_service.features.kb_first`
- `src.agent_service.features.nbfc_router`
- `src.agent_service.features.shadow_eval`
- `src.agent_service.llm.catalog`
- `src.agent_service.security.metrics`
- `src.agent_service.tools.mcp_manager`

## TODO / Risk Markers
- rate_limit_metrics.py: L120: TODO Add admin authentication check here

## Session Handover Notes
1. Work completed in this folder:
2. Interfaces changed (APIs/schemas/config):
3. Tests run and evidence:
4. Open risks or blockers:
5. Next folder to process:
