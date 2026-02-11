import logging
from typing import Dict, Optional
from src.agent_service.llm.catalog import model_service

log = logging.getLogger("cost_tracker")

async def calculate_run_cost(model_id: str, usage: Dict[str, int]) -> float:
    """
    Calculates the estimated cost of a run based on usage stats and cached pricing.
    """
    if not usage or not model_id:
        return 0.0

    try:
        # Standardize model ID (trim spaces)
        target = model_id.strip()
        
        # 1. Fetch pricing dynamically for ANY provider (OpenAI, Anthropic, DeepSeek, etc.)
        pricing = await model_service.get_price(target)
        
        if not pricing:
            # If explicit lookup fails, try to find a fallback match (e.g. ignoring quantization suffixes)
            # This logic could be expanded, but for now we fail safe to 0.0
            return 0.0

        prompt_tokens = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)

        p_rate = float(pricing.get("prompt", 0))
        c_rate = float(pricing.get("completion", 0))

        cost = (prompt_tokens * p_rate) + (completion_tokens * c_rate)
        return cost

    except Exception as e:
        log.warning(f"Failed to calculate cost for {model_id}: {e}")
        return 0.0
