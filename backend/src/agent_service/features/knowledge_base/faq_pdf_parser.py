from __future__ import annotations

import io
import re
from typing import Any

import pdfplumber

_QA_PATTERN = re.compile(
    r"Question:\s*(.*?)\s*Answer:\s*(.*?)(?=\nQuestion:|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def parse_pdf_faqs(pdf_bytes: bytes) -> list[dict[str, str]]:
    if not pdf_bytes:
        return []

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1)
            if text:
                pages.append(text)

    full_text = "\n".join(pages)
    pairs: list[dict[str, str]] = []

    for match in _QA_PATTERN.finditer(full_text):
        question = _clean_text(match.group(1))
        answer = _clean_text(match.group(2))
        if not question or not answer:
            continue
        pairs.append({"question": question, "answer": answer})

    return pairs


def coerce_json_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        q = _clean_text(str(item.get("question") or ""))
        a = _clean_text(str(item.get("answer") or ""))
        if not q or not a:
            continue
        tags: list[str] = []
        raw_tags = item.get("tags")
        if isinstance(raw_tags, str):
            tags = [_clean_text(tag) for tag in raw_tags.split(",") if _clean_text(tag)]
        elif isinstance(raw_tags, list):
            tags = [_clean_text(str(tag)) for tag in raw_tags if _clean_text(str(tag))]

        rows.append(
            {
                "question": q,
                "answer": a,
                "category": _clean_text(str(item.get("category") or "")),
                "tags": tags,
            }
        )
    return rows
