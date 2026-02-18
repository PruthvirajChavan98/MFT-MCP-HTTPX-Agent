from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import OpenAIEmbeddings

from src.agent_service.core.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from src.agent_service.llm.client import get_llm

from .prototypes_nbfc import REASON_PROTOTYPES, SENTIMENT_PROTOTYPES
from .schemas import LabelScore, RouterResult

# Regex Patterns
_PROFANITY = re.compile(r"\b(wtf|bc|mc|bkl|madarchod|behenchod)\b", re.I)
_NEG_CUES = re.compile(
    r"\b(refund|charged twice|not coming|failed|harass|fraud|unauthorized|penalty)\b", re.I
)
_POS_CUES = re.compile(r"\b(thanks|thank you|love|great|mast|awesome|super smooth)\b", re.I)


def _cosine_top(
    qv: List[float],
    proto_vecs: Dict[str, List[List[float]]],
    *,
    topn: int = 3,
) -> Tuple[str, float, List[Tuple[str, float]]]:
    import math

    def cos(a, b):
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        na = math.sqrt(sum(x * x for x in a)) or 1e-9
        nb = math.sqrt(sum(x * x for x in b)) or 1e-9
        return dot / (na * nb)

    scored: List[Tuple[str, float]] = []
    for label, vecs in proto_vecs.items():
        best = max((cos(qv, pv) for pv in vecs), default=-1.0)
        scored.append((label, float(best)))

    scored.sort(key=lambda x: x[1], reverse=True)
    best_label, best_score = scored[0]
    return best_label, best_score, scored[:topn]


class RouterService:
    def __init__(self):
        # We perform lazy initialization of embeddings to allow for BYOK injection
        # or graceful failure if no server-side key exists.
        self._sent_proto_vecs: Optional[Dict[str, List[List[float]]]] = None
        self._reason_proto_vecs: Optional[Dict[str, List[List[float]]]] = None

    def _get_embedder(self, api_key: Optional[str] = None):
        key = api_key or OPENROUTER_API_KEY
        if not key:
            raise ValueError("Router requires an OpenRouter API Key (Server or Request).")

        return OpenAIEmbeddings(
            model="openai/text-embedding-3-small",
            api_key=key,
            base_url=OPENROUTER_BASE_URL,
            check_embedding_ctx_length=False,
        )

    async def warm(self, api_key: Optional[str] = None):
        if self._sent_proto_vecs is not None:
            return

        emb = self._get_embedder(api_key)

        self._sent_proto_vecs = {}
        for k, texts in SENTIMENT_PROTOTYPES.items():
            self._sent_proto_vecs[k] = [await emb.aembed_query(t) for t in texts]

        self._reason_proto_vecs = {}
        for k, texts in REASON_PROTOTYPES.items():
            self._reason_proto_vecs[k] = [await emb.aembed_query(t) for t in texts]

    def _override_sentiment(self, text: str) -> Optional[Tuple[str, str]]:
        t = text or ""
        if _POS_CUES.search(t) and not _NEG_CUES.search(t):
            return ("positive", "positive_cues")
        if _PROFANITY.search(t) and not _POS_CUES.search(t):
            return ("negative", "profanity")
        if _NEG_CUES.search(t) and not _POS_CUES.search(t):
            return ("negative", "negative_cues")
        return None

    async def classify_embeddings(
        self,
        text: str,
        openrouter_api_key: Optional[str] = None,
        *,
        sent_threshold: float = 0.24,
        reason_threshold: float = 0.32,
    ) -> RouterResult:
        await self.warm(openrouter_api_key)
        assert self._sent_proto_vecs and self._reason_proto_vecs

        # Use the specific key for this query
        emb = self._get_embedder(openrouter_api_key)

        t0 = time.perf_counter()
        qv = await emb.aembed_query(text)

        # Sentiment
        s_label, s_score, s_top = _cosine_top(qv, self._sent_proto_vecs, topn=3)

        override = None
        ov = self._override_sentiment(text)
        if ov:
            s_label, override = ov[0], ov[1]
            s_score = max(s_score, 0.60)

        sentiment = LabelScore(label=s_label, score=float(s_score), top=s_top)

        # Reason
        reason = None
        if s_label == "negative" or (s_label == "neutral" and s_score < 0.55):
            r_label, r_score, r_top = _cosine_top(qv, self._reason_proto_vecs, topn=3)
            if r_score >= reason_threshold:
                reason = LabelScore(label=r_label, score=float(r_score), top=r_top)
            else:
                reason = LabelScore(label="unknown", score=float(r_score), top=r_top)

        dt = (time.perf_counter() - t0) * 1000
        return RouterResult(
            backend="embeddings",
            sentiment=sentiment,
            reason=reason,
            override=override,
            meta={"latency_ms": round(dt, 2)},
        )

    async def classify_llm_glm47(
        self, text: str, *, openrouter_api_key: Optional[str] = None
    ) -> RouterResult:
        llm = get_llm(
            model_name="z-ai/glm-4.7",
            openrouter_api_key=openrouter_api_key,
        )

        parser = JsonOutputParser()
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a strict classifier. Return ONLY JSON."),
                (
                    "human",
                    """
Classify this NBFC customer message into:
- sentiment: positive|neutral|negative
- reason: one of: application_status_approval, lead_intent_new_loan, disbursal, emi_payment_reflecting, charges_fees_penalty,
  statement_receipt, otp_login_app_tech, kyc_verification, nach_autodebit_bounce, collections_harassment, foreclosure_partpayment,
  fraud_security, customer_support, unknown
Return JSON:
{{
  "sentiment": {{"label":"...", "score":0.0-1.0}},
  "reason": {{"label":"...", "score":0.0-1.0}},
  "rationale": "optional"
}}

Text: {text}
""",
                ),
            ]
        )
        chain = prompt | llm | parser
        out = await chain.ainvoke({"text": text})

        sent = out.get("sentiment") or {}
        rea = out.get("reason") or {}

        return RouterResult(
            backend="llm_glm_4.7",
            sentiment=LabelScore(
                label=str(sent.get("label", "unknown")), score=float(sent.get("score", 0.0))
            ),
            reason=LabelScore(
                label=str(rea.get("label", "unknown")), score=float(rea.get("score", 0.0))
            ),
            meta={"rationale": out.get("rationale")},
        )

    async def classify(
        self, text: str, openrouter_api_key: Optional[str] = None, mode: Optional[str] = None
    ) -> RouterResult:
        # Default behavior
        return await self.classify_hybrid(text, openrouter_api_key=openrouter_api_key)

    async def classify_hybrid(
        self, text: str, *, openrouter_api_key: Optional[str] = None
    ) -> RouterResult:
        emb = await self.classify_embeddings(text, openrouter_api_key=openrouter_api_key)

        s = emb.sentiment
        need_llm = (s.score < 0.55) or (
            s.label == "neutral" and (emb.reason and emb.reason.label == "unknown")
        )

        if not need_llm:
            emb.backend = "hybrid"  # type: ignore
            emb.meta["selected"] = "embeddings"
            return emb

        llm = await self.classify_llm_glm47(text, openrouter_api_key=openrouter_api_key)
        llm.backend = "hybrid"  # type: ignore
        llm.meta["selected"] = "llm_glm_4.7"
        return llm

    async def compare(self, text: str, openrouter_api_key: Optional[str] = None) -> Any:
        # Debug tool to run both
        e = await self.classify_embeddings(text, openrouter_api_key=openrouter_api_key)
        l = await self.classify_llm_glm47(text, openrouter_api_key=openrouter_api_key)
        return {"embeddings": e, "llm": l}
