from typing import Optional
from pydantic import BaseModel

class AgentRequest(BaseModel):
    session_id: str
    question: str
    # Optional overrides still allowed per-request
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None

class SessionConfig(BaseModel):
    session_id: str
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None
