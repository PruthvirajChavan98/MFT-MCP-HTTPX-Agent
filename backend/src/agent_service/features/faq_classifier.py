"""LLM-based FAQ categorization using Groq API."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from src.agent_service.core.config import GROQ_API_KEYS, GROQ_BASE_URL
from src.agent_service.core.http_client import get_http_client

log = logging.getLogger(__name__)

FAQ_CLASSIFIER_MODEL = os.getenv("FAQ_CLASSIFIER_MODEL", "openai/gpt-oss-120b").strip()
BATCH_SIZE = int(os.getenv("FAQ_CLASSIFIER_BATCH_SIZE", "30"))


async def classify_faqs(
    items: list[dict[str, Any]],
    category_labels: list[str],
) -> list[dict[str, Any]]:
    """Classify a list of FAQ items into categories using Groq LLM.

    Populates the 'category' field on each item.  Items that already have
    a category are left unchanged.  If classification fails, items are
    returned unchanged (empty category defaults to 'technical' downstream).
    """
    if not items or not category_labels or not GROQ_API_KEYS:
        return items

    # Split items needing classification
    needs_classification: list[tuple[int, dict[str, Any]]] = [
        (i, item) for i, item in enumerate(items) if not (item.get("category") or "").strip()
    ]
    if not needs_classification:
        return items

    indices, to_classify_tuple = zip(*needs_classification, strict=True)
    to_classify: list[dict[str, Any]] = list(to_classify_tuple)
    batches = [to_classify[i : i + BATCH_SIZE] for i in range(0, len(to_classify), BATCH_SIZE)]

    all_categories: list[str] = []
    for batch in batches:
        categories = await _classify_batch(batch, category_labels)
        all_categories.extend(categories)

    # Apply classifications back — immutable: build new list with new dicts
    result = list(items)
    for idx, category in zip(indices, all_categories, strict=True):
        if category:
            result[idx] = {**result[idx], "category": category}

    return result


async def _classify_batch(
    batch: list[dict[str, Any]],
    category_labels: list[str],
) -> list[str]:
    """Classify a single batch of FAQs via Groq API."""
    try:
        faqs_payload = [
            {
                "index": i,
                "question": (item.get("question") or "")[:500],
                "answer_preview": (item.get("answer") or "")[:200],
            }
            for i, item in enumerate(batch)
        ]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an FAQ categorizer for a fintech NBFC company. "
                    "Classify each FAQ into exactly one of the provided categories "
                    "based on its content. "
                    "Return a JSON object with a 'classifications' key containing an array. "
                    "Each entry must have: index (int matching the input index), "
                    "category (string, must be one of the provided categories). "
                    "If unsure, use 'technical' as the default."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "categories": category_labels,
                        "faqs": faqs_payload,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        payload: dict[str, Any] = {
            "model": FAQ_CLASSIFIER_MODEL,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEYS[0]}",
            "Content-Type": "application/json",
        }

        client = await get_http_client()
        response = await client.post(
            f"{GROQ_BASE_URL.rstrip('/')}/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()

        body = response.json()
        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            log.warning("FAQ classifier: empty response from Groq")
            return [""] * len(batch)

        parsed = json.loads(content)
        classifications = parsed.get("classifications", [])
        if not isinstance(classifications, list):
            log.warning("FAQ classifier: response missing 'classifications' array")
            return [""] * len(batch)

        # Build a set of valid category labels (lowered) for validation
        valid_labels = {c.lower() for c in category_labels}

        # Map index -> category
        by_index: dict[int, str] = {}
        for entry in classifications:
            if isinstance(entry, dict):
                idx = entry.get("index")
                cat = str(entry.get("category", "")).strip().lower()
                if isinstance(idx, int) and cat in valid_labels:
                    by_index[idx] = cat

        return [by_index.get(i, "") for i in range(len(batch))]

    except Exception:
        log.warning("FAQ classifier batch failed", exc_info=True)
        return [""] * len(batch)
