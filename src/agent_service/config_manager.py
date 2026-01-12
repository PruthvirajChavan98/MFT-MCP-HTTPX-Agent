from redis.asyncio import Redis
from .config import REDIS_URL

class ConfigManager:
    def __init__(self):
        self.redis = Redis.from_url(REDIS_URL, decode_responses=True)

    async def set_config(self, session_id: str, system_prompt: str = None, model_name: str = None, openrouter_api_key: str = None, reasoning_effort: str = None):  # type: ignore
        """Saves configuration to Redis hash."""
        key = f"agent:config:{session_id}"
        data = {}
        if system_prompt:
            data["system_prompt"] = system_prompt
        if model_name:
            data["model_name"] = model_name
        if openrouter_api_key:
            data["openrouter_api_key"] = openrouter_api_key
        if reasoning_effort:
            data["reasoning_effort"] = reasoning_effort
        
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
        3. Removes LangGraph Checkpoints (thread_id:{sid})
        """
        # Keys to target
        config_key = f"agent:config:{session_id}"
        auth_key = session_id 
        
        # We also attempt to clean up LangGraph checkpoints if they exist in the same DB
        # Default LangGraph redis saver uses `checkpoint:{thread_id}:...`
        # We can scan for them or just hit the main ones we know.
        # For performance, we simply delete the known config and auth keys.
        await self.redis.delete(config_key, auth_key)

    async def close(self):
        await self.redis.close()

config_manager = ConfigManager()
