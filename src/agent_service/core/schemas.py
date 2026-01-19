# src/agent_service/schemas.py
from typing import Optional, Literal, List
from pydantic import BaseModel, Field

class AgentRequest(BaseModel):
    session_id: str
    question: str
    # Optional overrides
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    
    # FIX: Changed from Literal["low", "medium", "high"] to str
    # This allows values like "default", "none" (for Qwen) or "low"/"high" (for o1/DeepSeek)
    reasoning_effort: Optional[str] = None

class BaseSessionConfig(BaseModel):
    session_id: str
    system_prompt: Optional[str] = None
    reasoning_effort: Optional[str] = None  # Persist this preference
    
    # --- FIX: Define keys here so they are valid for ANY provider ---
    openrouter_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None

class GroqConfig(BaseSessionConfig):
    model_name: str 

class OpenRouterConfig(BaseSessionConfig):
    model_name: str 

class NvidiaConfig(BaseSessionConfig):
    model_name: str
    
class FAQItem(BaseModel):
    question: str
    answer: str

class FAQBatchRequest(BaseModel):
    items: List[FAQItem]
    
class FollowUpResponse(BaseModel):
    """Initial raw generation of candidates."""
    questions: List[str] = Field(
        description="A list of 5 potential follow-up questions.",
        min_length=1,
        max_length=5
    )

# --- NEW: Structures for the Judge ---
class ScoredQuestion(BaseModel):
    """Evaluation of a single candidate question."""
    question: str = Field(description="The candidate question text being evaluated.")
    groundedness: int = Field(
        description="Score (1-10): Is this question supported by the Knowledge Base or Tools? (1=Hallucination, 10=Fully supported)",
        ge=1, le=10
    )
    relevance: int = Field(
        description="Score (1-10): Does this logically follow the Assistant's last answer? (1=Random, 10=Perfect flow)",
        ge=1, le=10
    )
    correctness: int = Field(
        description="Score (1-10): Is the question safe, grammatically correct, and non-repetitive? (1=Bad, 10=Perfect)",
        ge=1, le=10
    )

class JudgeResponse(BaseModel):
    """The Judge's final output containing scored candidates."""
    evaluations: List[ScoredQuestion] = Field(
        description="List of evaluated questions with their scores."
    )

class FAQItem(BaseModel):
    question: str
    answer: str

class FAQBatchRequest(BaseModel):
    items: List[FAQItem]

class FAQEditRequest(BaseModel):
    original_question: str
    new_question: Optional[str] = None
    new_answer: Optional[str] = None

class FAQSemanticSearchRequest(BaseModel):
    query: str
    limit: int = 5

class FAQSemanticDeleteRequest(BaseModel):
    query: str
    threshold: float = 0.92