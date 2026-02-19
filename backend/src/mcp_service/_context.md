# Context: `src/mcp_service`

## Folder Snapshot
- Path: `src/mcp_service`
- Role: MCP service APIs, session store, tool descriptions, and server runtime.
- Priority: `high`
- Generated (UTC): `2026-02-19 18:37:32Z`
- Regenerate: `make context-docs`

## File Inventory
| File | Type | Purpose | Key Symbols |
| --- | --- | --- | --- |
| `auth_api.py` | `python` | Python module. | def _valid_session_id, class MockFinTechAuthAPIs |
| `config.py` | `python` | Python module. | - |
| `core_api.py` | `python` | Python module. | def _valid_session_id, class MockFinTechAPIs |
| `description_utils.py` | `python` | Python module. | def _load_tool_descriptions, def _d |
| `image_store.py` | `python` | Python module. | class RedisImageStore |
| `server.py` | `python` | Python module. | def _touch, def get_auth, def get_api, def generate_otp, def validate_otp |
| `session_store.py` | `python` | Python module. | def _redact_uri, class RedisSessionStore |
| `tool_descriptions.json` | `json` | JSON object with keys: tool_descriptions. | - |
| `utils.py` | `python` | Python module. | class ToonOptions, class JsonConverter |

## Internal Dependencies
- `.auth_api`
- `.config`
- `.core_api`
- `.description_utils`
- `.session_store`
- `.utils`

## TODO / Risk Markers
- No TODO/FIXME/HACK markers detected.

## Session Handover Notes
1. Work completed in this folder:
2. Interfaces changed (APIs/schemas/config):
3. Tests run and evidence:
4. Open risks or blockers:
5. Next folder to process:
