from src.agent_service.core.streaming_utils import sse_formatter


def test_stream_terminal_success_event_order_is_trace_then_done() -> None:
    trace_evt = sse_formatter.trace_event("trace_ok")
    done_evt = sse_formatter.done_event()

    assert trace_evt["event"] == "trace"
    assert done_evt["event"] == "done"


def test_stream_terminal_error_contract_includes_trace_error_done() -> None:
    events = [
        sse_formatter.trace_event("trace_err"),
        sse_formatter.error_event("failed"),
        sse_formatter.done_event(),
    ]

    assert [evt["event"] for evt in events] == ["trace", "error", "done"]


def test_stream_blocked_prompt_contract_includes_trace_before_done() -> None:
    events = [
        sse_formatter.trace_event("trace_blocked"),
        {
            "event": "error",
            "data": '{"message":"Prompt violates security policy"}',
        },
        sse_formatter.done_event(),
    ]

    assert events[0]["event"] == "trace"
    assert events[-1]["event"] == "done"


def test_stream_no_token_fallback_contract_emits_token_before_terminal_events() -> None:
    events = [
        sse_formatter.token_event("fallback answer from checkpoint state"),
        sse_formatter.trace_event("trace_fallback"),
        sse_formatter.done_event(),
    ]

    assert [evt["event"] for evt in events] == ["token", "trace", "done"]
