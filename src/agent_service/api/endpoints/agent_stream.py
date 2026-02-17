"""Agent streaming endpoint with SSE."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage, ToolMessage
from sse_starlette.sse import EventSourceResponse

from src.agent_service.core.cost import calculate_run_cost_detailed
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
from src.agent_service.features.kb_first import kb_first_payload
from src.agent_service.features.nbfc_router import nbfc_router_service
from src.agent_service.features.shadow_eval import ShadowEvalCollector, maybe_shadow_eval_commit

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent-stream"])


def extract_reasoning_tokens(usage_metadata: Any) -> int:
    """
    Extract reasoning tokens from various usage metadata formats.

    Supports:
    - LangChain UsageMetadata with output_token_details.reasoning
    - Groq API format
    - OpenRouter format
    """
    reasoning_tokens = 0

    if hasattr(usage_metadata, "output_token_details"):
        details = getattr(usage_metadata, "output_token_details", {})
        if isinstance(details, dict):
            reasoning_tokens = details.get("reasoning", 0)

    if hasattr(usage_metadata, "reasoning_tokens"):
        reasoning_tokens = getattr(usage_metadata, "reasoning_tokens", 0)
    elif isinstance(usage_metadata, dict):
        reasoning_tokens = usage_metadata.get("reasoning_tokens", 0)

        if not reasoning_tokens:
            output_details = usage_metadata.get("output_token_details", {})
            reasoning_tokens = output_details.get("reasoning", 0)

    return reasoning_tokens


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


@router.post("/stream")
async def stream_agent(request: AgentRequest, http_request: Request):
    """
    Streaming agent endpoint with Server-Sent Events.
    Streams tokens, tool calls, and cost information in real-time.

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

        router_task = asyncio.create_task(
            nbfc_router_service.classify(
                request.question, openrouter_api_key=resources.openrouter_api_key
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

        kb_payload = await kb_first_payload(request.question, resources.tools)
        if kb_payload:

            async def kb_event_generator():
                try:
                    tool_name = kb_payload.get("tool", "kb")
                    tool_input = kb_payload.get("input", {})
                    output = str(kb_payload.get("output", ""))

                    collector.on_tool_start(tool_name, tool_input)
                    collector.on_tool_end(tool_name, output, tool_call_id="kb_first")

                    yield sse_formatter.token_event(output)

                    collector.on_token(output)
                    collector.on_done(final_output=output, error=None)

                    yield sse_formatter.cost_event(
                        total_cost=0.0,
                        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        model=resources.model_name,
                        provider=resources.provider,
                        cached=True,
                    )

                    tracker = get_session_cost_tracker()
                    await tracker.add_cost(
                        session_id=sid,
                        cost=0.0,
                        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        model=resources.model_name,
                        provider="kb_cache",
                        metadata={"endpoint": "/agent/stream", "cached": True},
                    )

                    yield sse_formatter.done_event()

                except Exception as e:
                    collector.on_done(final_output="", error=str(e))
                    yield sse_formatter.error_event(str(e))
                finally:
                    try:
                        r_out = await router_task
                        if r_out:
                            collector.set_router_outcome(r_out)
                    except Exception:
                        pass
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

            return EventSourceResponse(kb_event_generator(), headers={"Cache-Control": "no-cache"})

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
            router_sent = False
            pending_tool_calls: dict[str, tuple[str, Any]] = {}

            seen_messages = 0
            final_messages: list[Any] = []
            final_output = ""

            try:
                async for snapshot in graph.astream(
                    initial_recursive_rag_state(request.question),
                    {"configurable": {"thread_id": sid}},
                    stream_mode="values",
                ):
                    messages = snapshot.get("messages", [])
                    if not isinstance(messages, list):
                        continue

                    if not router_sent and router_task.done():
                        try:
                            router_out = router_task.result()
                            if router_out:
                                collector.set_router_outcome(router_out)
                                yield sse_formatter.router_event(router_out)
                            router_sent = True
                        except Exception as e:
                            log.warning(f"Router classification failed: {e}")
                            router_sent = True

                    new_messages = messages[seen_messages:]
                    seen_messages = len(messages)
                    final_messages = messages

                    for msg in new_messages:
                        if isinstance(msg, AIMessage):
                            tool_calls = getattr(msg, "tool_calls", []) or []

                            for tool_call in tool_calls:
                                t_name = tool_call.get("name", "tool")
                                t_input = tool_call.get("args", {})
                                t_id = tool_call.get("id") or t_name
                                pending_tool_calls[t_id] = (t_name, t_input)
                                collector.on_tool_start(t_name, t_input)
                                yield sse_formatter.tool_start_event(t_name, t_input)

                            text = _message_content_to_text(getattr(msg, "content", ""))
                            if text:
                                final_output += text
                                collector.on_token(text)
                                yield sse_formatter.token_event(text)

                            usage_meta = getattr(msg, "usage_metadata", None)
                            if usage_meta:
                                if hasattr(usage_meta, "__dict__"):
                                    usage = dict(usage_meta.__dict__)
                                elif isinstance(usage_meta, dict):
                                    usage = dict(usage_meta)
                                else:
                                    usage = {}

                                reasoning = extract_reasoning_tokens(usage_meta)
                                if reasoning > 0:
                                    usage["reasoning_tokens"] = reasoning

                                cost, _ = await calculate_run_cost_detailed(
                                    resources.model_name, usage, resources.provider
                                )
                                state.total_cost += cost
                                streaming_utils.accumulate_usage(state, usage)

                        elif isinstance(msg, ToolMessage):
                            t_id = getattr(msg, "tool_call_id", None) or ""
                            t_name, t_input = pending_tool_calls.get(
                                t_id, (getattr(msg, "name", None) or "tool", {})
                            )
                            output = streaming_utils.extract_tool_output(msg)
                            collector.on_tool_end(t_name, output, tool_call_id=t_id)
                            yield sse_formatter.tool_end_event(t_name, output, t_id)

                if not final_output:
                    for msg in reversed(final_messages):
                        if isinstance(msg, AIMessage):
                            text = _message_content_to_text(getattr(msg, "content", ""))
                            if text:
                                final_output = text
                                collector.on_token(text)
                                yield sse_formatter.token_event(text)
                            break

                if not router_sent:
                    try:
                        router_out = await router_task
                        if router_out:
                            collector.set_router_outcome(router_out)
                            yield sse_formatter.router_event(router_out)
                    except Exception as e:
                        log.warning(f"Router classification failed: {e}")

                collector.on_done(final_output=final_output, error=None)

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
                    metadata={"endpoint": "/agent/stream"},
                )

                yield sse_formatter.done_event()

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

            except Exception as e:
                err = str(e)
                log.error(f"Stream error: {err}")
                collector.on_done(final_output="", error=err)
                yield sse_formatter.error_event(err)

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

        return EventSourceResponse(event_generator(), headers={"Cache-Control": "no-cache"})

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Stream setup error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
