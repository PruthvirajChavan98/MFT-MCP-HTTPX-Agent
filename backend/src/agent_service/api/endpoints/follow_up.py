"""Follow-up question generation endpoints."""

import json
import logging

from fastapi import APIRouter, HTTPException
from langchain.agents import create_agent
from sse_starlette.sse import EventSourceResponse

from src.agent_service.core.resource_resolver import resource_resolver
from src.agent_service.core.schemas import AgentRequest
from src.agent_service.core.session_utils import session_utils
from src.agent_service.features.follow_up import follow_up_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["follow-up"])


async def _persist_follow_ups_to_last_ai_message(
    *,
    agent: object,
    session_id: str,
    questions: list[str],
) -> None:
    if not questions:
        return
    try:
        config = {"configurable": {"thread_id": session_id}}
        state_obj = await agent.aget_state(config)
        if not state_obj:
            return

        messages = state_obj.values.get("messages", [])
        if not messages:
            return

        for msg in reversed(messages):
            if getattr(msg, "type", "") != "ai":
                continue
            add_kwargs = getattr(msg, "additional_kwargs", None)
            if not isinstance(add_kwargs, dict):
                add_kwargs = {}
                msg.additional_kwargs = add_kwargs
            add_kwargs["follow_ups"] = questions[:8]
            await agent.aupdate_state(config, {"messages": [msg]})
            break
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to persist follow-ups for session %s: %s", session_id, exc)


@router.post("/follow-up")
async def generate_follow_up(request: AgentRequest):
    """
    Generate follow-up questions based on conversation history.
    Non-streaming version that returns all questions at once.
    """
    try:
        sid = session_utils.validate_session_id(request.session_id)

        # Resolve resources
        resources = await resource_resolver.resolve_agent_resources(sid, request)

        # Get checkpointer
        from src.main_agent import app

        checkpointer = app.state.checkpointer

        # Create temporary agent to access state
        temp_agent = create_agent(resources.model, resources.tools, checkpointer=checkpointer)

        # Get conversation state
        state = await temp_agent.aget_state({"configurable": {"thread_id": sid}})
        messages = state.values.get("messages", []) if state else []

        # Generate questions
        questions = await follow_up_service.generate_questions(
            messages=messages,
            llm=resources.model,
            tools=resources.tools,
            openrouter_key=resources.api_key,
        )
        await _persist_follow_ups_to_last_ai_message(
            agent=temp_agent, session_id=sid, questions=questions
        )

        return {"questions": questions, "provider": resources.provider}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Follow-up generation error: {e}")
        return {"questions": []}


@router.post("/follow-up-stream")
async def generate_follow_up_stream(request: AgentRequest):
    """
    Generate follow-up questions with streaming.
    Streams questions as they're generated.
    """
    try:
        sid = session_utils.validate_session_id(request.session_id)

        # Resolve resources
        resources = await resource_resolver.resolve_agent_resources(sid, request)

        # Get checkpointer
        from src.main_agent import app

        checkpointer = app.state.checkpointer

        # Create temporary agent
        temp_agent = create_agent(resources.model, resources.tools, checkpointer=checkpointer)

        # Get conversation state
        state = await temp_agent.aget_state({"configurable": {"thread_id": sid}})
        messages = state.values.get("messages", []) if state else []

        # Stream events generator
        async def event_generator():
            collected_questions: dict[int, str] = {}
            try:
                async for event in follow_up_service.generate_questions_stream(
                    messages=messages,
                    llm=resources.model,
                    tools=resources.tools,
                    openrouter_key=resources.api_key,
                ):
                    if event.get("event") == "token":
                        try:
                            payload = json.loads(str(event.get("data") or "{}"))
                            idx = int(payload.get("index"))
                            token = str(payload.get("token") or "")
                            if token:
                                collected_questions[idx] = (
                                    f"{collected_questions.get(idx, '')}{token}"
                                )
                        except Exception:
                            pass
                    yield event
                ordered = [
                    collected_questions[idx].strip()
                    for idx in sorted(collected_questions.keys())
                    if collected_questions[idx].strip()
                ]
                await _persist_follow_ups_to_last_ai_message(
                    agent=temp_agent,
                    session_id=sid,
                    questions=ordered,
                )
            except Exception as e:
                yield {"event": "error", "data": str(e)}

        return EventSourceResponse(event_generator())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
