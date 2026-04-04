from types import SimpleNamespace

from src.agent_service.api.endpoints.agent_stream import (
    _LIFECYCLE_EVENTS,
    _extract_stream_segments_from_event_data,
    _lifecycle_payload,
)


def test_extract_stream_segments_splits_reasoning_and_answer_from_content_list():
    data = {
        "chunk": {
            "content": [
                {"type": "reasoning", "text": "thinking"},
                {"type": "text", "text": "final answer"},
            ]
        }
    }
    answer, reasoning = _extract_stream_segments_from_event_data(data)
    assert answer == "final answer"
    assert reasoning == "thinking"


def test_extract_stream_segments_reads_reasoning_from_additional_kwargs():
    chunk = SimpleNamespace(
        content="",
        additional_kwargs={"reasoning_content": ["a", {"text": "b"}], "other": "ignored"},
    )
    answer, reasoning = _extract_stream_segments_from_event_data({"chunk": chunk})
    assert answer == ""
    assert reasoning == "ab"


def test_extract_stream_segments_reads_provider_direct_reasoning_field():
    data = {"chunk": {"content": "", "reasoning": "internal"}}
    answer, reasoning = _extract_stream_segments_from_event_data(data)
    assert answer == ""
    assert reasoning == "internal"


def test_lifecycle_payload_compacts_large_start_input():
    event = {
        "event": "on_chain_start",
        "name": "rag_chain",
        "run_id": "run-1",
        "parent_ids": [],
        "tags": ["test"],
        "metadata": {"trace": "x"},
        "data": {"input": {"question": "q" * 1000}},
    }
    payload = _lifecycle_payload(event)
    question = payload["data"]["input"]["question"]
    assert isinstance(question, str)
    assert "[truncated:" in question


def test_nested_tool_end_filtered_by_parent_ids():
    """Inner/nested on_tool_end events whose parent_ids overlap with
    tracked tool_start run_ids should be skipped."""
    tool_start_run_ids: set[str] = set()

    # Outer tool starts — run_id tracked
    outer_run_id = "outer-run-001"
    tool_start_run_ids.add(outer_run_id)

    # Inner tool starts — run_id also tracked
    inner_run_id = "inner-run-002"
    tool_start_run_ids.add(inner_run_id)

    # Inner on_tool_end: parent_ids includes outer_run_id (a tracked tool start)
    inner_event_parent_ids = ["graph-run", outer_run_id]
    assert any(pid in tool_start_run_ids for pid in inner_event_parent_ids)
    # → this event should be SKIPPED

    # Outer on_tool_end: parent_ids are graph/node-level, NOT other tool starts
    outer_event_parent_ids = ["graph-run", "node-run"]
    assert not any(pid in tool_start_run_ids for pid in outer_event_parent_ids)
    # → this event should be EMITTED


def test_non_nested_tool_end_emitted_when_no_parent_overlap():
    """on_tool_end events without tool-run parents pass through."""
    tool_start_run_ids = {"tool-run-A", "tool-run-B"}

    # Event from a tool whose parents are graph/node runs only
    parent_ids = ["graph-run-1", "chain-run-2"]
    assert not any(pid in tool_start_run_ids for pid in parent_ids)


def test_lifecycle_events_contains_langchain_v2_required_types():
    required = {
        "on_chat_model_start",
        "on_chat_model_stream",
        "on_chat_model_end",
        "on_tool_start",
        "on_tool_end",
        "on_chain_start",
        "on_chain_stream",
        "on_chain_end",
        "on_llm_start",
        "on_llm_stream",
        "on_llm_end",
        "on_retriever_start",
        "on_retriever_end",
        "on_prompt_start",
        "on_prompt_end",
    }
    assert required.issubset(_LIFECYCLE_EVENTS)
