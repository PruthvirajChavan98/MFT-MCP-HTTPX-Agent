"""Tests for the output-side PII leak detector (GD6 TA4 / R4).

The scanner NEVER blocks the response — the assertions here verify that
(a) the correct set of foreign phones is returned for observability,
(b) the caller's own phone (in any format) is exempt, and (c) the
Prometheus counter gets the right increment.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest
from prometheus_client import CollectorRegistry, Counter

from src.mcp_service import output_pii_scanner as scanner_mod
from src.mcp_service.output_pii_scanner import (
    _canonicalise,
    scan_tool_response_for_pii,
)
from src.mcp_service.session_context import LoanRef, SessionContext


def _ctx(phone: str = "9999988888") -> SessionContext:
    return SessionContext(
        session_id="sess_1",
        customer_id="CUST-42",
        phone_number=phone,
        access_token="tok_abc",
        loans=(
            LoanRef(
                loan_number="LN-001",
                status="ACTIVE",
                product_code="PL",
                raw=MappingProxyType({"loan_number": "LN-001"}),
            ),
        ),
        app_id="LN-001",
        user_details=MappingProxyType({"id": "CUST-42"}),
    )


@pytest.fixture(autouse=True)
def fresh_counter(monkeypatch: pytest.MonkeyPatch) -> Counter:
    """Rebuild the PII counter on a fresh CollectorRegistry per test so
    label counts don't leak between tests (the global counter is
    process-wide)."""
    registry = CollectorRegistry()
    fresh = Counter(
        "agent_pii_leak_suspicions_total",
        "test-isolated copy of the PII counter",
        ["tool"],
        registry=registry,
    )
    monkeypatch.setattr(scanner_mod, "AGENT_PII_LEAK_SUSPICIONS_TOTAL", fresh)
    return fresh


# ─────────────────────────────────────────────────────────────────────────────
# canonicalise helper
# ─────────────────────────────────────────────────────────────────────────────


def test_canonicalise_strips_country_code_to_last_10() -> None:
    assert _canonicalise("+91 99999 88888") == "9999988888"
    assert _canonicalise("09999988888") == "9999988888"
    assert _canonicalise("9999988888") == "9999988888"
    assert _canonicalise("91-9999988888") == "9999988888"


def test_canonicalise_tolerates_short_input() -> None:
    assert _canonicalise("999") == "999"
    assert _canonicalise("") == ""


# ─────────────────────────────────────────────────────────────────────────────
# Scanner — no hits
# ─────────────────────────────────────────────────────────────────────────────


def test_scanner_returns_empty_set_for_response_without_digits() -> None:
    result = scan_tool_response_for_pii("no numbers at all in this string", _ctx(), "loan_details")
    assert result == set()


def test_scanner_ignores_callers_own_phone(fresh_counter: Counter) -> None:
    response = "Your EMI is due. Reach us at 9999988888 for help."
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result == set()
    assert fresh_counter.labels(tool="loan_details")._value.get() == 0


def test_scanner_ignores_callers_phone_regardless_of_format() -> None:
    # Response carries the caller's number with country code; the
    # canonical-last-10 match still exempts it.
    response = "Registered phone: +91-9999988888. Please confirm."
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result == set()


# ─────────────────────────────────────────────────────────────────────────────
# Scanner — hits
# ─────────────────────────────────────────────────────────────────────────────


def test_scanner_flags_foreign_phone(fresh_counter: Counter) -> None:
    response = "Raj's phone is 8888877777. Call him for loan info."
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result == {"8888877777"}
    assert fresh_counter.labels(tool="loan_details")._value.get() == 1


def test_scanner_dedupes_repeated_foreign_phones(fresh_counter: Counter) -> None:
    response = "Contact 8888877777 for help. Or 8888877777 again. Or a new one: 7777766666."
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result == {"8888877777", "7777766666"}
    # Counter increments once per UNIQUE foreign phone, not per occurrence.
    assert fresh_counter.labels(tool="loan_details")._value.get() == 2


def test_scanner_counter_is_per_tool(fresh_counter: Counter) -> None:
    scan_tool_response_for_pii("8888877777", _ctx("9999988888"), "loan_details")
    scan_tool_response_for_pii("7777766666", _ctx("9999988888"), "noc_details")
    assert fresh_counter.labels(tool="loan_details")._value.get() == 1
    assert fresh_counter.labels(tool="noc_details")._value.get() == 1


def test_scanner_does_not_false_positive_on_11_digit_runs(
    fresh_counter: Counter,
) -> None:
    # A tracking number or order ID of 11+ digits must not be detected
    # as a phone — we only flag sequences that are EXACTLY 10 digits
    # bounded by non-digits. Otherwise any amount/timestamp produces noise.
    response = "Order 12345678901 placed; loan application 9876543210987."
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result == set()


def test_scanner_accepts_10_digits_bounded_by_punctuation(
    fresh_counter: Counter,
) -> None:
    # Commas, brackets, whitespace, commas inside the response should
    # not defeat the detection.
    response = "Also reachable: (8888877777), or via 7777766666!"
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result == {"8888877777", "7777766666"}


# ─────────────────────────────────────────────────────────────────────────────
# Robustness
# ─────────────────────────────────────────────────────────────────────────────


def test_scanner_handles_non_string_response() -> None:
    # str() coercion means dict/list responses still get scanned.
    result = scan_tool_response_for_pii(
        {"note": "call 8888877777 urgently"}, _ctx("9999988888"), "loan_details"
    )
    assert result == {"8888877777"}


def test_scanner_handles_none_response() -> None:
    assert scan_tool_response_for_pii(None, _ctx(), "loan_details") == set()


def test_scanner_skips_when_caller_has_no_phone() -> None:
    # SessionContext construction blocks this upstream, but if a bug
    # ever produces a ctx with empty phone we must not false-positive
    # on EVERY number in the response.
    ctx = _ctx(phone="")
    result = scan_tool_response_for_pii("8888877777", ctx, "loan_details")
    assert result == set()
