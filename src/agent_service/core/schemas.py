from __future__ import annotations

from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field


# =========================
# Agent
# =========================

class AgentRequest(BaseModel):
    session_id: str
    question: str

    # Optional overrides
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None

    # allow "default"/"none" for qwen, and low/medium/high for others
    reasoning_effort: Optional[str] = None


class BaseSessionConfig(BaseModel):
    session_id: str
    system_prompt: Optional[str] = None
    reasoning_effort: Optional[str] = None

    openrouter_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None


class GroqConfig(BaseSessionConfig):
    model_name: str


class OpenRouterConfig(BaseSessionConfig):
    model_name: str


class NvidiaConfig(BaseSessionConfig):
    model_name: str


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
# FAQ / KB
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
    questions: List[str] = Field(description="A list of 5 potential follow-up questions.", min_length=1, max_length=5)


# =========================
# Judge schemas
# =========================

class ScoredQuestion(BaseModel):
    question: str = Field(description="The candidate question text being evaluated.")
    groundedness: int = Field(description="Score (1-10)", ge=1, le=10)
    relevance: int = Field(description="Score (1-10)", ge=1, le=10)
    correctness: int = Field(description="Score (1-10)", ge=1, le=10)

class JudgeResponse(BaseModel):
    evaluations: List[ScoredQuestion] = Field(description="List of evaluated questions with their scores.")