"""Output-side PII leak detector (GD6 Phase TA4 / R4).

Scans the plaintext response of an authenticated MCP tool for
phone-number-shaped digit sequences that do NOT belong to the caller.
Any hit logs a warning and increments a Prometheus counter — the
response itself is never blocked. The scanner is strictly detection.

Operating model:
- The decorator (``@requires_authenticated_session``) calls
  ``scan_tool_response_for_pii(result, ctx, tool_name)`` after the
  inner tool returns. ``ctx.phone_number`` is the caller's canonical
  phone; any 10-digit sequence that differs from it is flagged.
- ``agent_pii_leak_suspicions_total{tool}`` is the metric operators
  graph. A sustained spike for a tool means either (a) the CRM
  response is leaking another customer's data, or (b) the tool
  legitimately returns phone-shaped data that isn't actually PII
  (e.g., a loan application number like ``RNTWL-1234567890``) — in
  which case we add an allow-list for that tool.

This layer is complementary to the input-side decorator: it catches
*upstream* bugs (CRM returning too much data) that authorization
checks cannot see.
"""

from __future__ import annotations

import logging
import re

from prometheus_client import Counter

from .session_context import SessionContext

log = logging.getLogger(name="mcp_pii_scanner")


AGENT_PII_LEAK_SUSPICIONS_TOTAL = Counter(
    "agent_pii_leak_suspicions_total",
    "Count of unique foreign (not-the-caller's) phone-shaped digit "
    "sequences found in authenticated tool responses, labelled by tool.",
    ["tool"],
)


_PHONE_DIGIT_RUN = re.compile(r"(?<!\d)(\d{10})(?!\d)")


def _canonicalise(phone: str) -> str:
    """Return the last-10-digits of a phone string.

    Accepts any shape (``+91 9999988888``, ``09999988888``,
    ``9999988888``) and reduces to the 10-digit national part so the
    comparison against detected matches is format-agnostic.
    """
    digits = "".join(c for c in phone if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def scan_tool_response_for_pii(response: object, ctx: SessionContext, tool_name: str) -> set[str]:
    """Scan ``response`` for foreign phone-shaped digit runs.

    Returns the set of unique foreign 10-digit strings detected (for
    tests / future admin-side surfacing). The function NEVER raises —
    PII detection must not break the response path. Non-string
    responses (``dict``, ``None``, ...) are serialised via ``str()``
    so the scanner sees their printed form; this is intentional so
    tool return shapes don't bypass the scan.
    """
    try:
        text = response if isinstance(response, str) else str(response)
    except Exception:
        return set()

    caller_last_10 = _canonicalise(ctx.phone_number)
    if not caller_last_10:
        # Defence: a caller without a phone shouldn't have passed the
        # decorator's SessionContext construction, but be paranoid.
        return set()

    foreign: set[str] = set()
    for match in _PHONE_DIGIT_RUN.finditer(text):
        digits = match.group(1)
        if digits == caller_last_10:
            continue
        foreign.add(digits)

    if foreign:
        log.warning(
            "pii_scan: foreign_phones_detected tool=%s caller_last4=%s hits=%d",
            tool_name,
            caller_last_10[-4:],
            len(foreign),
        )
        AGENT_PII_LEAK_SUSPICIONS_TOTAL.labels(tool=tool_name).inc(len(foreign))

    return foreign
