from redis.asyncio import Redis
from typing import Optional
from src.agent_service.core.config import REDIS_URL

class ConfigManager:
    def __init__(self):
        self.redis = Redis.from_url(REDIS_URL, decode_responses=True)

    async def set_config(
        self, 
        session_id: str, 
        system_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        nvidia_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        provider: Optional[str] = None
    ) -> None:
        """Saves configuration to Redis hash."""
        key = f"agent:config:{session_id}"
        data = {}
        if system_prompt:
            data["system_prompt"] = system_prompt
        if model_name:
            data["model_name"] = model_name
        if openrouter_api_key:
            data["openrouter_api_key"] = openrouter_api_key
        if nvidia_api_key is not None:
            data["nvidia_api_key"] = nvidia_api_key
        if groq_api_key:
            data["groq_api_key"] = groq_api_key
        if reasoning_effort:
            data["reasoning_effort"] = reasoning_effort
        if provider:
            data["provider"] = provider
        
        if data:
            await self.redis.hset(key, mapping=data) # type: ignore

    async def get_config(self, session_id: str) -> dict:
        key = f"agent:config:{session_id}"
        return await self.redis.hgetall(key)  # type: ignore

    async def session_exists(self, session_id: str) -> bool:
        key = f"agent:config:{session_id}"
        return await self.redis.exists(key) > 0

    async def list_sessions(self) -> list[str]:
        sessions = []
        async for key in self.redis.scan_iter(match="agent:config:*"):
            try:
                parts = key.split(":")
                if len(parts) >= 3:
                    sid = ":".join(parts[2:]) 
                    sessions.append(sid)
            except Exception:
                continue
        return sessions
    
    async def delete_session(self, session_id: str):
        """
        Hard delete for a session:
        1. Removes Agent Configuration (agent:config:{sid})
        2. Removes MCP Auth Data (stored at root {sid})
        """
        config_key = f"agent:config:{session_id}"
        auth_key = session_id 
        
        await self.redis.delete(config_key, auth_key)

    async def close(self):
        await self.redis.close()

config_manager = ConfigManager()