from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
from typing import Any

from src.agent_service.core.config import (
    INLINE_GUARD_ENABLED,
    INLINE_GUARD_GROQ_TIMEOUT_MS,
    INLINE_GUARD_PROMPT_GUARD_MODEL,
    INLINE_GUARD_PROTOTYPE_CACHE_TTL_SECONDS,
    INLINE_GUARD_REDIS_KEY_PREFIX,
    INLINE_GUARD_SIMILARITY_THRESHOLD,
    INLINE_GUARD_TOTAL_TIMEOUT_MS,
    INLINE_GUARD_VECTOR_TIMEOUT_MS,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_EMBED_MODEL_DEFAULT,
)
from src.agent_service.core.http_client import get_http_client
from src.agent_service.core.session_utils import get_redis
from src.agent_service.llm.client import get_embeddings

log = logging.getLogger(__name__)

SECURITY_PROTOTYPES: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore safety policy",
    "system prompt leak",
    "reveal hidden policies",
    "how to jailbreak",
    "bypass guardrails",
    "developer mode override",
    "give competitor recommendation",
    "what are your internal tools",
    "act as unrestricted model",
    "return admin secrets",
)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _to_float_vector(raw: Any) -> list[float]:
    if not isinstance(raw, list):
        raise ValueError("Embedding vector must be a list.")
    return [float(item) for item in raw]


def _prototype_cache_key() -> str:
    digest = hashlib.sha256("||".join(SECURITY_PROTOTYPES).encode("utf-8")).hexdigest()[:16]
    return f"{INLINE_GUARD_REDIS_KEY_PREFIX}:prototypes:{OPENROUTER_EMBED_MODEL_DEFAULT}:{digest}"


def _extract_guard_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for chunk in content:
                if isinstance(chunk, str):
                    parts.append(chunk)
                elif isinstance(chunk, dict):
                    text = chunk.get("text")
                    if text:
                        parts.append(str(text))
            return "".join(parts)
    return ""


async def _get_or_build_prototype_vectors() -> list[list[float]]:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is required for inline vector guard.")

    redis = await get_redis()
    key = _prototype_cache_key()
    cached = await redis.get(key)
    if cached:
        parsed = json.loads(cached)
        if isinstance(parsed, list):
            return [_to_float_vector(item) for item in parsed]

    embedder = get_embeddings(
        api_key=OPENROUTER_API_KEY,
        model=OPENROUTER_EMBED_MODEL_DEFAULT,
        base_url=OPENROUTER_BASE_URL,
    )
    vectors_raw = await asyncio.to_thread(embedder.embed_documents, list(SECURITY_PROTOTYPES))
    vectors = [_to_float_vector(vector) for vector in vectors_raw]
    await redis.set(key, json.dumps(vectors), ex=INLINE_GUARD_PROTOTYPE_CACHE_TTL_SECONDS)
    return vectors


async def _vector_rail_check(prompt: str) -> bool:
    if not OPENROUTER_API_KEY:
        log.warning("Inline guard vector rail unavailable: OPENROUTER_API_KEY missing.")
        return False

    embedder = get_embeddings(
        api_key=OPENROUTER_API_KEY,
        model=OPENROUTER_EMBED_MODEL_DEFAULT,
        base_url=OPENROUTER_BASE_URL,
    )
    prompt_vector = _to_float_vector(await asyncio.to_thread(embedder.embed_query, prompt))
    prototype_vectors = await _get_or_build_prototype_vectors()
    similarity = max(
        (_cosine_similarity(prompt_vector, vector) for vector in prototype_vectors), default=0.0
    )
    return similarity <= INLINE_GUARD_SIMILARITY_THRESHOLD


async def _openrouter_prompt_guard_check(prompt: str) -> bool:
    if not OPENROUTER_API_KEY:
        log.warning("Inline guard prompt rail unavailable: OPENROUTER_API_KEY missing.")
        return False

    client = await get_http_client()
    payload: dict[str, Any] = {
        "model": INLINE_GUARD_PROMPT_GUARD_MODEL,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    response = await client.post(
        f"{OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
        json=payload,
        headers=headers,
    )
    response.raise_for_status()
    body = response.json()
    text = _extract_guard_text(body).strip().lower()
    if not text:
        return False
    unsafe_tokens = ("unsafe", "injection", "jailbreak")
    return not any(token in text for token in unsafe_tokens)


async def _with_timeout(coro: Any, timeout_seconds: float) -> Any:
    async with asyncio.timeout(timeout_seconds):
        return await coro


async def evaluate_prompt_safety(prompt: str) -> bool:
    """
    Dual inline safety gate for prompt injection/jailbreak detection.

    Fail-closed by default: any timeout/error/unknown state returns False.
    """
    if not INLINE_GUARD_ENABLED:
        return True

    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        log.warning("Inline guard blocked empty prompt.")
        return False

    vector_timeout = max(0.01, INLINE_GUARD_VECTOR_TIMEOUT_MS / 1000)
    provider_timeout = max(0.01, INLINE_GUARD_GROQ_TIMEOUT_MS / 1000)
    total_timeout = max(0.05, INLINE_GUARD_TOTAL_TIMEOUT_MS / 1000)

    try:
        async with asyncio.timeout(total_timeout):
            checks = await asyncio.gather(
                _with_timeout(_vector_rail_check(clean_prompt), vector_timeout),
                _with_timeout(_openrouter_prompt_guard_check(clean_prompt), provider_timeout),
                return_exceptions=True,
            )
    except TimeoutError:
        log.warning(
            "Inline guard timed out (total_timeout_ms=%s), failing closed.",
            INLINE_GUARD_TOTAL_TIMEOUT_MS,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        log.warning("Inline guard failed before completion, failing closed: %s", exc)
        return False

    for check in checks:
        if isinstance(check, Exception):
            log.warning("Inline guard check raised exception, failing closed: %s", check)
            return False
        if check is False:
            return False

    return True
