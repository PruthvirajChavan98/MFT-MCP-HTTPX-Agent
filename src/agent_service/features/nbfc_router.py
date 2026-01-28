from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from langchain_deepseek import ChatDeepSeek
from langchain_openai import OpenAIEmbeddings


# =============================================================================
# Labels
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


# =============================================================================
# Config (env-driven, stable)
# =============================================================================

OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
OPENROUTER_SITE_URL = (os.getenv("OPENROUTER_SITE_URL") or "").strip() or None
OPENROUTER_APP_TITLE = (os.getenv("OPENROUTER_APP_TITLE") or "").strip() or None

NBFC_ROUTER_ENABLED = os.getenv("NBFC_ROUTER_ENABLED", "true").lower() in ("1", "true", "yes", "y")
NBFC_ROUTER_MODE = os.getenv("NBFC_ROUTER_MODE", "hybrid").strip().lower()  # embeddings|llm|hybrid|compare
NBFC_ROUTER_CHAT_MODEL = os.getenv("NBFC_ROUTER_CHAT_MODEL", "z-ai/glm-4.7").strip()
NBFC_ROUTER_EMBED_MODEL = os.getenv("NBFC_ROUTER_EMBED_MODEL", "openai/text-embedding-3-small").strip()
NBFC_ROUTER_CACHE_DIR = os.getenv("NBFC_ROUTER_CACHE_DIR", ".cache_nbfc_router").strip()

# thresholds tuned for openai/text-embedding-3-small scale (adjust with eval later)
SENTIMENT_THRESHOLD = float(os.getenv("NBFC_ROUTER_SENTIMENT_THRESHOLD", "0.26"))
SENTIMENT_MARGIN = float(os.getenv("NBFC_ROUTER_SENTIMENT_MARGIN", "0.03"))
REASON_UNKNOWN_GATE = float(os.getenv("NBFC_ROUTER_REASON_UNKNOWN_GATE", "0.30"))
REASON_MARGIN = float(os.getenv("NBFC_ROUTER_REASON_MARGIN", "0.03"))

# when embeddings are low-confidence -> call LLM
FALLBACK_SENTIMENT_SCORE = float(os.getenv("NBFC_ROUTER_FALLBACK_SENTIMENT_SCORE", "0.33"))
FALLBACK_REASON_SCORE = float(os.getenv("NBFC_ROUTER_FALLBACK_REASON_SCORE", "0.60"))

# always call LLM for these (high-stakes)
FORCE_LLM_RE = re.compile(r"\b(fraud|unauthorized|harass|harassment|threat|abuse)\b", re.I)


def _headers() -> Optional[Dict[str, str]]:
    h: Dict[str, str] = {}
    if OPENROUTER_SITE_URL:
        h["HTTP-Referer"] = OPENROUTER_SITE_URL
    if OPENROUTER_APP_TITLE:
        h["X-Title"] = OPENROUTER_APP_TITLE
    return h or None


def _norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = a / (np.linalg.norm(a) + 1e-12)
    b = b / (np.linalg.norm(b) + 1e-12)
    return float(np.dot(a, b))


def _sha256_json(obj: Any) -> str:
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# =============================================================================
# Tone != "has an issue"
# sentiment = emotional tone
# =============================================================================

PROFANITY_RE = re.compile(
    r"\b(fuck|fucking|wtf|shit|madarchod|bhenchod|bc|mc|chutiya|gandu)\b",
    re.IGNORECASE,
)

POS_CUES_RE = re.compile(
    r"\b(thanks|thank you|thx|love|loved|awesome|amazing|great|super smooth|"
    r"mast|bhadiya|badiya|resolved|sorted|helpful|quick|fast)\b|"
    r"(❤️|😍|🔥|💯)",
    re.IGNORECASE,
)

NEG_EMOTION_RE = re.compile(
    r"\b("
    r"worst|pathetic|unacceptable|frustrat(ed|ing)|pissed|angry|annoyed|"
    r"harass|harassment|threat|abuse|stop calling|too many calls|"
    r"scam|fraud|unauthorized|hacked|"
    r"refund my money|refund.*(asap|now|immediately)|"
    r"charged twice|double charged|overcharged"
    r")\b",
    re.IGNORECASE,
)

FORECLOSE_RE = re.compile(r"\b(foreclose|foreclosure|preclose|pre-closure|part payment|partpay|noc)\b", re.I)
QUESTION_RE = re.compile(r"(\?|how much|how to|charges|fee|process|kya|kaise|kitna|kitne)\b", re.I)

OPS_INTENT_RE = re.compile(
    r"\b("
    r"interest rate|roi|rate|tenure|emi|processing fee|charges|fee|"
    r"apply|application|loan status|approved|approval|rejected|declined|"
    r"disbursal|disburse|credited|not credited|not received|money not received|amount not received|"
    r"kyc|pan|aadhaar|verification|mismatch|document|"
    r"otp|login|app|crash|error|not working|"
    r"nach|autodebit|mandate|bounce|"
    r"foreclose|foreclosure|preclose|part payment|partpay|noc|"
    r"statement|receipt|certificate|schedule|"
    r"support|customer care|ticket|complaint|escalation|"
    r"recovery|collections|overdue"
    r")\b",
    re.IGNORECASE,
)


def _tone_override(text: str) -> Optional[Tuple[SentimentLabel, str]]:
    t = text
    has_pos = bool(POS_CUES_RE.search(t))
    has_prof = bool(PROFANITY_RE.search(t))
    has_neg = bool(NEG_EMOTION_RE.search(t))

    if FORECLOSE_RE.search(t) and QUESTION_RE.search(t) and not has_neg and not has_prof:
        return ("neutral", "foreclosure_inquiry")

    if has_pos and (has_neg or has_prof):
        return ("mixed", "pos+neg_emotion")

    if has_pos and not (has_neg or has_prof):
        return ("positive", "positive_cues")

    if has_neg or has_prof:
        why = []
        if has_prof:
            why.append("profanity")
        if has_neg:
            why.append("neg_emotion")
        return ("negative", "+".join(why))

    return None


# =============================================================================
# Prototypes
# =============================================================================

SENTIMENT_PROTOS: Dict[str, List[str]] = {
    "positive": [
        "Thanks! Super smooth experience, love the service ❤️",
        "Great support, very helpful",
        "Awesome experience, everything went smooth 🔥",
        "bhai mast service, full satisfied 💯",
    ],
    "neutral": [
        "KYC stuck, PAN name mismatch, what to do?",
        "Disbursal kab hoga? approved but money not received",
        "OTP is not coming, app keeps failing on login",
        "What is the interest rate for 24 months?",
        "How to download loan statement?",
        "How to check loan status?",
    ],
    "negative": [
        "Bro wtf, loan still not approved since 5 days",
        "This is unacceptable, refund my money ASAP",
        "Stop calling me, harassment by recovery agent",
        "Worst experience, totally disappointed 😡",
        "Charged twice, overcharged, fix it now",
    ],
}

REASON_PROTOS: Dict[str, List[str]] = {
    "lead_intent_new_loan": [
        "I want a new loan, how to apply, eligibility, required documents",
        "apply now, interested in loan, want to proceed",
        "loan chahiye, apply karna hai",
    ],
    "eligibility_offer": [
        "check eligibility, pre-approved offer, limit, income criteria",
        "why am I not eligible, offer not showing",
    ],
    "loan_terms_rates": [
        "what is the interest rate, ROI, tenure, EMI, processing fee, charges",
        "interest rate for 24 months, EMI calculation",
        "rate kitna hai, tenure options, EMI kitni banegi",
    ],
    "kyc_verification": [
        "kyc stuck, verification failed, documents rejected, selfie failed",
        "PAN/Aadhaar mismatch, address proof issue",
        "pan name mismatch, aadhaar mismatch",
    ],
    "otp_login_app_tech": [
        "otp not coming, login issue, app crash, technical error",
        "app not working, server error, cannot verify otp",
    ],
    "application_status_approval": [
        "loan application status, approval pending, rejected/declined",
        "when will approval come, still pending",
        "why rejected, underwriting pending",
    ],
    "disbursal": [
        "disbursal delayed, amount not credited, disbursement pending",
        "approved but money not received, amount not received after approval",
        "disbursal kab hoga, credit nahi hua",
    ],
    "emi_payment_reflecting": [
        "emi paid but not updated, payment not reflecting, receipt issue",
        "UPI paid but not showing, paid but still shows overdue",
    ],
    "nach_autodebit_bounce": [
        "NACH auto-debit failed, bounce, mandate issue, bank debit failed",
        "autopay setup, mandate not active",
    ],
    "charges_fees_penalty": [
        "processing fee, late fee, penalty, hidden charges, extra charge",
        "why penalty applied, charges are wrong",
    ],
    "foreclosure_partpayment": [
        "foreclosure, part payment, pre-closure charges, NOC",
        "how to close loan early, settlement amount",
    ],
    "statement_receipt": [
        "download loan statement, repayment schedule, interest certificate",
        "need receipt for EMI, transaction receipt",
    ],
    "collections_harassment": [
        "too many collection calls, harassment, abusive agent",
        "recovery team threatening, stop calling",
    ],
    "fraud_security": [
        "unauthorized transaction, scam, suspicious activity, account hacked",
        "someone used my details, identity misuse",
    ],
    "customer_support": [
        "customer care not responding, ticket unresolved, escalation",
        "need to talk to agent, callback request",
    ],
}

REASON_BOOSTS: List[Tuple[str, re.Pattern, float]] = [
    ("loan_terms_rates", re.compile(r"\b(interest rate|roi|rate|tenure|emi|processing fee|charges)\b", re.I), 0.08),
    ("disbursal", re.compile(r"\b(approved|approval)\b.*\b(not received|not credited|money not received|amount not received|credit nahi)\b", re.I), 0.10),
    ("kyc_verification", re.compile(r"\b(kyc|pan|aadhaar|verification)\b.*\b(stuck|failed|mismatch|rejected)\b", re.I), 0.10),
    ("otp_login_app_tech", re.compile(r"\b(otp|login|app)\b.*\b(not coming|failed|error|crash|not working)\b", re.I), 0.10),
    ("collections_harassment", re.compile(r"\b(harass|harassment|threat|abuse|too many calls|recovery agent|collection)\b", re.I), 0.12),
    ("fraud_security", re.compile(r"\b(fraud|scam|unauthorized|hacked|suspicious)\b", re.I), 0.12),
]


# =============================================================================
# Cache prototype embeddings to disk (fast start; avoids re-embedding)
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
        except Exception:
            return None

    def save(self, model: str, fp: str, data: Dict[str, List[List[float]]]) -> None:
        p = self._path(model, fp)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# =============================================================================
# Embeddings Router
# =============================================================================

@dataclass
class _ProtoBank:
    vectors: Dict[str, List[np.ndarray]]


class EmbeddingsRouter:
    def __init__(self, api_key: str, embed_model: str):
        self.api_key = api_key
        self.embed_model = embed_model
        self.emb = OpenAIEmbeddings(
            model=embed_model,
            api_key=api_key,  # type: ignore
            base_url=OPENROUTER_BASE_URL,
            default_headers=_headers(),
            check_embedding_ctx_length=False,
        )
        self.cache = _ProtoCache(NBFC_ROUTER_CACHE_DIR)
        self._lock = asyncio.Lock()
        self._ready = False
        self._sent_bank: Optional[_ProtoBank] = None
        self._reason_bank: Optional[_ProtoBank] = None

    async def _build_bank(self, protos: Dict[str, List[str]], cache_prefix: str) -> _ProtoBank:
        fp = _sha256_json({"prefix": cache_prefix, "protos": protos})
        cached = self.cache.load(self.embed_model, fp)
        if cached is not None:
            out: Dict[str, List[np.ndarray]] = {}
            for label, vecs in cached.items():
                out[label] = [np.asarray(v, dtype=np.float32) for v in vecs]
            return _ProtoBank(vectors=out)

        # batch embeddings (best practice)
        labels: List[str] = []
        flat: List[str] = []
        for lab, texts in protos.items():
            for t in texts:
                labels.append(lab)
                flat.append(_norm(t))

        vecs = await self.emb.aembed_documents(flat)
        ser: Dict[str, List[List[float]]] = {}
        out2: Dict[str, List[np.ndarray]] = {}
        for lab, v in zip(labels, vecs):
            ser.setdefault(lab, []).append(v)
            out2.setdefault(lab, []).append(np.asarray(v, dtype=np.float32))

        self.cache.save(self.embed_model, fp, ser)
        return _ProtoBank(vectors=out2)

    async def ensure_ready(self) -> None:
        if self._ready:
            return
        async with self._lock:
            if self._ready:
                return
            self._sent_bank = await self._build_bank(SENTIMENT_PROTOS, "sentiment_tone_v1")
            self._reason_bank = await self._build_bank(REASON_PROTOS, "reason_v1")
            self._ready = True

    async def _score(self, bank: _ProtoBank, text: str) -> List[Tuple[str, float]]:
        v = np.asarray(await self.emb.aembed_query(_norm(text)), dtype=np.float32)
        scored: List[Tuple[str, float]] = []
        for label, vecs in bank.vectors.items():
            scored.append((label, max(_cosine(v, pv) for pv in vecs)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    async def classify_sentiment(self, text: str) -> Dict[str, Any]:
        await self.ensure_ready()
        assert self._sent_bank is not None

        scored = await self._score(self._sent_bank, text)
        best_label, best_score = scored[0]

        label: str = best_label
        if best_score < SENTIMENT_THRESHOLD:
            label = "unknown"
        elif len(scored) > 1 and (scored[0][1] - scored[1][1]) < SENTIMENT_MARGIN:
            label = f"ambiguous:{scored[0][0]}|{scored[1][0]}"

        overridden = False
        override_reason = None

        # override only when low confidence / ambiguous
        if label == "unknown" or label.startswith("ambiguous:") or best_score < FALLBACK_SENTIMENT_SCORE:
            ov = _tone_override(text)
            if ov:
                label, override_reason = ov
                overridden = True

        return {
            "label": label,
            "score": float(best_score),
            "topk": [(a, float(b)) for a, b in scored[:3]],
            "overridden": overridden,
            "override_reason": override_reason,
        }

    async def classify_reason(self, text: str) -> Dict[str, Any]:
        await self.ensure_ready()
        assert self._reason_bank is not None

        scored = await self._score(self._reason_bank, text)

        # apply lexical boosts
        bumps: Dict[str, float] = {}
        for lab, pat, bump in REASON_BOOSTS:
            if pat.search(text):
                bumps[lab] = max(bumps.get(lab, 0.0), bump)

        if bumps:
            scored = [(lab, sc + bumps.get(lab, 0.0)) for (lab, sc) in scored]
            scored.sort(key=lambda x: x[1], reverse=True)

        best_label, best_score = scored[0]
        label: str = best_label

        if best_score < REASON_UNKNOWN_GATE:
            label = "unknown"
        elif len(scored) > 1 and (scored[0][1] - scored[1][1]) < REASON_MARGIN:
            label = f"ambiguous:{scored[0][0]}|{scored[1][0]}"

        return {
            "label": label,
            "score": float(best_score),
            "topk": [(a, float(b)) for a, b in scored[:3]],
        }

    async def classify(self, text: str) -> Dict[str, Any]:
        t = _norm(text)
        s = await self.classify_sentiment(t)

        need_reason = bool(OPS_INTENT_RE.search(t)) or s["label"] in ("negative", "mixed") or ("negative" in s["label"] if isinstance(s["label"], str) and s["label"].startswith("ambiguous:") else False)

        r = None
        if need_reason:
            r = await self.classify_reason(t)

        # pure praise -> no reason
        if s["label"] == "positive" and not OPS_INTENT_RE.search(t):
            r = None

        return {"sentiment": s, "reason": r, "backend": "embeddings"}


# =============================================================================
# LLM Router (GLM-4.7 via OpenRouter using ChatDeepSeek)
# =============================================================================

class LLMRoute(BaseModel):
    sentiment: SentimentLabel
    reason: ReasonLabel
    confidence: float = Field(ge=0.0, le=1.0)
    reason_confidence: float = Field(ge=0.0, le=1.0)
    short_rationale: Optional[str] = Field(default=None, description="One short sentence. No chain-of-thought.")


class LLMRouter:
    def __init__(self, api_key: str, chat_model: str):
        self.api_key = api_key
        self.chat_model = chat_model
        self.llm = ChatDeepSeek(
            model=chat_model,
            api_key=api_key,  # type: ignore
            api_base=OPENROUTER_BASE_URL,
            default_headers=_headers(),
            temperature=0,
            streaming=False,
            max_retries=2,
            timeout=30,
        )
        # Try structured output; we will fallback to manual JSON parsing if provider rejects.
        self.structured = self.llm.with_structured_output(LLMRoute)

        self.system = (
            "You are an NBFC chatbot router.\n"
            "Output MUST be valid JSON matching the schema.\n\n"
            "Sentiment is EMOTIONAL TONE (not 'has an issue'):\n"
            "- positive: praise/thanks\n"
            "- negative: anger/frustration/harassment/fraud/demanding tone\n"
            "- neutral: informational or problem report without emotional language\n"
            "- mixed: praise + complaint\n"
            "- unknown if unclear\n\n"
            "Reason should be the best ops queue when relevant; if message is pure praise with no request, use reason='unknown' and low reason_confidence.\n"
            "No markdown."
        )

    @staticmethod
    def _extract_json(s: str) -> dict:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if not m:
            raise ValueError("No JSON object found")
        return json.loads(m.group(0))

    async def classify(self, text: str) -> Dict[str, Any]:
        t = _norm(text)
        try:
            out: LLMRoute = await self.structured.ainvoke([("system", self.system), ("human", t)])
        except Exception:
            raw = await self.llm.ainvoke([("system", self.system), ("human", t)])
            payload = self._extract_json(getattr(raw, "content", str(raw)))
            out = LLMRoute(**payload)

        s = {"label": out.sentiment, "score": float(out.confidence), "topk": [], "overridden": False, "override_reason": None}
        r = {"label": out.reason, "score": float(out.reason_confidence), "topk": [], "meta": {"rationale": out.short_rationale}}

        if out.sentiment == "positive" and not OPS_INTENT_RE.search(t):
            r = None

        return {"sentiment": s, "reason": r, "backend": "llm_glm-4.7"}


# =============================================================================
# Hybrid Router (permanent: embeddings first, LLM on demand)
# =============================================================================

class HybridRouter:
    def __init__(self, emb: EmbeddingsRouter, llm: LLMRouter):
        self.emb = emb
        self.llm = llm

    async def classify(self, text: str) -> Dict[str, Any]:
        t = _norm(text)
        e = await self.emb.classify(t)

        # force LLM
        if FORCE_LLM_RE.search(t):
            l = await self.llm.classify(t)
            l["backend"] = "hybrid->llm_glm-4.7"
            return l

        s = e["sentiment"]
        r = e["reason"]

        need_llm = False
        if s["label"] == "unknown" or (isinstance(s["label"], str) and s["label"].startswith("ambiguous:")) or float(s["score"]) < FALLBACK_SENTIMENT_SCORE:
            need_llm = True

        expect_reason = bool(OPS_INTENT_RE.search(t)) or s["label"] in ("negative", "mixed")
        if expect_reason:
            if r is None:
                need_llm = True
            else:
                if r["label"] == "unknown" or (isinstance(r["label"], str) and r["label"].startswith("ambiguous:")) or float(r["score"]) < FALLBACK_REASON_SCORE:
                    need_llm = True

        if not need_llm:
            e["backend"] = "hybrid->embeddings"
            return e

        l = await self.llm.classify(t)
        l["backend"] = "hybrid->llm_glm-4.7"
        return l


# =============================================================================
# Public service
# =============================================================================

class NBFCClassifierService:
    def __init__(self):
        self.enabled = NBFC_ROUTER_ENABLED

    def _require_key(self, openrouter_api_key: Optional[str]) -> str:
        key = (openrouter_api_key or os.getenv("OPENROUTER_API_KEY") or "").strip()
        if not key:
            raise ValueError("OPENROUTER_API_KEY missing (router requires OpenRouter key)")
        return key

    async def classify(self, text: str, openrouter_api_key: Optional[str] = None, mode: Optional[str] = None) -> Dict[str, Any]:
        if not self.enabled:
            return {"disabled": True, "backend": "disabled"}

        key = self._require_key(openrouter_api_key)
        mode2 = (mode or NBFC_ROUTER_MODE).strip().lower()

        emb = EmbeddingsRouter(api_key=key, embed_model=NBFC_ROUTER_EMBED_MODEL)
        llm = LLMRouter(api_key=key, chat_model=NBFC_ROUTER_CHAT_MODEL)
        hyb = HybridRouter(emb, llm)

        if mode2 == "embeddings":
            return await emb.classify(text)
        if mode2 == "llm":
            return await llm.classify(text)
        if mode2 == "compare":
            e = await emb.classify(text)
            l = await llm.classify(text)
            return {"backend": "compare", "embeddings": e, "llm": l}
        # default hybrid
        return await hyb.classify(text)

    async def compare(self, text: str, openrouter_api_key: Optional[str] = None) -> Dict[str, Any]:
        return await self.classify(text, openrouter_api_key=openrouter_api_key, mode="compare")


nbfc_router_service = NBFCClassifierService()
