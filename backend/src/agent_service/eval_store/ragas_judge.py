from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics.collections import AnswerRelevancy, ContextRelevance, Faithfulness

from src.agent_service.core.config import (
    JUDGE_MODEL_NAME,
    RAGAS_PER_METRIC_TIMEOUT_S,
)
from src.agent_service.llm.client import get_llm, get_owner_embeddings
from src.agent_service.llm.groq_rotator import next_groq_keys

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
        """Single-LLM constructor — used when a session/user BYOK key is present.

        The eval path that has no session key should call
        ``await RagasJudge.for_eval(model_name)`` instead, which fans out
        3 distinct Groq keys across the 3 metrics via the shared rotator.
        """
        self.model_name = model_name
        wrapped_llm = self._build_wrapped_llm(
            model_name=model_name,
            openrouter_api_key=openrouter_api_key,
            nvidia_api_key=nvidia_api_key,
            groq_api_key=groq_api_key,
        )
        wrapped_emb = self._build_wrapped_embeddings()

        self._faithfulness = Faithfulness(llm=wrapped_llm)
        self._answer_rel = AnswerRelevancy(llm=wrapped_llm, embeddings=wrapped_emb)
        self._context_rel = ContextRelevance(llm=wrapped_llm)

    @classmethod
    async def for_eval(
        cls,
        model_name: str = JUDGE_MODEL_NAME,
        *,
        openrouter_api_key: str | None = None,
        nvidia_api_key: str | None = None,
    ) -> RagasJudge:
        """Build a judge for the eval/shadow path with per-metric Groq keys.

        When provider resolves to Groq, each metric gets its own API key
        (3 distinct keys when ``len(GROQ_API_KEYS) >= 3``) so the 3 concurrent
        ``ascore`` calls cannot saturate a single key. For OpenRouter / Nvidia
        callers this collapses to the single-LLM path.
        """
        mn = (model_name or "").lower()
        # Groq is implied when no other provider key is present AND the model
        # name does not carry the `nvidia/` prefix. OpenRouter-prefixed models
        # (e.g. `openai/gpt-oss-120b`) route through Groq in this deployment,
        # so that case stays on the Groq rotator path.
        is_groq = not openrouter_api_key and not nvidia_api_key and not mn.startswith("nvidia/")

        if not is_groq:
            return cls(
                model_name=model_name,
                openrouter_api_key=openrouter_api_key,
                nvidia_api_key=nvidia_api_key,
            )

        keys = await next_groq_keys(3)
        judge = cls.__new__(cls)
        judge.model_name = model_name

        wrapped_llms = [
            LangchainLLMWrapper(
                get_llm(
                    model_name=model_name,
                    provider="groq",
                    groq_api_key=k,
                    temperature=0.0,
                )
            )
            for k in keys
        ]
        wrapped_emb = cls._build_wrapped_embeddings()

        judge._faithfulness = Faithfulness(llm=wrapped_llms[0])
        judge._answer_rel = AnswerRelevancy(llm=wrapped_llms[1], embeddings=wrapped_emb)
        judge._context_rel = ContextRelevance(llm=wrapped_llms[2])
        judge._metric_keys = keys  # exposed for tests/observability
        return judge

    @staticmethod
    def _build_wrapped_llm(
        *,
        model_name: str,
        openrouter_api_key: str | None,
        nvidia_api_key: str | None,
        groq_api_key: str | None,
    ) -> LangchainLLMWrapper:
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
        return LangchainLLMWrapper(lc_llm)

    @staticmethod
    def _build_wrapped_embeddings() -> LangchainEmbeddingsWrapper:
        return LangchainEmbeddingsWrapper(get_owner_embeddings(model=_EMBED_MODEL))

    async def evaluate(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        trace_id: str,
    ) -> list[dict[str, Any]]:
        """Run the 3 RAGAS metrics concurrently with per-metric timeout.

        One slow or rate-limited metric cannot stall the other two; timed-out
        metrics are logged and skipped (schema-compatible with the existing
        eval_results pipeline which already tolerates partial results).
        """
        if not question or not answer:
            return []

        ctxs = contexts or []
        short = self.model_name.split("/", 1)[-1] if "/" in self.model_name else self.model_name
        evaluator_id = f"ragas:{short}"

        # `answer_relevancy` is the only metric that scores meaningfully without
        # retrieved contexts. `faithfulness` and `context_relevance` need
        # tool-call outputs and would raise / score 0 on an empty list — gate
        # them so tool-less traces still produce ≥1 RAGAS row instead of zero.
        metric_coros: list[tuple[str, Any]] = [
            (
                "answer_relevancy",
                self._answer_rel.ascore(user_input=question, response=answer),
            ),
        ]
        if ctxs:
            metric_coros.append(
                (
                    "faithfulness",
                    self._faithfulness.ascore(
                        user_input=question, response=answer, retrieved_contexts=ctxs
                    ),
                )
            )
            metric_coros.append(
                (
                    "context_relevance",
                    self._context_rel.ascore(user_input=question, retrieved_contexts=ctxs),
                )
            )

        async def _scored(name: str, coro: Any) -> tuple[str, float | BaseException]:
            try:
                value = await asyncio.wait_for(coro, timeout=RAGAS_PER_METRIC_TIMEOUT_S)
            except (TimeoutError, asyncio.TimeoutError) as exc:
                log.warning(
                    "[ragas_judge] %s timed out after %ss for trace %s",
                    name,
                    RAGAS_PER_METRIC_TIMEOUT_S,
                    trace_id,
                )
                return name, exc
            except Exception as exc:  # noqa: BLE001
                return name, exc
            return name, value

        scored = await asyncio.gather(
            *(_scored(name, coro) for name, coro in metric_coros),
        )

        results: list[dict[str, Any]] = []
        for name, raw in scored:
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
