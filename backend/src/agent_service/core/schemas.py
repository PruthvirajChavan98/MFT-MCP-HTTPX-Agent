from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# =========================
# Agent & Session Configuration
# =========================


class AgentRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier")
    question: str = Field(..., description="User query")


class SessionConfig(BaseModel):
    """
    Unified configuration for a session.
    Replaces separate GroqConfig/OpenRouterConfig/NvidiaConfig.
    """

    session_id: str
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None
    reasoning_effort: Optional[str] = None
    provider: Optional[Literal["groq", "openrouter", "nvidia"]] = None

    # Persisted Keys
    openrouter_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None


# =========================
# NBFC Router (GLM vs Embeddings)
# =========================

RouterMode = Literal["embeddings", "llm", "hybrid", "compare"]


class RouterClassifyRequest(BaseModel):
    session_id: Optional[str] = None
    text: str
    mode: Optional[RouterMode] = None
    openrouter_api_key: Optional[str] = None


class RouterResultResponse(BaseModel):
    backend: str
    sentiment: Dict[str, Any]
    reason: Optional[Dict[str, Any]] = None
    embeddings: Optional[Dict[str, Any]] = None
    llm: Optional[Dict[str, Any]] = None
    disabled: Optional[bool] = None


# =========================
# FAQ / Knowledge Base
# =========================


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


# =========================
# Follow-up
# =========================


class FollowUpResponse(BaseModel):
    questions: List[str] = Field(
        description="A list of 5 potential follow-up questions.", min_length=1, max_length=5
    )


# =========================
# Judge Schemas
# =========================


class ScoredQuestion(BaseModel):
    question: str = Field(description="The candidate question text being evaluated.")
    groundedness: int = Field(description="Score (1-10)", ge=1, le=10)
    relevance: int = Field(description="Score (1-10)", ge=1, le=10)
    correctness: int = Field(description="Score (1-10)", ge=1, le=10)


class JudgeResponse(BaseModel):
    evaluations: List[ScoredQuestion] = Field(
        description="List of evaluated questions with their scores."
    )


# =========================
# Cost Tracking
# =========================


class TokenUsage(BaseModel):
    """Detailed token usage breakdown."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # Optional advanced fields
    reasoning_tokens: Optional[int] = None  # For DeepSeek/O1/Qwen reasoning models
    cached_tokens: Optional[int] = None  # For Claude/Gemini cache hits
    audio_tokens: Optional[int] = None  # For multimodal audio


class CostBreakdown(BaseModel):
    """Detailed cost breakdown with pricing."""

    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    reasoning_cost: Optional[float] = None
    cached_cost: Optional[float] = None
    total_cost: float = 0.0

    # Metadata
    model: str
    provider: str
    currency: str = "USD"

    # Token details
    usage: TokenUsage
