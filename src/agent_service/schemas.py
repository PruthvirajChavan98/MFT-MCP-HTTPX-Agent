from pydantic import BaseModel

class AgentRequest(BaseModel):
    session_id: str
    question: str
