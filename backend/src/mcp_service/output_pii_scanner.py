"""Output-side PII leak detector (GD6 TA4 / R4, expanded in RR1).

Scans the plaintext response of an authenticated MCP tool for four
classes of personally-identifiable strings that do NOT belong to the
caller:

- ``phone``   — 10-digit runs (canonical Indian MSISDN).
- ``pan``     — Indian PAN format ``AAAAA9999A``.
- ``aadhaar`` — 12 digits with optional single-space grouping.
- ``email``   — simplified RFC-lookalike pattern.

For every unique foreign match the Prometheus Counter
``agent_pii_leak_suspicions_total{tool, pii_class}`` increments; each
hit also emits a log warning. The tool's response itself is never
modified — this layer is strictly detection, complementary to the
input-side authorization decorator.

Adding a new authenticated tool does not require touching this
scanner — the decorator runs it on every authenticated response. If
a tool legitimately emits one of these patterns (e.g. a loan
application number shaped like a PAN) operators allow-list that
``(tool, pii_class)`` pair operationally — either by muting the
Grafana alert or by adding a conditional short-circuit here.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from prometheus_client import Counter

from .session_context import SessionContext

log = logging.getLogger(name="mcp_pii_scanner")


AGENT_PII_LEAK_SUSPICIONS_TOTAL = Counter(
    "agent_pii_leak_suspicions_total",
    "Unique foreign (not-the-caller's) PII-shaped strings found in "
    "authenticated tool responses, labelled by tool and PII class.",
    ["tool", "pii_class"],
)


_PII_CLASS_NAMES: tuple[str, ...] = ("phone", "pan", "aadhaar", "email")


# ─────────────────────────────────────────────────────────────────────────────
# Regex patterns
# ─────────────────────────────────────────────────────────────────────────────

# 10-digit phone bounded by non-digits. Keeps timestamps / order IDs out.
_PHONE_PATTERN = re.compile(r"(?<!\d)(\d{10})(?!\d)")

# PAN — AAAAA9999A (5 letters + 4 digits + 1 letter). Word-bounded so
# embeddings like "NOT-PAN-ABCDE1234F-SUFFIX" still hit on the middle
# substring, but a run of 11 letters (no digit segment) doesn't.
_PAN_PATTERN = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")

# Aadhaar — 12 digits with optional single whitespace between 4-digit
# groups. Bounded by non-digits so 13+ digit runs aren't misread.
_AADHAAR_PATTERN = re.compile(r"(?<!\d)(\d{4}\s?\d{4}\s?\d{4})(?!\d)")

# Email — intentionally simplified. Covers the common shapes without
# the full RFC-5322 complexity; a false miss on exotic valid emails is
# less bad than false-positive spam from an over-permissive pattern.
_EMAIL_PATTERN = re.compile(r"\b[\w.+\-]+@[\w\-]+\.[\w.\-]+\b")


# ─────────────────────────────────────────────────────────────────────────────
# Canonicalisation (match side — applied to every regex hit before
# dedupe / exempt comparison)
# ─────────────────────────────────────────────────────────────────────────────


def _canonicalise_phone(phone: str) -> str:
    """Return the last-10-digits of a phone string, format-agnostic.

    Accepts ``+91 9999988888``, ``09999988888``, ``9999988888`` etc.
    Used for BOTH the caller's stored phone and every match.
    """
    digits = "".join(c for c in phone if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def _canonicalise_pan(value: str) -> str:
    return (value or "").strip().upper()


def _canonicalise_aadhaar(value: str) -> str:
    """Return the 12-digit canonical form of an Aadhaar-like string.

    Strips all whitespace. Returns ``""`` if the cleaned form isn't
    exactly 12 digits — used for the caller's stored value, where we
    can be strict about shape.
    """
    digits = re.sub(r"\s+", "", value or "")
    return digits if len(digits) == 12 and digits.isdigit() else ""


def _canonicalise_email(value: str) -> str:
    return (value or "").strip().lower()


# Historical compatibility alias (used by tests written before RR1).
_canonicalise = _canonicalise_phone


# ─────────────────────────────────────────────────────────────────────────────
# Per-class exempt predicates — "is THIS match the caller's own?"
# ─────────────────────────────────────────────────────────────────────────────


def _phone_is_exempt(canonical: str, ctx: SessionContext) -> bool:
    own = _canonicalise_phone(ctx.phone_number)
    return bool(own) and canonical == own


def _pan_is_exempt(canonical: str, ctx: SessionContext) -> bool:
    own = _canonicalise_pan(str(ctx.user_details.get("pan", "")))
    return bool(own) and canonical == own


def _aadhaar_is_exempt(canonical: str, ctx: SessionContext) -> bool:
    """Aadhaar exempts the caller in two modes:

    1. Full 12-digit match against ``ctx.user_details["aadhaar"]``.
    2. Last-4 match against ``ctx.user_details["aadhaar_last_4"]`` —
       the CRM commonly returns Aadhaar masked as ``XXXX-XXXX-1234``,
       so if only the last 4 are in session, exempt any 12-digit run
       ending in those 4 digits.
    """
    own_full = _canonicalise_aadhaar(str(ctx.user_details.get("aadhaar", "")))
    if own_full and canonical == own_full:
        return True
    last_4 = str(ctx.user_details.get("aadhaar_last_4", "")).strip()
    if len(last_4) == 4 and last_4.isdigit() and canonical.endswith(last_4):
        return True
    return False


def _email_is_exempt(canonical: str, ctx: SessionContext) -> bool:
    own = _canonicalise_email(str(ctx.user_details.get("email", "")))
    return bool(own) and canonical == own


# ─────────────────────────────────────────────────────────────────────────────
# Class registry
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _PiiClass:
    name: str
    pattern: re.Pattern[str]
    canonicalise_match: Callable[[str], str]
    is_exempt: Callable[[str, SessionContext], bool]


_PII_CLASSES: tuple[_PiiClass, ...] = (
    # Phone matches are already 10 digits by regex construction, but
    # routing through `_canonicalise_phone` keeps intent explicit so a
    # future regex widening (e.g. capturing `+91XXXXXXXXXX`) cannot
    # silently leave matches un-normalised. (code-review LOW-1)
    _PiiClass("phone", _PHONE_PATTERN, _canonicalise_phone, _phone_is_exempt),
    _PiiClass("pan", _PAN_PATTERN, _canonicalise_pan, _pan_is_exempt),
    _PiiClass(
        "aadhaar",
        _AADHAAR_PATTERN,
        lambda m: re.sub(r"\s+", "", m),
        _aadhaar_is_exempt,
    ),
    _PiiClass("email", _EMAIL_PATTERN, _canonicalise_email, _email_is_exempt),
)


def _empty_result() -> dict[str, set[str]]:
    return {name: set() for name in _PII_CLASS_NAMES}


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def scan_tool_response_for_pii(
    response: object, ctx: SessionContext, tool_name: str
) -> dict[str, set[str]]:
    """Scan ``response`` for foreign matches across all PII classes.

    Returns ``dict[class_name, set[canonical_match]]`` for every class
    in ``_PII_CLASS_NAMES``; classes with no hits map to an empty set
    so callers can rely on the shape. The function NEVER raises —
    detection must not break the tool's response path.
    """
    result = _empty_result()

    try:
        text = response if isinstance(response, str) else str(response)
    except Exception:
        return result

    # Short-circuit: a caller who somehow reached here without a
    # phone number shouldn't produce false positives. SessionContext
    # construction enforces non-empty phone_number, but be paranoid.
    if not _canonicalise_phone(ctx.phone_number):
        return result

    for cls in _PII_CLASSES:
        hits: set[str] = set()
        for match in cls.pattern.finditer(text):
            # Use the whole match (group 0) so patterns without an
            # explicit capture group (email) also work. Lookarounds
            # in the phone/aadhaar regexes are zero-width, so the
            # whole match equals the historical group-1 value.
            canonical = cls.canonicalise_match(match.group(0))
            if not canonical:
                continue
            if cls.is_exempt(canonical, ctx):
                continue
            hits.add(canonical)

        if hits:
            log.warning(
                "pii_scan: foreign_%s_detected tool=%s caller=%s hits=%d",
                cls.name,
                tool_name,
                ctx.customer_id,
                len(hits),
            )
            AGENT_PII_LEAK_SUSPICIONS_TOTAL.labels(tool=tool_name, pii_class=cls.name).inc(
                len(hits)
            )
            result[cls.name] = hits

    return result


# Helpers used by tests — exposed so test assertions can reuse the
# same canonicalisation logic the scanner does.
__all__ = [
    "AGENT_PII_LEAK_SUSPICIONS_TOTAL",
    "scan_tool_response_for_pii",
    "_canonicalise",
    "_canonicalise_phone",
    "_canonicalise_pan",
    "_canonicalise_aadhaar",
    "_canonicalise_email",
]


def _supported_classes() -> Iterable[str]:  # pragma: no cover — introspection aid
    return _PII_CLASS_NAMES


# Type-checker hint: we access ctx.user_details via .get() without
# claiming a schema. This alias keeps the callable inspectable.
_UserDetails = dict[str, Any]
