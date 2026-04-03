from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from ragas import SingleTurnSample
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics.collections import AnswerRelevancy, ContextRelevance, Faithfulness

from src.agent_service.core.config import (
    JUDGE_MODEL_NAME,
)
from src.agent_service.llm.client import get_llm, get_owner_embeddings

log = logging.getLogger("ragas_judge")

# Embedding model — same as EvalEmbedder so no extra cost on infra
_EMBED_MODEL = "openai/text-embedding-3-small"

# Per-metric pass thresholds (scores are cosine similarity / NLI probability, 0.0–1.0)
_THRESHOLDS: dict[str, float] = {
    "faithfulness": 0.5,
    "answer_relevancy": 0.5,
    "context_relevance": 0.4,
}


class RagasJudge:
    """
    RAGAS v0.4.x evaluator wired to the user's session model.

    Runs 3 reference-free metrics concurrently:
    - Faithfulness      — is the response grounded in tool outputs? (hallucination check)
    - AnswerRelevancy   — does the response address the question?  (embedding-based)
    - ContextRelevance  — are the tool outputs relevant to the question?

    All metrics use the same LLM the user chose for the agent session, via LangchainLLMWrapper.
    Embeddings (for AnswerRelevancy) reuse the same OpenRouter text-embedding-3-small config
    as EvalEmbedder so there is no additional embedding infrastructure.
    """

    def __init__(
        self,
        model_name: str = JUDGE_MODEL_NAME,
        *,
        openrouter_api_key: str | None = None,
        nvidia_api_key: str | None = None,
        groq_api_key: str | None = None,
    ) -> None:
        self.model_name = model_name

        # 1. Get session's LangChain model — same factory used by the agent itself
        mn = (model_name or "").lower()
        provider: str | None = None
        if openrouter_api_key:
            provider = "openrouter"
        elif nvidia_api_key or mn.startswith("nvidia/"):
            provider = "nvidia"
        elif groq_api_key or ("/" not in mn):
            provider = "groq"

        lc_llm = get_llm(
            model_name=model_name,
            provider=provider,
            openrouter_api_key=openrouter_api_key,
            nvidia_api_key=nvidia_api_key,
            groq_api_key=groq_api_key,
            temperature=0.0,
        )
        wrapped_llm = LangchainLLMWrapper(lc_llm)

        # 2. Embeddings for AnswerRelevancy — same config as EvalEmbedder
        lc_emb = get_owner_embeddings(model=_EMBED_MODEL)
        wrapped_emb = LangchainEmbeddingsWrapper(lc_emb)

        # 3. Metrics — each receives the session's wrapped LLM
        self._faithfulness = Faithfulness(llm=wrapped_llm)
        self._answer_rel = AnswerRelevancy(llm=wrapped_llm, embeddings=wrapped_emb)
        self._context_rel = ContextRelevance(llm=wrapped_llm)

    async def evaluate(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        trace_id: str,
    ) -> list[dict[str, Any]]:
        """
        Run all 3 RAGAS metrics concurrently.

        Returns a list of dicts compatible with the eval_results PostgreSQL schema
        (eval_id, trace_id, metric_name, score, passed, reasoning, evaluator_id, evidence, meta).
        """
        if not question or not answer:
            return []

        sample = SingleTurnSample(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts or [],
        )

        short = self.model_name.split("/", 1)[-1] if "/" in self.model_name else self.model_name
        evaluator_id = f"ragas:{short}"

        scores = await asyncio.gather(
            self._faithfulness.single_turn_ascore(sample),
            self._answer_rel.single_turn_ascore(sample),
            self._context_rel.single_turn_ascore(sample),
            return_exceptions=True,
        )

        metric_names = ["faithfulness", "answer_relevancy", "context_relevance"]
        results: list[dict[str, Any]] = []

        for name, raw in zip(metric_names, scores, strict=False):
            if isinstance(raw, BaseException):
                log.warning("[ragas_judge] %s failed for trace %s: %s", name, trace_id, raw)
                continue
            s = float(raw)
            results.append(
                {
                    "eval_id": uuid.uuid4().hex,
                    "trace_id": trace_id,
                    "metric_name": name,
                    "score": s,
                    "passed": s >= _THRESHOLDS[name],
                    "reasoning": f"RAGAS {name}: {s:.4f}",
                    "evaluator_id": evaluator_id,
                    "evidence": [],
                    "meta": {
                        "framework": "ragas",
                        "version": "0.4.x",
                        "model": self.model_name,
                    },
                }
            )

        return results
