"""Agent query endpoint (non-streaming)."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.agent_service.core.config import AGENT_INLINE_ROUTER_ENABLED, AGENT_INLINE_ROUTER_EXPOSE
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


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content) if content is not None else ""


def _extract_final_response(graph_output: Any) -> str:
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


@router.post("/query")
async def query_agent(request: AgentRequest):
    """
    Non-streaming agent query endpoint.
    Returns only user-safe response payload (no internal graph state).
    """
    try:
        sid = session_utils.validate_session_id(request.session_id)

        resources = await resource_resolver.resolve_agent_resources(sid, request)

        router_out: Dict[str, Any] | None = None
        if AGENT_INLINE_ROUTER_ENABLED:
            try:
                router_out = await nbfc_router_service.classify(
                    request.question,
                    openrouter_api_key=resources.api_key,
                    tools=resources.tools,
                )
            except Exception as e:
                log.warning(f"Router classification failed: {e}")
                router_out = None

        kb_payload = await kb_first_payload(request.question, resources.tools)
        if kb_payload:
            out = {
                "response": str(kb_payload["output"]),
                "kb_first": True,
                "provider": resources.provider,
                "model": resources.model_name,
            }
            if AGENT_INLINE_ROUTER_ENABLED and AGENT_INLINE_ROUTER_EXPOSE and router_out:
                out["router"] = router_out
            return out

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
        final_text = _extract_final_response(resp)

        out = {
            "response": final_text,
            "provider": resources.provider,
            "model": resources.model_name,
            "kb_first": False,
        }
        if AGENT_INLINE_ROUTER_ENABLED and AGENT_INLINE_ROUTER_EXPOSE and router_out:
            out["router"] = router_out
        return out

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
