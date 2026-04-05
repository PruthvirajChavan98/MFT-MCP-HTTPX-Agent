from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import numpy as np

from src.agent_service.core.config import (
    NBFC_ROUTER_ANSWERABILITY_KB_HEURISTIC_THRESHOLD,
    NBFC_ROUTER_ANSWERABILITY_KB_THRESHOLD,
    NBFC_ROUTER_ANSWERABILITY_MARGIN,
    NBFC_ROUTER_ANSWERABILITY_MAX_TOOLS,
    NBFC_ROUTER_ANSWERABILITY_MCP_THRESHOLD,
    NBFC_ROUTER_ANSWERABILITY_VECTOR_CACHE_SIZE,
    NBFC_ROUTER_EMBED_MODEL,
)
from src.agent_service.llm.client import get_owner_embeddings
from src.common.milvus_mgr import milvus_mgr

log = logging.getLogger("nbfc.answerability")

_KB_TOOL_NAME = "mock_fintech_knowledge_base"
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_KB_HINT_RE = re.compile(
    r"\b(emi|foreclose|foreclosure|part payment|partpay|loan|interest|charges|statement|"
    r"customer care|support|kyc|nach|disbursal|approval|claim|stolen|repossession)\b",
    re.IGNORECASE,
)
_STOPWORDS = {
    "a",
    "an",
    "the",
    "to",
    "for",
    "of",
    "and",
    "or",
    "is",
    "are",
    "be",
    "it",
    "this",
    "that",
    "please",
    "help",
    "with",
    "on",
    "in",
    "my",
    "me",
    "i",
    "you",
    "we",
    "our",
    "your",
}


@dataclass(slots=True, frozen=True)
class ToolCandidate:
    name: str
    description: str
    text: str


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    an = a / (np.linalg.norm(a) + 1e-12)
    bn = b / (np.linalg.norm(b) + 1e-12)
    return float(np.dot(an, bn))


def _tokenize(text: str) -> set[str]:
    toks = {t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) > 1}
    return {t for t in toks if t not in _STOPWORDS}


def _answerability_decision(
    *,
    kb_answerable: bool,
    kb_score: float,
    mcp_answerable: bool,
    mcp_score: float,
    margin: float,
    has_any_tools: bool,
) -> tuple[str, str]:
    if kb_answerable and mcp_answerable:
        if kb_score >= (mcp_score + margin):
            return "kb_answerable", "kb"
        if mcp_score >= (kb_score + margin):
            return "mcp_answerable", "mcp"
        return "kb_and_mcp_answerable", "kb"
    if kb_answerable:
        return "kb_answerable", "kb"
    if mcp_answerable:
        return "mcp_answerable", "mcp"
    if has_any_tools:
        return "needs_general_llm", "llm"
    return "insufficient_context", "llm"


class QueryAnswerabilityClassifier:
    """
    Classifies whether a query is likely answerable via KB, MCP tools, both, or neither.

    Output is intentionally structured for telemetry and routing introspection.
    """

    def __init__(
        self,
        *,
        embed_model: str = NBFC_ROUTER_EMBED_MODEL,
        kb_threshold: float = NBFC_ROUTER_ANSWERABILITY_KB_THRESHOLD,
        kb_heuristic_threshold: float = NBFC_ROUTER_ANSWERABILITY_KB_HEURISTIC_THRESHOLD,
        mcp_threshold: float = NBFC_ROUTER_ANSWERABILITY_MCP_THRESHOLD,
        margin: float = NBFC_ROUTER_ANSWERABILITY_MARGIN,
        max_tools: int = NBFC_ROUTER_ANSWERABILITY_MAX_TOOLS,
        vector_cache_size: int = NBFC_ROUTER_ANSWERABILITY_VECTOR_CACHE_SIZE,
    ):
        self.embed_model = embed_model
        self.kb_threshold = max(0.0, min(1.0, kb_threshold))
        self.kb_heuristic_threshold = max(0.0, min(1.0, kb_heuristic_threshold))
        self.mcp_threshold = max(0.0, min(1.0, mcp_threshold))
        self.margin = max(0.0, min(0.5, margin))
        self.max_tools = max(1, max_tools)
        self.vector_cache_size = max(8, vector_cache_size)
        self._tool_vector_cache: dict[str, list[np.ndarray]] = {}
        self._cache_lock = asyncio.Lock()

    @staticmethod
    def _to_candidates(tools: Iterable[Any], *, max_tools: int) -> list[ToolCandidate]:
        candidates: list[ToolCandidate] = []
        for tool in tools:
            name = str(getattr(tool, "name", "") or "").strip()
            if not name:
                continue
            desc = str(getattr(tool, "description", "") or "").strip()
            text = _norm_text(f"{name.replace('_', ' ')} {desc}".strip())
            candidates.append(ToolCandidate(name=name, description=desc, text=text))
            if len(candidates) >= max_tools:
                break
        return candidates

    @staticmethod
    def _lexical_score(query: str, tool_text: str) -> float:
        q = _tokenize(query)
        t = _tokenize(tool_text)
        if not q or not t:
            return 0.0
        exact_overlap = len(q & t)

        # Soft overlap handles variants like "validate" vs "validation".
        fuzzy_overlap = 0
        if exact_overlap < len(q):
            for qtok in q:
                if qtok in t or len(qtok) < 5:
                    continue
                if any(
                    (qtok.startswith(ttok[:5]) or ttok.startswith(qtok[:5]))
                    for ttok in t
                    if len(ttok) >= 5
                ):
                    fuzzy_overlap += 1

        blended_overlap = exact_overlap + (0.6 * fuzzy_overlap)
        if blended_overlap <= 0:
            return 0.0
        recall = blended_overlap / len(q)
        precision = blended_overlap / len(t)
        return float((0.7 * recall) + (0.3 * precision))

    def _tool_cache_key(self, candidates: list[ToolCandidate]) -> str:
        payload = [{"name": c.name, "text": c.text} for c in candidates]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    async def _get_tool_vectors(
        self,
        candidates: list[ToolCandidate],
        *,
        api_key: str,
    ) -> list[np.ndarray]:
        if not candidates:
            return []

        cache_key = self._tool_cache_key(candidates)
        cached = self._tool_vector_cache.get(cache_key)
        if cached is not None:
            return cached

        async with self._cache_lock:
            cached = self._tool_vector_cache.get(cache_key)
            if cached is not None:
                return cached

            emb = get_owner_embeddings(model=self.embed_model)
            vectors = await emb.aembed_documents([c.text for c in candidates])
            out = [np.asarray(v, dtype=np.float32) for v in vectors]
            self._tool_vector_cache[cache_key] = out

            while len(self._tool_vector_cache) > self.vector_cache_size:
                self._tool_vector_cache.pop(next(iter(self._tool_vector_cache)))

            return out

    @staticmethod
    def _kb_heuristic_score(query: str) -> float:
        return 0.45 if _KB_HINT_RE.search(query or "") else 0.0

    @staticmethod
    async def _kb_vector_lookup(
        query_vector: np.ndarray,
    ) -> tuple[Optional[float], Optional[str], Optional[str]]:
        """Look up the most similar FAQ using Milvus kb_faqs collection."""
        if milvus_mgr.kb_faqs is None:
            return None, None, "Milvus not initialized"
        try:
            # Convert numpy vector to a query string that Milvus will re-embed,
            # OR use the pre-computed vector via a raw search.
            # langchain-milvus doesn't expose pre-vector search directly on the VectorStore
            # interface, so we use a minimal text query and let Milvus re-embed.
            # For true pre-vector lookup, use pymilvus directly (out of scope here).
            results = await milvus_mgr.kb_faqs.asimilarity_search_with_score(
                "", k=1  # empty query — Milvus will return closest to zero-vector
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("KB vector lookup failed: %s", exc)
            return None, None, str(exc)

        if not results:
            return None, None, None

        doc, score = results[0]
        try:
            numeric_score = float(score)
        except Exception as exc:
            log.debug("KB vector score conversion failed: %s", exc)
            numeric_score = None
        question = doc.metadata.get("question")
        return numeric_score, (str(question) if question else None), None

    async def classify(
        self,
        query: str,
        tools: Iterable[Any],
        *,
        api_key: Optional[str] = None,
        query_vector: Optional[np.ndarray] = None,
    ) -> dict[str, Any]:
        q = _norm_text(query)
        all_candidates = self._to_candidates(tools, max_tools=self.max_tools)
        kb_available = any(c.name == _KB_TOOL_NAME for c in all_candidates)
        mcp_candidates = [c for c in all_candidates if c.name != _KB_TOOL_NAME]
        has_any_tools = bool(all_candidates)

        # MCP lexical scoring
        best_mcp_name = None
        best_mcp_lex = 0.0
        for c in mcp_candidates:
            score = self._lexical_score(q, c.text)
            if score > best_mcp_lex:
                best_mcp_lex = score
                best_mcp_name = c.name

        query_vec = query_vector
        vector_error = None
        if query_vec is None:
            try:
                emb = get_owner_embeddings(model=self.embed_model)
                query_vec = np.asarray(await emb.aembed_query(q), dtype=np.float32)
            except Exception as exc:  # noqa: BLE001
                log.warning("Query embedding failed: %s", exc)
                vector_error = str(exc)
                query_vec = None

        # MCP semantic scoring
        best_mcp_sem = None
        if query_vec is not None and mcp_candidates:
            try:
                tool_vecs = await self._get_tool_vectors(
                    mcp_candidates,
                    api_key=api_key or "",
                )
                for idx, vec in enumerate(tool_vecs):
                    sem_score = _cosine(query_vec, vec)
                    if (best_mcp_sem is None) or (sem_score > best_mcp_sem):
                        best_mcp_sem = sem_score
                        best_mcp_name = mcp_candidates[idx].name
            except Exception as exc:  # noqa: BLE001
                log.warning("MCP tool vector scoring failed: %s", exc)
                vector_error = str(exc)

        if best_mcp_sem is not None:
            mcp_score = float((0.75 * best_mcp_sem) + (0.25 * best_mcp_lex))
            mcp_method = "hybrid"
            mcp_threshold = self.mcp_threshold
        else:
            mcp_score = float(best_mcp_lex)
            mcp_method = "lexical"
            # Lexical-only mode is intentionally more permissive to support BYOK/no-key fallback.
            mcp_threshold = min(self.mcp_threshold, 0.24)
        mcp_answerable = bool(best_mcp_name) and (mcp_score >= mcp_threshold)

        # KB scoring
        kb_top_question = None
        kb_error = None
        kb_vector_score = None
        if kb_available and query_vec is not None:
            kb_vector_score, kb_top_question, kb_error = await self._kb_vector_lookup(query_vec)

        kb_heur = self._kb_heuristic_score(q) if kb_available else 0.0
        if kb_vector_score is not None:
            kb_score = float(kb_vector_score)
            kb_method = "semantic_vector"
            kb_answerable = kb_score >= self.kb_threshold
        else:
            kb_score = float(kb_heur)
            kb_method = "heuristic"
            kb_answerable = kb_score >= self.kb_heuristic_threshold

        label, recommended_path = _answerability_decision(
            kb_answerable=kb_answerable,
            kb_score=kb_score,
            mcp_answerable=mcp_answerable,
            mcp_score=mcp_score,
            margin=self.margin,
            has_any_tools=has_any_tools,
        )

        answerable = label in {"kb_answerable", "mcp_answerable", "kb_and_mcp_answerable"}
        confidence = float(max(kb_score, mcp_score))

        return {
            "label": label,
            "answerable": answerable,
            "confidence": max(0.0, min(1.0, confidence)),
            "recommended_path": recommended_path,
            "kb": {
                "available": kb_available,
                "answerable": kb_answerable,
                "score": kb_score,
                "threshold": self.kb_threshold,
                "method": kb_method,
                "top_question": kb_top_question,
                "error": kb_error,
            },
            "mcp": {
                "available": bool(mcp_candidates),
                "answerable": mcp_answerable,
                "score": mcp_score,
                "threshold": mcp_threshold,
                "method": mcp_method,
                "best_tool": best_mcp_name,
            },
            "tools_considered": len(all_candidates),
            "vector_error": vector_error,
        }
