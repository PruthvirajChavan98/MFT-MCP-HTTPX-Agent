from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel

from src.agent_service.core.config import (
    NBFC_ROUTER_ANSWERABILITY_ENABLED,
    NBFC_ROUTER_CHAT_MODEL,
    NBFC_ROUTER_EMBED_MODEL,
    NBFC_ROUTER_ENABLED,
    NBFC_ROUTER_FALLBACK_REASON_SCORE,
    NBFC_ROUTER_FALLBACK_SENTIMENT_SCORE,
    NBFC_ROUTER_MODE,
    NBFC_ROUTER_REASON_UNKNOWN_GATE,
    NBFC_ROUTER_SENTIMENT_MARGIN,
    NBFC_ROUTER_SENTIMENT_THRESHOLD,
)
from src.agent_service.core.session_utils import get_redis
from src.agent_service.features.answerability import QueryAnswerabilityClassifier

# Enterprise Imports (Use Factory, not raw classes)
from src.agent_service.llm.client import get_embeddings, get_llm

from .prototypes_nbfc import REASON_PROTOTYPES, SENTIMENT_PROTOTYPES

# =============================================================================
# Labels & Constants
# =============================================================================

SentimentLabel = Literal["positive", "neutral", "negative", "mixed", "unknown"]
ReasonLabel = Literal[
    "lead_intent_new_loan",
    "eligibility_offer",
    "loan_terms_rates",
    "kyc_verification",
    "otp_login_app_tech",
    "application_status_approval",
    "disbursal",
    "emi_payment_reflecting",
    "nach_autodebit_bounce",
    "charges_fees_penalty",
    "foreclosure_partpayment",
    "statement_receipt",
    "collections_harassment",
    "fraud_security",
    "customer_support",
    "unknown",
]
VALID_SENTIMENT_LABELS: set[str] = {"positive", "neutral", "negative", "mixed", "unknown"}
VALID_REASON_LABELS: set[str] = {
    "lead_intent_new_loan",
    "eligibility_offer",
    "loan_terms_rates",
    "kyc_verification",
    "otp_login_app_tech",
    "application_status_approval",
    "disbursal",
    "emi_payment_reflecting",
    "nach_autodebit_bounce",
    "charges_fees_penalty",
    "foreclosure_partpayment",
    "statement_receipt",
    "collections_harassment",
    "fraud_security",
    "customer_support",
    "unknown",
}

FORCE_LLM_RE = re.compile(r"\b(fraud|unauthorized|harass|harassment|threat|abuse)\b", re.I)
PROFANITY_RE = re.compile(
    r"\b(fuck|fucking|wtf|shit|madarchod|bhenchod|bc|mc|chutiya|gandu)\b", re.I
)
POS_CUES_RE = re.compile(
    r"\b(thanks|thank you|thx|love|loved|awesome|amazing|great|super smooth|mast|bhadiya|badiya)\b|(❤️|😍|🔥|💯)",
    re.I,
)
NEG_EMOTION_RE = re.compile(
    r"\b(worst|pathetic|unacceptable|frustrat|pissed|angry|annoyed|harass|fraud|refund|charged twice)\b",
    re.I,
)
FORECLOSE_RE = re.compile(r"\b(foreclose|foreclosure|preclose|part payment|partpay|noc)\b", re.I)
QUESTION_RE = re.compile(r"(\?|how much|how to|charges|fee|process|kya|kaise|kitna|kitne)\b", re.I)
OPS_INTENT_RE = re.compile(
    r"\b(interest|rate|roi|emi|fee|charges|apply|status|approved|disburs|kyc|pan|otp|login|nach|statement|support)\b",
    re.I,
)

# ... (Prototypes imported from module or defined here.
# For brevity in this fix, we assume they are imported or re-defined.

REASON_BOOSTS: List[Tuple[str, re.Pattern, float]] = [
    (
        "loan_terms_rates",
        re.compile(r"\b(interest rate|roi|rate|tenure|emi|processing fee|charges)\b", re.I),
        0.08,
    ),
    (
        "disbursal",
        re.compile(r"\b(approved|approval)\b.*\b(not received|not credited)\b", re.I),
        0.10,
    ),
    ("kyc_verification", re.compile(r"\b(kyc|pan|aadhaar|verification)\b", re.I), 0.10),
    ("otp_login_app_tech", re.compile(r"\b(otp|login|app)\b", re.I), 0.10),
    ("collections_harassment", re.compile(r"\b(harass|recovery agent)\b", re.I), 0.12),
    ("fraud_security", re.compile(r"\b(fraud|scam|unauthorized)\b", re.I), 0.12),
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = a / (np.linalg.norm(a) + 1e-12)
    b = b / (np.linalg.norm(b) + 1e-12)
    return float(np.dot(a, b))


def _sha256_json(obj: Any) -> str:
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _tone_override(text: str) -> Optional[Tuple[SentimentLabel, str]]:
    t = text
    has_pos = bool(POS_CUES_RE.search(t))
    has_prof = bool(PROFANITY_RE.search(t))
    has_neg = bool(NEG_EMOTION_RE.search(t))

    if FORECLOSE_RE.search(t) and QUESTION_RE.search(t) and not has_neg and not has_prof:
        return ("neutral", "foreclosure_inquiry")
    if has_pos and (has_neg or has_prof):
        return ("mixed", "pos+neg_emotion")
    if has_pos:
        return ("positive", "positive_cues")
    if has_neg or has_prof:
        return ("negative", "neg_emotion/profanity")
    return None


# =============================================================================
# Caching
# =============================================================================


class _ProtoCache:
    def _key(self, model: str, fp: str) -> str:
        return f"agent:router:proto:{model}:{fp}"

    async def load(self, model: str, fp: str) -> Optional[Dict[str, List[List[float]]]]:
        redis = await get_redis()
        payload = await redis.get(self._key(model, fp))
        if not payload:
            return None
        try:
            raw = json.loads(payload)
            if not isinstance(raw, dict):
                return None
            out: Dict[str, List[List[float]]] = {}
            for label, vecs in raw.items():
                if not isinstance(label, str) or not isinstance(vecs, list):
                    continue
                norm_vecs: List[List[float]] = []
                for vec in vecs:
                    if isinstance(vec, list):
                        norm_vecs.append([float(x) for x in vec])
                out[label] = norm_vecs
            return out
        except Exception:
            return None

    async def save(self, model: str, fp: str, data: Dict[str, List[List[float]]]) -> None:
        redis = await get_redis()
        # Redis can only store serialized strings. Ensure ndarray-like inputs are cast to plain lists.
        serializable = {
            label: [[float(x) for x in vec] for vec in vecs] for label, vecs in data.items()
        }
        await redis.set(
            self._key(model, fp),
            json.dumps(serializable, ensure_ascii=False),
            ex=30 * 24 * 60 * 60,
        )


@dataclass
class _ProtoBank:
    vectors: Dict[str, List[np.ndarray]]


# =============================================================================
# Embeddings Router
# =============================================================================


class EmbeddingsRouter:
    def __init__(self, embed_model: str):
        self.embed_model = embed_model
        self.cache = _ProtoCache()
        self._lock = asyncio.Lock()
        self._ready = False
        self._sent_bank: Optional[_ProtoBank] = None
        self._reason_bank: Optional[_ProtoBank] = None

    async def _build_bank(
        self, protos: Dict[str, List[str]], cache_prefix: str, api_key: str
    ) -> _ProtoBank:
        fp = _sha256_json({"prefix": cache_prefix, "protos": protos})
        cached = await self.cache.load(self.embed_model, fp)
        if cached is not None:
            out = {k: [np.asarray(v, dtype=np.float32) for v in vecs] for k, vecs in cached.items()}
            return _ProtoBank(vectors=out)

        # Generate fresh embeddings using Factory
        emb = get_embeddings(api_key=api_key, model=self.embed_model)

        flat = []
        labels = []
        for lab, texts in protos.items():
            for t in texts:
                labels.append(lab)
                flat.append(_norm(t))

        vecs = await emb.aembed_documents(flat)

        ser: Dict[str, List[List[float]]] = {}
        out2: Dict[str, List[np.ndarray]] = {}
        for lab, v in zip(labels, vecs, strict=False):
            ser.setdefault(lab, []).append(v)
            out2.setdefault(lab, []).append(np.asarray(v, dtype=np.float32))

        await self.cache.save(self.embed_model, fp, ser)
        return _ProtoBank(vectors=out2)

    async def ensure_ready(self, api_key: str) -> None:
        if self._ready:
            return
        async with self._lock:
            if self._ready:
                return
            self._sent_bank = await self._build_bank(SENTIMENT_PROTOTYPES, "sentiment_v1", api_key)
            self._reason_bank = await self._build_bank(REASON_PROTOTYPES, "reason_v1", api_key)
            self._ready = True

    async def _embed_query(self, text: str, api_key: str) -> np.ndarray:
        emb = get_embeddings(api_key=api_key, model=self.embed_model)
        return np.asarray(await emb.aembed_query(_norm(text)), dtype=np.float32)

    @staticmethod
    def _score_vector(bank: _ProtoBank, vector: np.ndarray) -> List[Tuple[str, float]]:
        scored = []
        for label, vecs in bank.vectors.items():
            scored.append((label, max(_cosine(vector, pv) for pv in vecs)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    async def classify_with_query_vector(
        self, text: str, api_key: str
    ) -> tuple[Dict[str, Any], np.ndarray]:
        await self.ensure_ready(api_key)

        query_vector = await self._embed_query(text, api_key)

        # Sentiment
        scored_s = self._score_vector(self._sent_bank, query_vector)  # type: ignore
        best_s, score_s = scored_s[0]

        label_s = best_s
        if score_s < NBFC_ROUTER_SENTIMENT_THRESHOLD:
            label_s = "unknown"
        elif len(scored_s) > 1 and (scored_s[0][1] - scored_s[1][1]) < NBFC_ROUTER_SENTIMENT_MARGIN:
            label_s = f"ambiguous:{scored_s[0][0]}|{scored_s[1][0]}"

        ov = _tone_override(text)
        if ov:
            label_s = ov[0]

        # Reason
        need_reason = bool(OPS_INTENT_RE.search(text)) or label_s in ("negative", "mixed")
        reason_res = None

        if need_reason:
            scored_r = self._score_vector(self._reason_bank, query_vector)  # type: ignore
            # Boosts
            bumps = {}
            for lab, pat, bump in REASON_BOOSTS:
                if pat.search(text):
                    bumps[lab] = max(bumps.get(lab, 0.0), bump)

            if bumps:
                scored_r = [(lab, sc + bumps.get(lab, 0.0)) for lab, sc in scored_r]
                scored_r.sort(key=lambda x: x[1], reverse=True)

            best_r, score_r = scored_r[0]
            label_r = best_r
            if score_r < NBFC_ROUTER_REASON_UNKNOWN_GATE:
                label_r = "unknown"

            reason_res = {
                "label": label_r,
                "score": float(score_r),
                "topk": [(lab, float(sc)) for lab, sc in scored_r[:3]],
            }

        return (
            {
                "sentiment": {"label": label_s, "score": float(score_s)},
                "reason": reason_res,
                "backend": "embeddings",
            },
            query_vector,
        )

    async def classify(self, text: str, api_key: str) -> Dict[str, Any]:
        result, _ = await self.classify_with_query_vector(text, api_key)
        return result


# =============================================================================
# LLM Router
# =============================================================================


class LLMRoute(BaseModel):
    sentiment: SentimentLabel
    reason: ReasonLabel
    confidence: float
    reason_confidence: float
    short_rationale: Optional[str]


class LLMRouter:
    def __init__(self, chat_model: str):
        self.chat_model = chat_model
        self.system = (
            "You are an NBFC chatbot router. Output JSON only.\n"
            "Sentiment: positive, negative, neutral, mixed, unknown.\n"
            "Reason: Choose from standard list or unknown."
        )

    async def classify(self, text: str, api_key: str) -> Dict[str, Any]:
        llm = get_llm(model_name=self.chat_model, openrouter_api_key=api_key, temperature=0.0)

        # Try structured output if available, else standard JSON parsing
        try:
            structured = llm.with_structured_output(LLMRoute)
            out = await structured.ainvoke([("system", self.system), ("human", text)])
        except Exception:
            try:
                # Fallback
                chain = llm | JsonOutputParser(pydantic_object=LLMRoute)
                out = await chain.ainvoke([("system", self.system), ("human", text)])
            except Exception as exc:
                return {
                    "sentiment": {"label": "unknown", "score": 0.0},
                    "reason": {
                        "label": "unknown",
                        "score": 0.0,
                        "meta": {"rationale": None, "error": str(exc)},
                    },
                    "backend": f"llm_{self.chat_model}",
                }

        def _as_float(value: Any) -> float:
            try:
                return float(value)
            except Exception:
                return 0.0

        # Convert to dict format (handle both BaseModel and dict) with safe defaults.
        try:
            if isinstance(out, dict):
                sentiment_label = str(out.get("sentiment", "unknown")).strip().lower()
                if sentiment_label not in VALID_SENTIMENT_LABELS:
                    sentiment_label = "unknown"

                reason_label = str(out.get("reason", "unknown")).strip().lower()
                if reason_label not in VALID_REASON_LABELS:
                    reason_label = "unknown"

                s = {"label": sentiment_label, "score": _as_float(out.get("confidence", 0.0))}
                r = {
                    "label": reason_label,
                    "score": _as_float(out.get("reason_confidence", 0.0)),
                    "meta": {"rationale": out.get("short_rationale")},
                }
            else:
                route: LLMRoute = out  # type: ignore
                s = {"label": route.sentiment, "score": float(route.confidence)}
                r = {
                    "label": route.reason,
                    "score": float(route.reason_confidence),
                    "meta": {"rationale": route.short_rationale},
                }
        except Exception as exc:
            return {
                "sentiment": {"label": "unknown", "score": 0.0},
                "reason": {
                    "label": "unknown",
                    "score": 0.0,
                    "meta": {"rationale": None, "error": str(exc)},
                },
                "backend": f"llm_{self.chat_model}",
            }

        return {"sentiment": s, "reason": r, "backend": f"llm_{self.chat_model}"}


# =============================================================================
# Service
# =============================================================================


class NBFCClassifierService:
    def __init__(self):
        self.emb = EmbeddingsRouter(NBFC_ROUTER_EMBED_MODEL)
        self.llm = LLMRouter(NBFC_ROUTER_CHAT_MODEL)
        self.answerability = QueryAnswerabilityClassifier(embed_model=NBFC_ROUTER_EMBED_MODEL)

    async def _safe_answerability(
        self,
        text: str,
        *,
        tools: Optional[List[Any]],
        openrouter_api_key: Optional[str],
        query_vector: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        if not NBFC_ROUTER_ANSWERABILITY_ENABLED:
            return {
                "disabled": True,
                "label": "disabled",
                "answerable": False,
                "confidence": 0.0,
                "recommended_path": "llm",
            }
        try:
            return await self.answerability.classify(
                text,
                tools or [],
                api_key=openrouter_api_key,
                query_vector=query_vector,
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "label": "unknown",
                "answerable": False,
                "confidence": 0.0,
                "recommended_path": "llm",
                "error": str(exc),
            }

    async def classify(
        self,
        text: str,
        openrouter_api_key: Optional[str] = None,
        mode: Optional[str] = None,
        tools: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        if not NBFC_ROUTER_ENABLED:
            return {"disabled": True, "backend": "disabled"}

        t = _norm(text)
        mode = mode or NBFC_ROUTER_MODE

        if not openrouter_api_key:
            answerability = await self._safe_answerability(
                t,
                tools=tools,
                openrouter_api_key=None,
            )
            return {
                "error": "OpenRouter Key required for router",
                "backend": "router_unavailable",
                "answerability": answerability,
            }

        # Embeddings First
        e, query_vector = await self.emb.classify_with_query_vector(t, openrouter_api_key)

        if mode == "embeddings":
            e["answerability"] = await self._safe_answerability(
                t,
                tools=tools,
                openrouter_api_key=openrouter_api_key,
                query_vector=query_vector,
            )
            return e

        # Force LLM check
        force_llm = bool(FORCE_LLM_RE.search(t))

        # Confidence check
        s_score = e["sentiment"]["score"]
        r_score = e["reason"]["score"] if e["reason"] else 1.0

        low_conf = (s_score < NBFC_ROUTER_FALLBACK_SENTIMENT_SCORE) or (
            r_score < NBFC_ROUTER_FALLBACK_REASON_SCORE
        )

        if mode == "llm" or force_llm or (mode == "hybrid" and low_conf):
            llm_result = await self.llm.classify(t, openrouter_api_key)
            llm_result["backend"] = (
                f"hybrid->{llm_result['backend']}" if mode == "hybrid" else llm_result["backend"]
            )
            result = llm_result
        else:
            result = e

        result["answerability"] = await self._safe_answerability(
            t,
            tools=tools,
            openrouter_api_key=openrouter_api_key,
            query_vector=query_vector,
        )
        return result

    async def compare(
        self,
        text: str,
        openrouter_api_key: Optional[str] = None,
        tools: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        t = _norm(text)
        if not openrouter_api_key:
            return {
                "error": "Key required",
                "answerability": await self._safe_answerability(
                    t,
                    tools=tools,
                    openrouter_api_key=None,
                ),
            }
        errors: Dict[str, str] = {}
        query_vector: Optional[np.ndarray] = None

        try:
            e, query_vector = await self.emb.classify_with_query_vector(t, openrouter_api_key)
        except Exception as exc:
            errors["embeddings"] = str(exc)
            e = {
                "sentiment": {"label": "unknown", "score": 0.0},
                "reason": {"label": "unknown", "score": 0.0},
                "backend": "embeddings",
                "error": str(exc),
            }

        try:
            llm_result = await self.llm.classify(t, openrouter_api_key)
        except Exception as exc:
            errors["llm"] = str(exc)
            llm_result = {
                "sentiment": {"label": "unknown", "score": 0.0},
                "reason": {"label": "unknown", "score": 0.0},
                "backend": f"llm_{self.llm.chat_model}",
                "error": str(exc),
            }

        result = {
            "embeddings": e,
            "llm": llm_result,
            "answerability": await self._safe_answerability(
                t,
                tools=tools,
                openrouter_api_key=openrouter_api_key,
                query_vector=query_vector,
            ),
        }
        if errors:
            result["errors"] = errors
        return result


nbfc_router_service = NBFCClassifierService()
