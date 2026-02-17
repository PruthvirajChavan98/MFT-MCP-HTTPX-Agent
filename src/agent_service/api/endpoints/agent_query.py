"""Agent query endpoint (non-streaming)."""

import logging

from fastapi import APIRouter, HTTPException

from src.agent_service.core.recursive_rag_graph import (
    build_recursive_rag_graph,
    initial_recursive_rag_state,
)
from src.agent_service.core.resource_resolver import resource_resolver
from src.agent_service.core.schemas import AgentRequest
from src.agent_service.core.session_utils import session_utils
from src.agent_service.features.kb_first import kb_first_payload
from src.agent_service.features.nbfc_router import nbfc_router_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent-query"])


@router.post("/query")
async def query_agent(request: AgentRequest):
    """
    Non-streaming agent query endpoint.
    Processes question and returns complete response.
    """
    try:
        sid = session_utils.validate_session_id(request.session_id)

        resources = await resource_resolver.resolve_agent_resources(sid, request)

        router_out = None
        try:
            router_out = await nbfc_router_service.classify(
                request.question, openrouter_api_key=resources.api_key
            )
        except Exception as e:
            log.warning(f"Router classification failed: {e}")
            router_out = None

        kb_payload = await kb_first_payload(request.question, resources.tools)
        if kb_payload:
            return {"response": kb_payload["output"], "kb_first": True, "router": router_out}

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

        inputs = initial_recursive_rag_state(request.question)
        resp = await graph.ainvoke(inputs, {"configurable": {"thread_id": sid}})

        return {"response": resp, "router": router_out, "provider": resources.provider}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
