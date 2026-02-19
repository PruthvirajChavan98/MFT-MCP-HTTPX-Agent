# Context: `src/agent_service/features`

## Folder Snapshot
- Path: `src/agent_service/features`
- Role: Feature flags/prototypes and answerability/follow-up behavior modules.
- Priority: `medium`
- Generated (UTC): `2026-02-19 18:37:32Z`
- Regenerate: `make context-docs`

## File Inventory
| File | Type | Purpose | Key Symbols |
| --- | --- | --- | --- |
| `__init__.py` | `python` | Python module. | - |
| `answerability.py` | `python` | Python module. | class ToolCandidate, def _norm_text, def _cosine, def _tokenize, def _answerability_decision |
| `follow_up.py` | `python` | Python module. | class FollowUpAngle, class FollowUpQuestionGenerator |
| `kb_first.py` | `python` | Python module. | def _as_text, async def kb_first_payload |
| `nbfc_router.py` | `python` | Python module. | def _norm, def _cosine, def _sha256_json, def _tone_override, class _ProtoCache |
| `prototypes_nbfc.py` | `python` | Python module. | - |
| `shadow_eval.py` | `python` | Python module. | def _utc_iso, def _clip, def _strip_html, def _normalize_text, def _load_rules |

## Internal Dependencies
- `.prototypes_nbfc`
- `src.agent_service.core.config`
- `src.agent_service.eval_store.embedder`
- `src.agent_service.eval_store.judge`
- `src.agent_service.eval_store.neo4j_store`
- `src.agent_service.features.answerability`
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
