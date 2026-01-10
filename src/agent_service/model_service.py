import json
import httpx
import asyncio
import logging
from typing import List, Dict, Any
from redis.asyncio import Redis
from .config import REDIS_URL

log = logging.getLogger("model_service")

class ModelService:
    def __init__(self):
        self.redis = Redis.from_url(REDIS_URL, decode_responses=True)
        self.CACHE_KEY = "agent:models:cache_all" # Updated key to reflect full dataset
        self.REFRESH_INTERVAL = 1800  # 30 minutes

    async def fetch_openrouter_data(self) -> List[Dict[str, Any]]:
        """Fetches ALL models from OpenRouter without filtering."""
        url = "https://openrouter.ai/api/v1/models"
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    log.error(f"OpenRouter returned {resp.status_code}")
                    return []
                
                data = resp.json().get("data", [])
                results = []
                
                for m in data:
                    pricing = m.get("pricing", {})
                    try:
                        p_price = float(pricing.get("prompt", "0")) * 1_000_000
                        c_price = float(pricing.get("completion", "0")) * 1_000_000
                    except (ValueError, TypeError):
                        p_price = c_price = 0.0

                    results.append({
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "context_length": m.get("context_length", 0),
                        "pricing": {
                            "prompt": p_price,
                            "completion": c_price,
                            "unit": "1M tokens"
                        },
                        "supported_parameters": m.get("supported_parameters", [])
                    })
                return results
            except Exception as e:
                log.error(f"Fetch Error: {e}")
                return []

    async def refresh_cache(self):
        """Fetches ALL data, categorizes it, and saves to Redis."""
        log.info("Refreshing Full Model Cache...")
        
        models = await self.fetch_openrouter_data()
        
        categories: Dict[str, List[Dict]] = {}
        for m in models:
            parts = m["id"].split("/")
            provider = parts[0] if len(parts) > 1 else "other"
            
            if provider not in categories:
                categories[provider] = []
            categories[provider].append(m)

        structured_data = [
            {"name": provider, "models": model_list}
            for provider, model_list in categories.items()
        ]
        
        structured_data.sort(key=lambda x: x["name"])
        
        await self.redis.set(self.CACHE_KEY, json.dumps(structured_data))
        log.info(f"Cache updated. Stored {len(models)} models across {len(categories)} providers.")

    async def get_cached_data(self) -> List[Dict[str, Any]]:
        raw = await self.redis.get(self.CACHE_KEY)
        if not raw: return []
        return json.loads(raw)

    async def start_background_loop(self):
        while True:
            try:
                await self.refresh_cache()
            except Exception as e:
                log.error(f"Background refresh failed: {e}")
            await asyncio.sleep(self.REFRESH_INTERVAL)

model_service = ModelService()
