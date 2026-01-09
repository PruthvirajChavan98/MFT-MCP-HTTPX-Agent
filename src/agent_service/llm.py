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
    """Fetches the list of available models from Groq API."""
    url = f"{GROQ_BASE_URL}/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch models from Groq: {e}")