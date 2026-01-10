from typing import Optional, Literal
from pydantic import BaseModel

class AgentRequest(BaseModel):
    session_id: str
    question: str
    # Optional overrides
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    # New: Reasoning Effort (low, medium, high) - mostly for OpenAI o1/o3
    reasoning_effort: Optional[Literal["low", "medium", "high"]] = None

class BaseSessionConfig(BaseModel):
    session_id: str
    system_prompt: Optional[str] = None
    reasoning_effort: Optional[str] = None  # Persist this preference

class GroqConfig(BaseSessionConfig):
    model_name: str 

class OpenRouterConfig(BaseSessionConfig):
    model_name: str 
    openrouter_api_key: Optional[str] = None 
