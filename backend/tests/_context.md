# Context: `tests`

## Folder Snapshot
- Path: `tests`
- Role: Contract/unit coverage for API, streaming, router, MCP, and security behavior.
- Priority: `high`
- Generated (UTC): `2026-02-19 18:37:32Z`
- Regenerate: `make context-docs`

## File Inventory
| File | Type | Purpose | Key Symbols |
| --- | --- | --- | --- |
| `__init__.py` | `python` | Python module. | - |
| `test_agent_query_contract.py` | `python` | Python module. | def test_extract_final_response_from_state_messages_dict, def test_extract_final_response_from_message_object, def test_public_streaming_event_formatters |
| `test_agent_stream_events.py` | `python` | Python module. | def test_extract_stream_segments_splits_reasoning_and_answer_from_content_list, def test_extract_stream_segments_reads_reasoning_from_additional_kwargs, def test_extract_stream_segments_reads_provider_direct_reasoning_field, def test_lifecycle_payload_compacts_large_start_input, def test_lifecycle_events_contains_langchain_v2_required_types |
| `test_agent_utils.py` | `python` | Python module. | def test_valid_session_id, def test_normalize_result_dict, def test_normalize_result_list_of_tools, def test_keep_only_last_n_messages |
| `test_llm_client_openrouter.py` | `python` | Python module. | def test_get_llm_prefers_chatopenrouter_when_available, def test_get_llm_openrouter_falls_back_to_openai_adapter, def test_get_llm_retains_reasoning_effort_for_non_openai_providers |
| `test_mcp_utils.py` | `python` | Python module. | def converter, def test_flatten_simple_dict, def test_flatten_with_list, def test_guess_records_list, def test_guess_records_wrapped_dict |
| `test_router_answerability.py` | `python` | Python module. | class _Tool, def test_answerability_decision_prefers_higher_confidence_path, async def test_answerability_mcp_lexical_classification, async def test_answerability_kb_heuristic_without_vector, async def test_nbfc_classifier_includes_answerability_in_responses |
| `test_security_layers.py` | `python` | Python module. | class StaticGeoResolver, async def test_session_risk_device_mismatch_step_up, async def test_session_risk_concurrent_ips_step_up, async def test_session_risk_impossible_travel_denied, def test_tor_exit_nodes_parser_normalizes_and_deduplicates |
| `test_session_store.py` | `python` | Python module. | def mock_redis, def test_set_and_get, def test_get_missing_key, def test_update_existing_session, def test_update_creates_if_missing |

## Internal Dependencies
- `src.agent_service.api.endpoints.agent_query`
- `src.agent_service.api.endpoints.agent_stream`
- `src.agent_service.core.streaming_utils`
- `src.agent_service.features.answerability`
- `src.agent_service.features.nbfc_router`
- `src.agent_service.llm.client`
- `src.agent_service.security.session_security`
- `src.agent_service.security.tor_block`
- `src.agent_service.security.tor_exit_nodes`
- `src.agent_service.utils`
- `src.mcp_service.session_store`
- `src.mcp_service.utils`

## TODO / Risk Markers
- No TODO/FIXME/HACK markers detected.

## Session Handover Notes
1. Work completed in this folder:
2. Interfaces changed (APIs/schemas/config):
3. Tests run and evidence:
4. Open risks or blockers:
5. Next folder to process:
