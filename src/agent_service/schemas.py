from typing import Optional, Literal, List
from pydantic import BaseModel

class AgentRequest(BaseModel):
    session_id: str
    question: str
    # Optional overrides
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None  # <--- NEW
    
    # FIX: Changed from Literal["low", "medium", "high"] to str
    # This allows values like "default", "none" (for Qwen) or "low"/"high" (for o1/DeepSeek)
    reasoning_effort: Optional[str] = None

class BaseSessionConfig(BaseModel):
    session_id: str
    system_prompt: Optional[str] = None
    reasoning_effort: Optional[str] = None  # Persist this preference

class GroqConfig(BaseSessionConfig):
    model_name: str 

class OpenRouterConfig(BaseSessionConfig):
    model_name: str 
    openrouter_api_key: Optional[str] = None

# --- NEW CONFIG ---
class NvidiaConfig(BaseSessionConfig):
    model_name: str
    nvidia_api_key: Optional[str] = None  # <--- NEW: Stores the user's BYOK
    
class FAQItem(BaseModel):
    question: str
    answer: str

class FAQBatchRequest(BaseModel):
    items: List[FAQItem]
