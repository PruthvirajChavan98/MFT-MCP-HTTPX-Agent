from fastapi import Header, HTTPException
from typing import Optional
from src.agent_service.data.config_manager import config_manager

async def get_byok_credentials(
    session_id: str,
    x_openai_key: Optional[str] = Header(None, alias="X-OpenAI-API-Key"),
    x_groq_key: Optional[str] = Header(None, alias="X-Groq-API-Key"),
    x_nvidia_key: Optional[str] = Header(None, alias="X-Nvidia-API-Key"),
):
    """
    Resolves credentials with a strict hierarchy:
    1. Direct Header (High Priority)
    2. Redis Session Store (Saved BYOK)
    3. Fail with 401
    """
    stored = await config_manager.get_config(session_id)
    
    keys = {
        "openai": x_openai_key or stored.get("openrouter_api_key") or stored.get("openai_api_key"),
        "groq": x_groq_key or stored.get("groq_api_key"),
        "nvidia": x_nvidia_key or stored.get("nvidia_api_key"),
    }

    if not any(keys.values()):
        raise HTTPException(
            status_code=401, 
            detail="BYOK Violation: No valid API keys provided in headers or session."
        )
    
    return keys
