import httpx
from langchain_groq import ChatGroq
from .config import GROQ_API_KEY, GROQ_BASE_URL, MODEL_NAME

def get_llm(model_name: str = None): # type: ignore
    """
    Returns an LLM instance.
    If model_name is provided, it overrides the default configuration.
    """
    target_model = model_name or MODEL_NAME
    
    return ChatGroq(
        api_key=GROQ_API_KEY, # type: ignore
        base_url=GROQ_BASE_URL,
        model=target_model,
        streaming=True,
        temperature=0.0,
        reasoning_format="parsed" 
    )

# Initialize Default LLM instance for backward compatibility
llm = get_llm()

async def get_available_models() -> dict:
    """
    Fetches the list of available models from Groq API.
    Filters out 'whisper' models to ensure only chat models are returned.
    """
    url = f"{GROQ_BASE_URL}/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            
            # Logic: Filter out models where ID contains "whisper" (case-insensitive)
            if "data" in data and isinstance(data["data"], list):
                filtered_models = [
                    model for model in data["data"]
                    if "whisper" not in model.get("id", "").lower()
                ]
                data["data"] = filtered_models
                
            return data
        except Exception as e:
            raise RuntimeError(f"Failed to fetch models from Groq: {e}")
