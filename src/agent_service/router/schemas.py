from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any

SentimentLabel = Literal["positive", "neutral", "negative"]
RouterBackend = Literal["embeddings", "llm_glm_4.7", "hybrid"]

class LabelScore(BaseModel):
    label: str
    score: float = Field(ge=0.0, le=1.0)
    top: Optional[list[tuple[str, float]]] = None

class RouterResult(BaseModel):
    backend: RouterBackend
    sentiment: LabelScore
    reason: Optional[LabelScore] = None
    override: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)