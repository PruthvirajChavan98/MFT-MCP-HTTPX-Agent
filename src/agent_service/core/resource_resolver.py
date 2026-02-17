"""
Agent Resource Resolution
Handles model, tool, and configuration resolution for agent requests.
"""
import logging
from typing import Optional, List, Any, Tuple
from dataclasses import dataclass

from src.agent_service.core.config import MODEL_NAME
from src.agent_service.core.prompts import SYSTEM_PROMPT
from src.agent_service.core.schemas import AgentRequest
from src.agent_service.data.config_manager import config_manager
from src.agent_service.llm.client import get_llm
from src.agent_service.tools.mcp_manager import mcp_manager

log = logging.getLogger(__name__)


@dataclass
class ResolvedResources:
    """Container for resolved agent resources."""
    model: Any
    tools: List[Any]
    system_prompt: str
    model_name: str
    provider: str
    
    # All three API keys
    openrouter_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    
    reasoning_effort: Optional[str] = None
    
    # Legacy alias for backward compatibility
    @property
    def api_key(self) -> Optional[str]:
        """Alias for openrouter_api_key for backward compatibility."""
        return self.openrouter_api_key


class ResourceResolver:
    """Resolves models, tools, and configurations for agent execution."""
    
    @staticmethod
    def infer_provider_from_model_name(model_name: Optional[str]) -> str:
        """Infer provider from model name prefix."""
        if not model_name:
            return "groq"
        
        mn = model_name.strip().lower()
        
        if mn.startswith("nvidia/"):
            return "nvidia"
        if mn.startswith("groq/"):
            return "groq"
        if "/" in mn:
            return "openrouter"
        
        return "groq"
    
    @staticmethod
    async def resolve_agent_resources(session_id: str, request: AgentRequest) -> ResolvedResources:
        """Resolve all resources needed for agent execution."""
        try:
            saved_config = await config_manager.get_config(session_id)
            
            model_name = request.model_name or saved_config.get("model_name") or MODEL_NAME
            system_prompt = request.system_prompt or saved_config.get("system_prompt") or SYSTEM_PROMPT.strip()
            reasoning_effort = request.reasoning_effort or saved_config.get("reasoning_effort")
            provider = request.provider or saved_config.get("provider") or ResourceResolver.infer_provider_from_model_name(model_name)
            
            openrouter_key = request.openrouter_api_key or saved_config.get("openrouter_api_key")
            nvidia_key = request.nvidia_api_key or saved_config.get("nvidia_api_key")
            groq_key = request.groq_api_key or saved_config.get("groq_api_key")
            
            # Get LLM (returns tuple: model, actual_provider)
            llm_result = get_llm(
                model_name=model_name,
                provider=provider,
                openrouter_api_key=openrouter_key,
                nvidia_api_key=nvidia_key,
                groq_api_key=groq_key,
                reasoning_effort=reasoning_effort
            )
            
            # Handle both tuple and single return value for backward compatibility
            if isinstance(llm_result, tuple):
                model, actual_provider = llm_result
            else:
                model = llm_result
                actual_provider = provider
            
            tools = mcp_manager.rebuild_tools_for_user(session_id, openrouter_api_key=openrouter_key)
            
            return ResolvedResources(
                model=model,
                tools=tools,
                system_prompt=system_prompt,
                model_name=model_name,
                provider=actual_provider,
                openrouter_api_key=openrouter_key,
                nvidia_api_key=nvidia_key,
                groq_api_key=groq_key,
                reasoning_effort=reasoning_effort
            )
            
        except Exception as e:
            log.error(f"Resource resolution failed for session {session_id}: {e}")
            raise ValueError(f"Failed to resolve agent resources: {e}") from e


# Singleton instance
resource_resolver = ResourceResolver()
