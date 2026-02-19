# Context: `scripts`

## Folder Snapshot
- Path: `scripts`
- Role: Operational scripts for ingestion, local setup, and endpoint validation.
- Priority: `medium`
- Generated (UTC): `2026-02-19 18:37:32Z`
- Regenerate: `make context-docs`

## File Inventory
| File | Type | Purpose | Key Symbols |
| --- | --- | --- | --- |
| `generate_context_docs.py` | `python` | Generate folder-level context docs and root handover context. | class FileSummary, class DirSnapshot, class FolderContext, def _is_dir_allowed, def _is_file_allowed |
| `ingest_faq.py` | `python` | Python module. | class FAQMetadata, async def extract_metadata, async def ingest_data_async |
| `ingest_grounding.py` | `python` | Python module. | def get_embeddings_model, def ingest_grounding_data |
| `localsetup.sh` | `shell` | Shell automation script. | - |
| `run_production_endpoint_tests.py` | `python` | Run production endpoint checks and emit a markdown report. | class TestCase, class TestResult, def _mask_secret, def _preview_text, def _run_one |
| `update_free_geoip.sh` | `shell` | Free-only updater for GeoIP/IP2Proxy datasets. | - |

## Internal Dependencies
- `src.agent_service.llm.client`
- `src.common.neo4j_mgr`

## TODO / Risk Markers
- generate_context_docs.py: L97: TODO |FIXME|HACK|XXX)\b[:\s-]*(.*)", re.IGNORECASE)
- generate_context_docs.py: L474: TODO / Risk Markers")
- generate_context_docs.py: L479: TODO /FIXME/HACK markers detected.")

## Session Handover Notes
1. Work completed in this folder:
2. Interfaces changed (APIs/schemas/config):
3. Tests run and evidence:
4. Open risks or blockers:
5. Next folder to process:
