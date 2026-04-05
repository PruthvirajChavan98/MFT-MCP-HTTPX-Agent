"""Agent streaming endpoint with SSE."""

import asyncio
import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from src.agent_service.core.config import (
    AGENT_INLINE_ROUTER_ENABLED,
    AGENT_INLINE_ROUTER_EXPOSE,
    AGENT_STREAM_EXPOSE_INTERNAL_EVENTS,
    AGENT_STREAM_EXPOSE_REASONING,
    SHADOW_JUDGE_ENABLED,
    SHADOW_TRACE_QUEUE_PUSH_TIMEOUT_SECONDS,
)
from src.agent_service.core.follow_ups import extract_follow_ups
from src.agent_service.core.pricing import calculate_run_cost_detailed
from src.agent_service.core.rate_limiter_manager import (
    enforce_rate_limit,
    get_rate_limiter_manager,
)
from src.agent_service.core.recursive_rag_graph import (
    build_recursive_rag_graph,
    initial_recursive_rag_state,
)
from src.agent_service.core.resource_resolver import resource_resolver
from src.agent_service.core.schemas import AgentRequest
from src.agent_service.core.session_cost import get_session_cost_tracker
from src.agent_service.core.session_utils import session_utils
from src.agent_service.core.streaming_utils import StreamingState, sse_formatter, streaming_utils
from src.agent_service.eval_store.shadow_queue import trace_queue
from src.agent_service.features.nbfc_router import nbfc_router_service
from src.agent_service.features.runtime_trace_store import persist_runtime_trace
from src.agent_service.features.shadow_eval import ShadowEvalCollector, maybe_shadow_eval_commit
from src.agent_service.security.inline_guard import evaluate_prompt_safety_decision

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent-stream"])

_LIFECYCLE_EVENTS = {
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


def _truncate_text(text: str, max_len: int = 400) -> str:
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}...[truncated:{len(text) - max_len}]"


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()
    return str(content) if content is not None else ""


def _safe_json(value: Any) -> Any:
    if value is None:
        return value
    if isinstance(value, str):
        return _truncate_text(value, 300)
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, dict):
        out = {}
        items = list(value.items())
        for idx, (k, v) in enumerate(items):
            if idx >= 10:
                out["_truncated_keys"] = len(items) - 10
                break
            out[str(k)] = _safe_json(v)
        return out
    if isinstance(value, (list, tuple)):
        out = [_safe_json(v) for v in value[:6]]
        if len(value) > 6:
            out.append({"_truncated_items": len(value) - 6})
        return out
    if hasattr(value, "content"):
        payload = {
            "content": _truncate_text(_message_content_to_text(getattr(value, "content", "")), 300)
        }
        addl = getattr(value, "additional_kwargs", None)
        if isinstance(addl, dict) and addl:
            payload["additional_kwargs"] = _safe_json(addl)
        return payload
    if hasattr(value, "__dict__"):
        return _safe_json(vars(value))
    return _truncate_text(str(value), 300)


def _summarize_messages(messages: Any) -> Dict[str, Any]:
    if not isinstance(messages, list):
        return {"messages_count": 0}
    out: Dict[str, Any] = {"messages_count": len(messages)}
    if messages:
        last = messages[-1]
        if hasattr(last, "content"):
            preview = _message_content_to_text(getattr(last, "content", ""))
        elif isinstance(last, dict):
            preview = _message_content_to_text(last.get("content"))
        else:
            preview = _message_content_to_text(last)
        if preview:
            out["last_message_preview"] = _truncate_text(preview, 180)
    return out


def _summarize_io_payload(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "content"):
        text = _message_content_to_text(getattr(value, "content", ""))
        addl = getattr(value, "additional_kwargs", None)
        out: Dict[str, Any] = {"content_preview": _truncate_text(text, 180)}
        reasoning = _extract_reasoning_from_additional_kwargs(addl)
        if reasoning:
            out["reasoning_preview"] = _truncate_text(reasoning, 180)
        return out
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        if "messages" in value:
            out["messages"] = _summarize_messages(value.get("messages"))
        for idx, key in enumerate(value.keys()):
            if key == "messages":
                continue
            if idx >= 6:
                out["_truncated_keys"] = max(0, len(value) - len(out))
                break
            out[str(key)] = _safe_json(value.get(key))
        return out
    return _safe_json(value)


def _extract_text_from_event_data(data: Any) -> str:
    if isinstance(data, dict):
        if "chunk" in data:
            chunk = data.get("chunk")
            if hasattr(chunk, "content"):
                return _message_content_to_text(getattr(chunk, "content", ""))
            return _message_content_to_text(chunk)

        if "output" in data:
            out = data.get("output")
            if hasattr(out, "content"):
                return _message_content_to_text(getattr(out, "content", ""))
            if isinstance(out, dict):
                if "content" in out:
                    return _message_content_to_text(out.get("content"))
                generations = out.get("generations")
                if isinstance(generations, list) and generations:
                    first = generations[0]
                    if isinstance(first, list) and first:
                        msg = first[0]
                        if isinstance(msg, dict):
                            nested = msg.get("message")
                            if isinstance(nested, dict):
                                return _message_content_to_text(nested.get("content"))
        if "input" in data:
            return _message_content_to_text(data.get("input"))

    return _message_content_to_text(data)


def _extract_final_response_from_graph_state(graph_output: Any) -> str:
    if graph_output is None:
        return ""
    if isinstance(graph_output, str):
        return graph_output
    if hasattr(graph_output, "content"):
        return _message_content_to_text(getattr(graph_output, "content", ""))
    if isinstance(graph_output, dict):
        messages = graph_output.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            if hasattr(last, "content"):
                return _message_content_to_text(getattr(last, "content", ""))
            if isinstance(last, dict):
                return _message_content_to_text(last.get("content"))
            return _message_content_to_text(last)
        if "response" in graph_output:
            return _message_content_to_text(graph_output.get("response"))
    return _message_content_to_text(graph_output)


def _reasoning_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_reasoning_text(v) for v in value)
    if isinstance(value, dict):
        for key in ("text", "content", "reasoning_content", "reasoning", "thinking"):
            if key in value:
                return _reasoning_text(value.get(key))
        return ""
    return str(value)


def _extract_reasoning_from_additional_kwargs(additional_kwargs: Any) -> str:
    if not isinstance(additional_kwargs, dict):
        return ""
    parts: list[str] = []
    for key in ("reasoning_content", "reasoning", "thinking", "reasoning_text"):
        if key in additional_kwargs:
            text = _reasoning_text(additional_kwargs.get(key))
            if text:
                parts.append(text)
    return "".join(parts)


def _extract_stream_segments_from_event_data(data: Any) -> tuple[str, str]:
    answer_parts: list[str] = []
    reasoning_parts: list[str] = []

    if not isinstance(data, dict):
        return _message_content_to_text(data), ""

    chunk = data.get("chunk")

    content = None
    if hasattr(chunk, "content"):
        content = getattr(chunk, "content", None)
    elif isinstance(chunk, dict):
        content = chunk.get("content")

    if isinstance(content, str):
        answer_parts.append(content)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                answer_parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text", item.get("content"))
            if text is None:
                continue
            content_type = str(item.get("type", "")).lower()
            if "reason" in content_type or "think" in content_type:
                reasoning_parts.append(str(text))
            else:
                answer_parts.append(str(text))
    elif content is not None:
        answer_parts.append(str(content))

    # Provider-specific reasoning fields on chunk payloads
    if hasattr(chunk, "reasoning"):
        direct_reasoning = _reasoning_text(getattr(chunk, "reasoning", None))
        if direct_reasoning:
            reasoning_parts.append(direct_reasoning)
    if isinstance(chunk, dict):
        for key in ("reasoning", "reasoning_content", "thinking"):
            if key in chunk:
                direct_reasoning = _reasoning_text(chunk.get(key))
                if direct_reasoning:
                    reasoning_parts.append(direct_reasoning)

    addl = getattr(chunk, "additional_kwargs", None)
    if addl is None and isinstance(chunk, dict):
        addl = chunk.get("additional_kwargs")
    reasoning_from_chunk = _extract_reasoning_from_additional_kwargs(addl)
    if reasoning_from_chunk:
        reasoning_parts.append(reasoning_from_chunk)

    for key in ("reasoning", "reasoning_content", "thinking"):
        if key in data:
            direct_reasoning = _reasoning_text(data.get(key))
            if direct_reasoning:
                reasoning_parts.append(direct_reasoning)

    reasoning_from_data = _extract_reasoning_from_additional_kwargs(data.get("additional_kwargs"))
    if reasoning_from_data:
        reasoning_parts.append(reasoning_from_data)

    return "".join(answer_parts), "".join(reasoning_parts)


def _extract_usage_candidate(obj: Any) -> Dict[str, int]:
    if obj is None:
        return {}

    if hasattr(obj, "usage_metadata"):
        usage = _extract_usage_candidate(getattr(obj, "usage_metadata", None))
        if usage:
            return usage

    if hasattr(obj, "response_metadata"):
        usage = _extract_usage_candidate(getattr(obj, "response_metadata", None))
        if usage:
            return usage

    if isinstance(obj, dict):
        for nested in ("usage_metadata", "response_metadata", "token_usage"):
            if nested in obj:
                usage = _extract_usage_candidate(obj.get(nested))
                if usage:
                    return usage

        prompt_tokens = int(obj.get("prompt_tokens", obj.get("input_tokens", 0)) or 0)
        completion_tokens = int(obj.get("completion_tokens", obj.get("output_tokens", 0)) or 0)
        total_tokens = int(obj.get("total_tokens", 0) or 0)
        if not total_tokens:
            total_tokens = prompt_tokens + completion_tokens

        reasoning_tokens = int(streaming_utils.extract_reasoning_tokens(obj) or 0)
        cached_tokens = int(obj.get("cached_tokens", obj.get("cache_read_input_tokens", 0)) or 0)

        if prompt_tokens or completion_tokens or total_tokens or reasoning_tokens or cached_tokens:
            return {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "reasoning_tokens": reasoning_tokens,
                "cached_tokens": cached_tokens,
            }

    return {}


def _extract_usage_from_event_data(data: Any) -> Dict[str, int]:
    if data is None:
        return {}

    if isinstance(data, dict):
        for key in ("chunk", "output", "input"):
            if key in data:
                usage = _extract_usage_candidate(data.get(key))
                if usage:
                    return usage

    return _extract_usage_candidate(data)


def _lifecycle_payload(event: Dict[str, Any]) -> Dict[str, Any]:
    event_name = str(event.get("event") or "")
    data = event.get("data", {})

    if isinstance(data, dict) and event_name.endswith("_stream"):
        text, reasoning = _extract_stream_segments_from_event_data(data)
        compact_stream: Dict[str, Any] = {}
        if text:
            compact_stream["text"] = _truncate_text(text, 180)
        if reasoning:
            compact_stream["reasoning"] = _truncate_text(reasoning, 180)
        if not compact_stream:
            compact_stream["chunk"] = _safe_json(data.get("chunk"))
        data = compact_stream
    elif isinstance(data, dict) and event_name.endswith("_start"):
        if "input" in data:
            data = {"input": _summarize_io_payload(data.get("input"))}
        else:
            data = _safe_json(data)
    elif isinstance(data, dict) and event_name.endswith("_end"):
        if "output" in data:
            data = {"output": _summarize_io_payload(data.get("output"))}
        else:
            data = _safe_json(data)
    else:
        data = _safe_json(data)

    metadata = event.get("metadata", {})
    if isinstance(metadata, dict):
        allowed_keys = (
            "thread_id",
            "langgraph_node",
            "langgraph_step",
            "ls_provider",
            "ls_model_name",
            "ls_model_type",
        )
        metadata = {k: metadata.get(k) for k in allowed_keys if k in metadata}
    else:
        metadata = _safe_json(metadata)

    return {
        "name": event.get("name"),
        "run_id": event.get("run_id"),
        "parent_ids": event.get("parent_ids", []),
        "tags": event.get("tags", []),
        "metadata": metadata,
        "data": data,
    }


@router.post("/stream")
async def stream_agent(request: AgentRequest, http_request: Request):
    """
    Streaming agent endpoint with Server-Sent Events.
    Public event contract:
    - `reasoning` (optional, controlled by config)
    - `tool_call`
    - `token`
    - `cost`
    - `done`

    Internal LangGraph lifecycle events are disabled by default and can be
    exposed only via explicit config for debugging.

    **Production-Grade Rate Limiting:**
    - Per-session rate limiting to prevent abuse
    - Graceful degradation on Redis failure
    - Returns 429 Too Many Requests if limit exceeded
    """
    try:
        manager = get_rate_limiter_manager()
        limiter = await manager.get_agent_stream_limiter()

        sid = session_utils.validate_session_id(request.session_id)
        identifier = f"session:{sid}"

        await enforce_rate_limit(http_request, limiter, identifier)

        resources = await resource_resolver.resolve_agent_resources(sid, request)

        router_task: asyncio.Task | None = None
        if AGENT_INLINE_ROUTER_ENABLED:
            router_task = asyncio.create_task(
                nbfc_router_service.classify(
                    request.question,
                    openrouter_api_key=resources.openrouter_api_key,
                    tools=resources.tools,
                )
            )

        app_id = await session_utils.get_app_id_for_session(sid)

        collector = ShadowEvalCollector(
            session_id=sid,
            question=request.question,
            provider=resources.provider,
            model=resources.model_name,
            endpoint="/agent/stream",
            system_prompt=resources.system_prompt,
            tool_definitions="",
        )
        collector.case_id = app_id

        inline_guard_decision = await evaluate_prompt_safety_decision(request.question)
        collector.set_inline_guard_decision(inline_guard_decision.as_dict())
        log.info(
            "Inline guard evaluated session_id=%s trace_id=%s decision=%s reason=%s risk_score=%.2f",
            sid,
            collector.trace_id,
            inline_guard_decision.decision,
            inline_guard_decision.reason_code,
            inline_guard_decision.risk_score,
        )

        if not inline_guard_decision.allow and inline_guard_decision.decision == "block":

            async def blocked_event_generator():
                blocked_err = "Prompt violates security policy"
                collector.on_done(final_output="", error=blocked_err)
                collector.set_eval_lifecycle("inline", "disabled", reason="disabled")
                collector.set_eval_lifecycle("shadow", "disabled", reason="disabled")

                persisted = await persist_runtime_trace(collector)
                if not persisted:
                    log.warning(
                        "Runtime trace persistence failed for blocked prompt "
                        "session_id=%s trace_id=%s inline_guard_decision=%s "
                        "inline_guard_reason=%s",
                        sid,
                        collector.trace_id,
                        inline_guard_decision.decision,
                        inline_guard_decision.reason_code,
                    )
                log.info(
                    "Stream terminal session_id=%s trace_id=%s status=blocked persisted=%s inline_guard_decision=%s inline_guard_reason=%s",
                    sid,
                    collector.trace_id,
                    persisted,
                    inline_guard_decision.decision,
                    inline_guard_decision.reason_code,
                )
                yield sse_formatter.trace_event(collector.trace_id)
                yield {
                    "event": "error",
                    "data": json.dumps({"message": blocked_err}),
                }
                yield sse_formatter.done_event()

            return EventSourceResponse(
                blocked_event_generator(), headers={"Cache-Control": "no-cache"}
            )

        if inline_guard_decision.decision == "degraded_allow":
            log.warning(
                "Inline guard degraded allow session_id=%s trace_id=%s reason=%s risk_score=%.2f",
                sid,
                collector.trace_id,
                inline_guard_decision.reason_code,
                inline_guard_decision.risk_score,
            )

        def schedule_shadow_trace_enqueue(latest_output: str) -> None:
            if not SHADOW_JUDGE_ENABLED:
                return

            async def _enqueue() -> None:
                try:
                    trace_data = collector.build_trace_dict()
                    response_text = str(trace_data.get("final_output") or latest_output or "")
                    async with asyncio.timeout(SHADOW_TRACE_QUEUE_PUSH_TIMEOUT_SECONDS):
                        await trace_queue.enqueue_trace(
                            session_id=sid,
                            user_prompt=request.question,
                            agent_response=response_text,
                            trace_id=str(trace_data.get("trace_id") or collector.trace_id),
                            status=str(trace_data.get("status") or collector.status),
                            metadata={
                                "endpoint": "/agent/stream",
                                "provider": resources.provider,
                                "model": resources.model_name,
                            },
                        )
                except Exception as exc:  # noqa: BLE001
                    collector.set_eval_lifecycle("shadow", "failed", reason="failed")
                    persisted = await persist_runtime_trace(collector)
                    log.warning(
                        "Failed to enqueue shadow trace for session %s trace_id=%s persisted=%s: %s",
                        sid,
                        collector.trace_id,
                        persisted,
                        exc,
                    )

            asyncio.create_task(_enqueue())

        if not resources.tools:
            raise HTTPException(status_code=500, detail="No tools loaded")

        from src.main_agent import app

        checkpointer = app.state.checkpointer
        graph = build_recursive_rag_graph(
            model=resources.model,
            tools=resources.tools,
            system_prompt=resources.system_prompt,
            checkpointer=checkpointer,
        )

        async def event_generator():
            state = StreamingState()
            router_handled = False
            final_output = ""
            metered_run_ids: set[str] = set()
            tool_start_run_ids: set[str] = set()
            saw_chat_model_events = False

            async def maybe_handle_router_outcome():
                nonlocal router_handled
                if router_handled or router_task is None or not router_task.done():
                    return None

                try:
                    router_out = router_task.result()
                    if router_out:
                        collector.set_router_outcome(router_out)
                        router_handled = True
                        if AGENT_INLINE_ROUTER_EXPOSE:
                            return sse_formatter.router_event(router_out)
                except Exception as e:
                    log.warning("Router classification failed: %s", e)
                router_handled = True
                return None

            try:
                stream_input = initial_recursive_rag_state(request.question)

                try:
                    event_stream = graph.astream_events(
                        stream_input,
                        {"configurable": {"thread_id": sid}},
                        version="v2",
                    )
                except TypeError:
                    log.warning(
                        "graph.astream_events does not accept explicit version; falling back"
                    )
                    event_stream = graph.astream_events(
                        stream_input,
                        {"configurable": {"thread_id": sid}},
                    )

                async for event in event_stream:
                    # Kill switch: detect client disconnect and stop burning tokens.
                    if await http_request.is_disconnected():
                        log.info(
                            "Client disconnected session_id=%s trace_id=%s — cancelling stream",
                            sid,
                            collector.trace_id,
                        )
                        break

                    router_evt = await maybe_handle_router_outcome()
                    if router_evt:
                        yield router_evt

                    if not isinstance(event, dict):
                        continue

                    event_name = str(event.get("event") or "")
                    data = event.get("data", {})

                    if event_name.startswith("on_chat_model"):
                        saw_chat_model_events = True

                    if AGENT_STREAM_EXPOSE_INTERNAL_EVENTS and event_name in _LIFECYCLE_EVENTS:
                        yield {"event": event_name, "data": _lifecycle_payload(event)}

                    if event_name == "on_tool_start":
                        tool_name = str(event.get("name") or "tool")
                        run_id = str(event.get("run_id") or "")
                        if run_id:
                            tool_start_run_ids.add(run_id)
                        tool_input = data.get("input", data) if isinstance(data, dict) else data
                        tool_input = _safe_json(tool_input)
                        collector.on_tool_start(tool_name, tool_input)
                        if AGENT_STREAM_EXPOSE_INTERNAL_EVENTS:
                            yield sse_formatter.tool_start_event(tool_name, tool_input)
                        continue

                    if event_name == "on_tool_end":
                        # Skip inner/nested tool runs (MCP adapter creates nested
                        # Runnables — outer wrapper + inner MCP call).  If any of
                        # this event's parent run_ids is itself a tool run we
                        # already track, this is the inner duplicate.
                        parent_ids = event.get("parent_ids") or []
                        if any(pid in tool_start_run_ids for pid in parent_ids):
                            continue

                        tool_name = str(event.get("name") or "tool")
                        tool_raw_output = (
                            data.get("output", data) if isinstance(data, dict) else data
                        )
                        output = _truncate_text(
                            streaming_utils.extract_tool_output(tool_raw_output), 6000
                        )
                        tool_call_id = str(event.get("run_id") or "")

                        collector.on_tool_end(tool_name, output, tool_call_id=tool_call_id)
                        if AGENT_STREAM_EXPOSE_INTERNAL_EVENTS:
                            yield sse_formatter.tool_end_event(tool_name, output, tool_call_id)
                        yield sse_formatter.tool_call_event(tool_name, output, tool_call_id)
                        continue

                    if event_name in ("on_chat_model_stream", "on_llm_stream"):
                        if event_name == "on_llm_stream" and saw_chat_model_events:
                            continue
                        text, reasoning = _extract_stream_segments_from_event_data(data)
                        if reasoning:
                            collector.on_reasoning(reasoning)
                            if AGENT_STREAM_EXPOSE_REASONING:
                                yield sse_formatter.reasoning_token_event(reasoning)
                        if text:
                            final_output += text
                            collector.on_token(text)
                            yield sse_formatter.token_event(text)
                        continue

                    if event_name in ("on_chat_model_end", "on_llm_end"):
                        if event_name == "on_llm_end" and saw_chat_model_events:
                            continue

                        run_id = str(event.get("run_id") or f"{event_name}:{id(event)}")
                        if run_id not in metered_run_ids:
                            usage = _extract_usage_from_event_data(data)
                            if usage:
                                cost, _ = await calculate_run_cost_detailed(
                                    resources.model_name,
                                    usage,
                                    resources.provider,
                                )
                                state.total_cost += cost
                                streaming_utils.accumulate_usage(state, usage)
                            metered_run_ids.add(run_id)

                        if not final_output:
                            text, _ = _extract_stream_segments_from_event_data(data)
                            if not text:
                                text = _extract_text_from_event_data(data)
                            if text:
                                final_output += text
                                collector.on_token(text)
                                yield sse_formatter.token_event(text)

                router_evt = await maybe_handle_router_outcome()
                if router_evt:
                    yield router_evt

                if router_task is not None and not router_handled:
                    try:
                        router_out = await asyncio.wait_for(router_task, timeout=0.25)
                        if router_out:
                            collector.set_router_outcome(router_out)
                            if AGENT_INLINE_ROUTER_EXPOSE:
                                yield sse_formatter.router_event(router_out)
                    except asyncio.TimeoutError:
                        log.debug("Router classification still running after stream completion")
                    except Exception as e:
                        log.warning("Router classification failed late: %s", e)
                    finally:
                        router_handled = True

                if not final_output:
                    try:
                        cfg = {"configurable": {"thread_id": sid}}
                        current_state = await graph.aget_state(cfg)
                        fallback_text = _extract_final_response_from_graph_state(
                            current_state.values if current_state is not None else None
                        )
                    except Exception as state_err:
                        log.warning("Failed to derive final fallback stream output: %s", state_err)
                        fallback_text = ""

                    if fallback_text:
                        final_output = fallback_text
                        collector.on_token(fallback_text)
                        yield sse_formatter.token_event(fallback_text)

                # Extract inline follow-up suggestions from the LLM output.
                final_output, follow_ups = extract_follow_ups(final_output)

                collector.on_done(final_output=final_output, error=None)
                if SHADOW_JUDGE_ENABLED:
                    collector.mark_shadow_judge_queued()
                else:
                    collector.set_eval_lifecycle("shadow", "disabled", reason="disabled")

                yield sse_formatter.cost_event(
                    total_cost=state.total_cost,
                    usage=state.cumulative_usage,
                    model=resources.model_name,
                    provider=resources.provider,
                )

                tracker = get_session_cost_tracker()
                await tracker.add_cost(
                    session_id=sid,
                    cost=state.total_cost,
                    usage=state.cumulative_usage,
                    model=resources.model_name,
                    provider=resources.provider,
                    metadata={"endpoint": "/agent/stream", "stream_version": "events_v2"},
                )

                try:
                    cfg = {"configurable": {"thread_id": sid}}
                    current_state = await graph.aget_state(cfg)
                    msgs = current_state.values.get("messages", [])
                    if msgs and getattr(msgs[-1], "type", "") == "ai":
                        # Persist canonical per-turn metadata for admin transcript rendering.
                        add_kwargs = getattr(msgs[-1], "additional_kwargs", None)
                        if not isinstance(add_kwargs, dict):
                            add_kwargs = {}
                            msgs[-1].additional_kwargs = add_kwargs

                        msgs[-1].content = final_output
                        add_kwargs["trace_id"] = collector.trace_id
                        add_kwargs["provider"] = resources.provider
                        add_kwargs["model"] = resources.model_name
                        add_kwargs["total_tokens"] = int(
                            (state.cumulative_usage or {}).get("total_tokens", 0) or 0
                        )
                        add_kwargs["cost"] = {
                            "total_cost": float(state.total_cost or 0.0),
                            "usage": state.cumulative_usage or {},
                            "model": resources.model_name,
                            "provider": resources.provider,
                            "currency": "USD",
                        }

                        if follow_ups:
                            add_kwargs["follow_ups"] = follow_ups
                        else:
                            add_kwargs.pop("follow_ups", None)

                        await graph.aupdate_state(cfg, {"messages": [msgs[-1]]})
                except Exception as store_err:
                    log.warning(
                        "Failed to save assistant metadata to checkpointer: %s",
                        store_err,
                    )

                persisted = await persist_runtime_trace(collector)
                if not persisted:
                    log.warning(
                        "Runtime trace persistence failed for stream trace_id=%s",
                        collector.trace_id,
                    )
                log.info(
                    "Stream terminal session_id=%s trace_id=%s status=success persisted=%s tokens=%s",
                    sid,
                    collector.trace_id,
                    persisted,
                    len(final_output),
                )
                if follow_ups:
                    yield sse_formatter.follow_ups_event(follow_ups)
                yield sse_formatter.trace_event(collector.trace_id)
                yield sse_formatter.done_event()

            except Exception as e:
                err = str(e)
                log.error("Stream error: %s", err)
                collector.on_done(final_output=final_output, error=err)
                if SHADOW_JUDGE_ENABLED:
                    collector.mark_shadow_judge_queued()
                else:
                    collector.set_eval_lifecycle("shadow", "disabled", reason="disabled")
                persisted = await persist_runtime_trace(collector)
                if not persisted:
                    log.warning(
                        "Runtime trace persistence failed for stream error trace_id=%s",
                        collector.trace_id,
                    )
                log.info(
                    "Stream terminal session_id=%s trace_id=%s status=error persisted=%s error=%s",
                    sid,
                    collector.trace_id,
                    persisted,
                    err,
                )
                yield sse_formatter.trace_event(collector.trace_id)
                yield sse_formatter.error_event(err)
                yield sse_formatter.done_event()
            finally:
                asyncio.create_task(
                    maybe_shadow_eval_commit(
                        collector,
                        openrouter_api_key=resources.openrouter_api_key,
                        nvidia_api_key=resources.nvidia_api_key,
                        groq_api_key=resources.groq_api_key,
                        model_name=resources.model_name,
                        provider=resources.provider,
                    )
                )
                schedule_shadow_trace_enqueue(final_output)

        return EventSourceResponse(event_generator(), headers={"Cache-Control": "no-cache"})

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error("Stream setup error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
