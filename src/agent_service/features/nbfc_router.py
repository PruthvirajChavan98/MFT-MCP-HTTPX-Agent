from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel

from src.agent_service.core.config import (  # Thresholds
    NBFC_ROUTER_CACHE_DIR,
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

# Enterprise Imports (Use Factory, not raw classes)
from src.agent_service.llm.client import get_embeddings, get_llm

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
# We'll re-define simpler versions to ensure standalone function)

from .prototypes_nbfc import REASON_PROTOTYPES, SENTIMENT_PROTOTYPES

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
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, model: str, fp: str) -> Path:
        safe_model = re.sub(r"[^a-zA-Z0-9_.-]+", "_", model)
        return self.root / f"router_proto_{safe_model}_{fp}.json"

    def load(self, model: str, fp: str) -> Optional[Dict[str, List[List[float]]]]:
        p = self._path(model, fp)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except:
            return None

    def save(self, model: str, fp: str, data: Dict[str, List[List[float]]]) -> None:
        p = self._path(model, fp)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@dataclass
class _ProtoBank:
    vectors: Dict[str, List[np.ndarray]]


# =============================================================================
# Embeddings Router
# =============================================================================


class EmbeddingsRouter:
    def __init__(self, embed_model: str):
        self.embed_model = embed_model
        self.cache = _ProtoCache(NBFC_ROUTER_CACHE_DIR)
        self._lock = asyncio.Lock()
        self._ready = False
        self._sent_bank: Optional[_ProtoBank] = None
        self._reason_bank: Optional[_ProtoBank] = None

    async def _build_bank(
        self, protos: Dict[str, List[str]], cache_prefix: str, api_key: str
    ) -> _ProtoBank:
        fp = _sha256_json({"prefix": cache_prefix, "protos": protos})
        cached = self.cache.load(self.embed_model, fp)
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

        self.cache.save(self.embed_model, fp, ser)
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

    async def _score(self, bank: _ProtoBank, text: str, api_key: str) -> List[Tuple[str, float]]:
        emb = get_embeddings(api_key=api_key, model=self.embed_model)
        v = np.asarray(await emb.aembed_query(_norm(text)), dtype=np.float32)
        scored = []
        for label, vecs in bank.vectors.items():
            scored.append((label, max(_cosine(v, pv) for pv in vecs)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    async def classify(self, text: str, api_key: str) -> Dict[str, Any]:
        await self.ensure_ready(api_key)

        # Sentiment
        scored_s = await self._score(self._sent_bank, text, api_key)  # type: ignore
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
            scored_r = await self._score(self._reason_bank, text, api_key)  # type: ignore
            # Boosts
            bumps = {}
            for lab, pat, bump in REASON_BOOSTS:
                if pat.search(text):
                    bumps[lab] = max(bumps.get(lab, 0.0), bump)

            if bumps:
                scored_r = [(l, s + bumps.get(l, 0.0)) for l, s in scored_r]
                scored_r.sort(key=lambda x: x[1], reverse=True)

            best_r, score_r = scored_r[0]
            label_r = best_r
            if score_r < NBFC_ROUTER_REASON_UNKNOWN_GATE:
                label_r = "unknown"

            reason_res = {
                "label": label_r,
                "score": float(score_r),
                "topk": [(l, float(s)) for l, s in scored_r[:3]],
            }

        return {
            "sentiment": {"label": label_s, "score": float(score_s)},
            "reason": reason_res,
            "backend": "embeddings",
        }


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
            # Fallback
            chain = llm | JsonOutputParser(pydantic_object=LLMRoute)
            out = await chain.ainvoke([("system", self.system), ("human", text)])

        # Convert to dict format (handle both BaseModel and dict)
        if isinstance(out, dict):
            s = {"label": out["sentiment"], "score": out["confidence"]}
            r = {
                "label": out["reason"],
                "score": out["reason_confidence"],
                "meta": {"rationale": out.get("short_rationale")},
            }
        else:
            route: LLMRoute = out  # type: ignore
            s = {"label": route.sentiment, "score": route.confidence}
            r = {
                "label": route.reason,
                "score": route.reason_confidence,
                "meta": {"rationale": route.short_rationale},
            }
        return {"sentiment": s, "reason": r, "backend": f"llm_{self.chat_model}"}


# =============================================================================
# Service
# =============================================================================


class NBFCClassifierService:
    def __init__(self):
        self.emb = EmbeddingsRouter(NBFC_ROUTER_EMBED_MODEL)
        self.llm = LLMRouter(NBFC_ROUTER_CHAT_MODEL)

    async def classify(
        self, text: str, openrouter_api_key: Optional[str] = None, mode: Optional[str] = None
    ) -> Dict[str, Any]:
        if not NBFC_ROUTER_ENABLED:
            return {"disabled": True, "backend": "disabled"}

        if not openrouter_api_key:
            return {"error": "OpenRouter Key required for router"}

        t = _norm(text)
        mode = mode or NBFC_ROUTER_MODE

        # Embeddings First
        e = await self.emb.classify(t, openrouter_api_key)

        if mode == "embeddings":
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
            l = await self.llm.classify(t, openrouter_api_key)
            l["backend"] = f"hybrid->{l['backend']}" if mode == "hybrid" else l["backend"]
            return l

        return e

    async def compare(self, text: str, openrouter_api_key: Optional[str] = None) -> Dict[str, Any]:
        if not openrouter_api_key:
            return {"error": "Key required"}
        e = await self.emb.classify(text, openrouter_api_key)
        l = await self.llm.classify(text, openrouter_api_key)
        return {"embeddings": e, "llm": l}


nbfc_router_service = NBFCClassifierService()
