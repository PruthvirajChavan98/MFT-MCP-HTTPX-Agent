from redis.asyncio import Redis
from .config import REDIS_URL

class ConfigManager:
    def __init__(self):
        # Redis client for metadata/configuration
        self.redis = Redis.from_url(REDIS_URL, decode_responses=True)

    async def set_config(self, session_id: str, system_prompt: str = None, model_name: str = None):  # type: ignore
        """Saves configuration to Redis hash."""
        key = f"agent:config:{session_id}"
        data = {}
        if system_prompt:
            data["system_prompt"] = system_prompt
        if model_name:
            data["model_name"] = model_name
        
        if data:
            # hset returns number of fields added, not success/fail (it rarely fails)
            await self.redis.hset(key, mapping=data) # type: ignore

    async def get_config(self, session_id: str) -> dict:
        """Retrieves configuration from Redis."""
        key = f"agent:config:{session_id}"
        return await self.redis.hgetall(key)  # type: ignore

    async def session_exists(self, session_id: str) -> bool:
        """Checks if a custom configuration exists for this session."""
        key = f"agent:config:{session_id}"
        return await self.redis.exists(key) > 0

    async def list_sessions(self) -> list[str]:
        """Lists all session IDs that have custom configurations."""
        sessions = []
        # Use scan_iter for safer, cleaner iteration
        async for key in self.redis.scan_iter(match="agent:config:*"):
            # Key format: agent:config:{session_id}
            try:
                # Split by ':' and take the last part. 
                # Handle cases where session_id might contain ':' (unlikely but safe)
                parts = key.split(":")
                if len(parts) >= 3:
                    # Join back in case session_id had colons, though typically it's the last part
                    sid = ":".join(parts[2:]) 
                    sessions.append(sid)
            except Exception:
                continue
        return sessions

    async def close(self):
        await self.redis.close()

# Singleton
config_manager = ConfigManager()
