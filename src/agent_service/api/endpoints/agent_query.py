"""Agent query endpoint (non-streaming)."""
import logging
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent

from src.agent_service.core.schemas import AgentRequest
from src.agent_service.core.session_utils import session_utils
from src.agent_service.core.resource_resolver import resource_resolver
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
        
        # Resolve all resources
        resources = await resource_resolver.resolve_agent_resources(sid, request)
        
        # Router classification (optional, runs in background)
        router_out = None
        try:
            router_out = await nbfc_router_service.classify(
                request.question, 
                openrouter_api_key=resources.api_key
            )
        except Exception as e:
            log.warning(f"Router classification failed: {e}")
            router_out = None
        
        # KB-first guardrail (returns cached response if available)
        kb_payload = await kb_first_payload(request.question, resources.tools)
        if kb_payload:
            return {
                "response": kb_payload["output"],
                "kb_first": True,
                "router": router_out
            }
        
        # Validate tools are loaded
        if not resources.tools:
            raise HTTPException(status_code=500, detail="No tools loaded")
        
        # Get checkpointer from app state
        from fastapi import Request
        # Access via closure or pass as dependency
        from src.main_agent import app
        checkpointer = app.state.checkpointer
        
        # Create and invoke agent
        agent = create_agent(
            resources.model,
            resources.tools,
            system_prompt=resources.system_prompt,
            checkpointer=checkpointer
        )
        
        inputs = {"messages": [HumanMessage(request.question)]}
        resp = await agent.ainvoke(inputs, {"configurable": {"thread_id": sid}})
        
        return {
            "response": resp,
            "router": router_out,
            "provider": resources.provider
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
