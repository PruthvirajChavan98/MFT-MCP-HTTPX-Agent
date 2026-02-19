# Context: `src/agent_service/eval_store`

## Folder Snapshot
- Path: `src/agent_service/eval_store`
- Role: Evaluation storage, embedding, and judge integration modules.
- Priority: `medium`
- Generated (UTC): `2026-02-19 18:37:32Z`
- Regenerate: `make context-docs`

## File Inventory
| File | Type | Purpose | Key Symbols |
| --- | --- | --- | --- |
| `embedder.py` | `python` | Python module. | def _sha256, def _truncate, def _build_trace_doc, def _build_eval_doc, class EvalEmbedder |
| `judge.py` | `python` | Python module. | class PointwiseScore, class PairwiseVerdict, class LLMJudge |
| `neo4j_store.py` | `python` | Python module. | def _json, class EvalNeo4jStore |

## Internal Dependencies
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
