# Context: `src/agent_service/router`

## Folder Snapshot
- Path: `src/agent_service/router`
- Role: NBFC router taxonomy, schemas, service, and worker runtime.
- Priority: `medium`
- Generated (UTC): `2026-02-19 18:37:32Z`
- Regenerate: `make context-docs`

## File Inventory
| File | Type | Purpose | Key Symbols |
| --- | --- | --- | --- |
| `nbfc_taxonomy.py` | `python` | Python module. | - |
| `prototypes_nbfc.py` | `python` | Python module. | - |
| `schemas.py` | `python` | Python module. | class LabelScore, class RouterResult |
| `service.py` | `python` | Python module. | def _cosine_top, class RouterService |
| `worker.py` | `python` | Python module. | async def ensure_group, async def run_worker |

## Internal Dependencies
- `.prototypes_nbfc`
- `.schemas`
- `.service`
- `src.agent_service.core.config`
- `src.agent_service.llm.client`
- `src.common.neo4j_mgr`

## TODO / Risk Markers
- No TODO/FIXME/HACK markers detected.

## Session Handover Notes
1. Work completed in this folder:
2. Interfaces changed (APIs/schemas/config):
3. Tests run and evidence:
4. Open risks or blockers:
5. Next folder to process:
