"""Agent streaming endpoint with SSE."""
import json
import asyncio
import logging
from typing import Any
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent

from src.agent_service.core.schemas import AgentRequest
from src.agent_service.core.session_utils import session_utils
from src.agent_service.core.session_cost import get_session_cost_tracker
from src.agent_service.core.resource_resolver import resource_resolver
from src.agent_service.core.streaming_utils import (
    streaming_utils, sse_formatter, StreamingState
)
from src.agent_service.core.cost import calculate_run_cost_detailed
from src.agent_service.features.kb_first import kb_first_payload
from src.agent_service.features.nbfc_router import nbfc_router_service
from src.agent_service.features.shadow_eval import (
    ShadowEvalCollector, maybe_shadow_eval_commit
)

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
    
    # LangChain standard: output_token_details.reasoning
    if hasattr(usage_metadata, 'output_token_details'):
        details = getattr(usage_metadata, 'output_token_details', {})
        if isinstance(details, dict):
            reasoning_tokens = details.get('reasoning', 0)
    
    # Direct reasoning_tokens field (Groq/OpenRouter)
    if hasattr(usage_metadata, 'reasoning_tokens'):
        reasoning_tokens = getattr(usage_metadata, 'reasoning_tokens', 0)
    elif isinstance(usage_metadata, dict):
        reasoning_tokens = usage_metadata.get('reasoning_tokens', 0)
        
        # Check nested output_token_details
        if not reasoning_tokens:
            output_details = usage_metadata.get('output_token_details', {})
            reasoning_tokens = output_details.get('reasoning', 0)
    
    return reasoning_tokens


@router.post("/stream")
async def stream_agent(request: AgentRequest):
    """
    Streaming agent endpoint with Server-Sent Events.
    Streams tokens, tool calls, and cost information in real-time.
    """
    try:
        sid = session_utils.validate_session_id(request.session_id)
        
        # Resolve all resources
        resources = await resource_resolver.resolve_agent_resources(sid, request)
        
        # Start router classification in background
        router_task = asyncio.create_task(
            nbfc_router_service.classify(
                request.question,
                openrouter_api_key=resources.openrouter_api_key
            )
        )
        
        # Get app_id for shadow eval
        app_id = await session_utils.get_app_id_for_session(sid)
        
        # Initialize shadow eval collector
        collector = ShadowEvalCollector(
            session_id=sid,
            question=request.question,
            provider=resources.provider,
            model=resources.model_name,
            endpoint="/agent/stream",
            system_prompt=resources.system_prompt,
            tool_definitions=""
        )
        collector.case_id = app_id
        
        # KB-first guardrail (cached response)
        kb_payload = await kb_first_payload(request.question, resources.tools)
        if kb_payload:
            async def kb_event_generator():
                try:
                    tool_name = kb_payload.get("tool", "kb")
                    tool_input = kb_payload.get("input", {})
                    output = str(kb_payload.get("output", ""))
                    
                    # Track in collector
                    collector.on_tool_start(tool_name, tool_input)
                    collector.on_tool_end(tool_name, output, tool_call_id="kb_first")
                    
                    # Stream events
                    yield sse_formatter.token_event(output)
                    
                    collector.on_token(output)
                    collector.on_done(final_output=output, error=None)
                    
                    # No cost for cached KB response
                    yield sse_formatter.cost_event(
                        total_cost=0.0,
                        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        model=resources.model_name,
                        provider=resources.provider,
                        cached=True
                    )
                    
                    # Track zero-cost KB hit
                    tracker = get_session_cost_tracker()
                    await tracker.add_cost(
                        session_id=sid,
                        cost=0.0,
                        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                        model=resources.model_name,
                        provider="kb_cache",
                        metadata={"endpoint": "/agent/stream", "cached": True}
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
                    except:
                        pass
                    asyncio.create_task(maybe_shadow_eval_commit(
                        collector,
                        openrouter_api_key=resources.openrouter_api_key,
                        nvidia_api_key=resources.nvidia_api_key,
                        groq_api_key=resources.groq_api_key,
                        model_name=resources.model_name,
                        provider=resources.provider
                    ))
            
            return EventSourceResponse(
                kb_event_generator(),
                headers={"Cache-Control": "no-cache"}
            )
        
        # Validate tools
        if not resources.tools:
            raise HTTPException(status_code=500, detail="No tools loaded")
        
        # Get checkpointer
        from src.main_agent import app
        checkpointer = app.state.checkpointer
        
        # Create agent
        agent = create_agent(
            resources.model,
            resources.tools,
            system_prompt=resources.system_prompt,
            checkpointer=checkpointer
        )
        
        # Main streaming event generator
        async def event_generator():
            state = StreamingState()
            
            try:
                # Wait for router result and stream it
                try:
                    router_out = await router_task
                    if router_out:
                        collector.set_router_outcome(router_out)
                        yield sse_formatter.router_event(router_out)
                except Exception as e:
                    log.warning(f"Router failed: {e}")
                
                # Stream agent events
                async for event in agent.astream_events(
                    {"messages": [HumanMessage(content=request.question)]},
                    {"configurable": {"thread_id": sid}},
                    version="v2"
                ):
                    kind = event["event"]
                    data = event["data"]
                    
                    # Token streaming
                    if kind == "on_chat_model_stream":
                        chunk = data["chunk"]
                        
                        # Reasoning tokens streaming (Groq parsed format)
                        if hasattr(chunk, "additional_kwargs"):
                            r_content = chunk.additional_kwargs.get("reasoning_content")
                            if r_content:
                                collector.on_reasoning(str(r_content))
                                yield sse_formatter.reasoning_token_event(str(r_content))
                        
                        # Regular tokens
                        if chunk.content:
                            txt = str(chunk.content)
                            collector.on_token(txt)
                            yield sse_formatter.token_event(txt)
                    
                    # Tool execution start
                    elif kind == "on_tool_start":
                        t_name = event["name"]
                        t_input = data.get("input")
                        collector.on_tool_start(t_name, t_input)
                        yield sse_formatter.tool_start_event(t_name, t_input)
                    
                    # Tool execution end
                    elif kind == "on_tool_end":
                        t_name = event["name"]
                        raw_output = data.get("output")
                        output = streaming_utils.extract_tool_output(raw_output)
                        run_id = event.get("run_id")
                        collector.on_tool_end(t_name, output, tool_call_id=run_id)
                        yield sse_formatter.tool_end_event(t_name, output, run_id)
                    
                    # Cost tracking with reasoning tokens
                    elif kind == "on_chat_model_end":
                        out_msg = data.get("output")
                        if hasattr(out_msg, "usage_metadata") and out_msg.usage_metadata:
                            usage_meta = out_msg.usage_metadata
                            
                            # Convert to dict for manipulation
                            if hasattr(usage_meta, '__dict__'):
                                usage = dict(usage_meta.__dict__)
                            elif isinstance(usage_meta, dict):
                                usage = dict(usage_meta)
                            else:
                                usage = {}
                            
                            # Extract reasoning tokens from multiple sources
                            reasoning = extract_reasoning_tokens(usage_meta)
                            if reasoning > 0:
                                usage['reasoning_tokens'] = reasoning
                            
                            # Calculate detailed cost
                            cost, breakdown = await calculate_run_cost_detailed(
                                resources.model_name,
                                usage,
                                resources.provider
                            )
                            state.total_cost += cost
                            
                            # Accumulate usage
                            streaming_utils.accumulate_usage(state, usage)
                
                # Mark completion
                collector.on_done(final_output="", error=None)
                
                # Final cost event with reasoning tokens
                yield sse_formatter.cost_event(
                    total_cost=state.total_cost,
                    usage=state.cumulative_usage,
                    model=resources.model_name,
                    provider=resources.provider
                )
                
                # Track session cost in Redis
                tracker = get_session_cost_tracker()
                await tracker.add_cost(
                    session_id=sid,
                    cost=state.total_cost,
                    usage=state.cumulative_usage,
                    model=resources.model_name,
                    provider=resources.provider,
                    metadata={"endpoint": "/agent/stream"}
                )
                
                yield sse_formatter.done_event()
                
                # Commit shadow eval with all keys + model info
                asyncio.create_task(maybe_shadow_eval_commit(
                    collector,
                    openrouter_api_key=resources.openrouter_api_key,
                    nvidia_api_key=resources.nvidia_api_key,
                    groq_api_key=resources.groq_api_key,
                    model_name=resources.model_name,
                    provider=resources.provider
                ))
                
            except Exception as e:
                err = str(e)
                log.error(f"Stream error: {err}")
                collector.on_done(final_output="", error=err)
                yield sse_formatter.error_event(err)
                
                # Pass all keys even on error
                asyncio.create_task(maybe_shadow_eval_commit(
                    collector,
                    openrouter_api_key=resources.openrouter_api_key,
                    nvidia_api_key=resources.nvidia_api_key,
                    groq_api_key=resources.groq_api_key,
                    model_name=resources.model_name,
                    provider=resources.provider
                ))
        
        return EventSourceResponse(
            event_generator(),
            headers={"Cache-Control": "no-cache"}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Stream setup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
