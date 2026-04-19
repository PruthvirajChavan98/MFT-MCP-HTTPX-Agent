"""Tests for the output-side PII leak detector (GD6 TA4 / R4, RR1).

Four PII classes — phone, pan, aadhaar, email — each with its own
regex, exempt source on ``ctx.user_details``, and Counter label. The
scanner NEVER blocks the response; assertions here verify (a) the
correct foreign matches end up in the per-class sets, (b) the
caller's own values (in any format) are exempt, (c) the Prometheus
counter gets the right increment per ``(tool, pii_class)`` label
pair, and (d) class regexes don't cross-fire on each other's shapes.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

import pytest
from prometheus_client import CollectorRegistry, Counter

from src.mcp_service import output_pii_scanner as scanner_mod
from src.mcp_service.output_pii_scanner import (
    _canonicalise,
    _canonicalise_aadhaar,
    _canonicalise_email,
    _canonicalise_pan,
    scan_tool_response_for_pii,
)
from src.mcp_service.session_context import LoanRef, SessionContext


def _ctx(phone: str = "9999988888", **user_details_extra: Any) -> SessionContext:
    user_details = {"id": "CUST-42", **user_details_extra}
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
        user_details=MappingProxyType(user_details),
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
        ["tool", "pii_class"],
        registry=registry,
    )
    monkeypatch.setattr(scanner_mod, "AGENT_PII_LEAK_SUSPICIONS_TOTAL", fresh)
    return fresh


def _empty_by_class() -> dict[str, set[str]]:
    return {"phone": set(), "pan": set(), "aadhaar": set(), "email": set()}


# ─────────────────────────────────────────────────────────────────────────────
# Canonicalise helpers
# ─────────────────────────────────────────────────────────────────────────────


def test_canonicalise_phone_strips_country_code_to_last_10() -> None:
    assert _canonicalise("+91 99999 88888") == "9999988888"
    assert _canonicalise("09999988888") == "9999988888"
    assert _canonicalise("9999988888") == "9999988888"
    assert _canonicalise("91-9999988888") == "9999988888"


def test_canonicalise_phone_tolerates_short_input() -> None:
    assert _canonicalise("999") == "999"
    assert _canonicalise("") == ""


def test_canonicalise_pan_uppercases_and_strips() -> None:
    assert _canonicalise_pan("  abcde1234f  ") == "ABCDE1234F"
    assert _canonicalise_pan("") == ""


def test_canonicalise_aadhaar_strips_spaces() -> None:
    assert _canonicalise_aadhaar("1234 5678 9012") == "123456789012"
    assert _canonicalise_aadhaar("123456789012") == "123456789012"
    assert _canonicalise_aadhaar("1234") == ""  # not 12 digits → not canonical
    assert _canonicalise_aadhaar("") == ""


def test_canonicalise_email_lowercases_and_strips() -> None:
    assert _canonicalise_email(" TEST@EXAMPLE.COM ") == "test@example.com"
    assert _canonicalise_email("") == ""


# ─────────────────────────────────────────────────────────────────────────────
# Phone class — pre-existing behaviour, updated for dict return shape
# ─────────────────────────────────────────────────────────────────────────────


def test_scanner_returns_empty_by_class_when_no_matches() -> None:
    result = scan_tool_response_for_pii("no numbers at all in this string", _ctx(), "loan_details")
    assert result == _empty_by_class()


def test_scanner_ignores_callers_own_phone(fresh_counter: Counter) -> None:
    response = "Your EMI is due. Reach us at 9999988888 for help."
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result["phone"] == set()
    assert fresh_counter.labels(tool="loan_details", pii_class="phone")._value.get() == 0


def test_scanner_ignores_callers_phone_regardless_of_format() -> None:
    response = "Registered phone: +91-9999988888. Please confirm."
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result["phone"] == set()


def test_scanner_flags_foreign_phone(fresh_counter: Counter) -> None:
    response = "Raj's phone is 8888877777. Call him for loan info."
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result["phone"] == {"8888877777"}
    assert fresh_counter.labels(tool="loan_details", pii_class="phone")._value.get() == 1


def test_scanner_dedupes_repeated_foreign_phones(fresh_counter: Counter) -> None:
    response = "Contact 8888877777 for help. Or 8888877777 again. Or a new one: 7777766666."
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result["phone"] == {"8888877777", "7777766666"}
    assert fresh_counter.labels(tool="loan_details", pii_class="phone")._value.get() == 2


def test_scanner_counter_is_per_tool(fresh_counter: Counter) -> None:
    scan_tool_response_for_pii("8888877777", _ctx("9999988888"), "loan_details")
    scan_tool_response_for_pii("7777766666", _ctx("9999988888"), "noc_details")
    assert fresh_counter.labels(tool="loan_details", pii_class="phone")._value.get() == 1
    assert fresh_counter.labels(tool="noc_details", pii_class="phone")._value.get() == 1


def test_scanner_does_not_false_positive_on_11_digit_runs() -> None:
    response = "Order 12345678901 placed; loan application 9876543210987."
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result["phone"] == set()
    # 13-digit run also shouldn't fire Aadhaar.
    assert result["aadhaar"] == set()


def test_scanner_accepts_10_digits_bounded_by_punctuation() -> None:
    response = "Also reachable: (8888877777), or via 7777766666!"
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result["phone"] == {"8888877777", "7777766666"}


# ─────────────────────────────────────────────────────────────────────────────
# PAN class
# ─────────────────────────────────────────────────────────────────────────────


def test_scanner_flags_foreign_pan_number(fresh_counter: Counter) -> None:
    response = "Applicant PAN: ABCDE1234F on file."
    result = scan_tool_response_for_pii(response, _ctx(), "loan_details")
    assert result["pan"] == {"ABCDE1234F"}
    assert fresh_counter.labels(tool="loan_details", pii_class="pan")._value.get() == 1


def test_scanner_ignores_callers_own_pan(fresh_counter: Counter) -> None:
    response = "Registered PAN: ABCDE1234F."
    ctx = _ctx(pan="abcde1234f")  # stored lowercased; canonicalisation normalises
    result = scan_tool_response_for_pii(response, ctx, "loan_details")
    assert result["pan"] == set()
    assert fresh_counter.labels(tool="loan_details", pii_class="pan")._value.get() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Aadhaar class
# ─────────────────────────────────────────────────────────────────────────────


def test_scanner_flags_foreign_aadhaar_12_digits(fresh_counter: Counter) -> None:
    response = "Next of kin's Aadhaar: 1234 5678 9012."
    result = scan_tool_response_for_pii(response, _ctx(), "loan_details")
    assert result["aadhaar"] == {"123456789012"}
    assert fresh_counter.labels(tool="loan_details", pii_class="aadhaar")._value.get() == 1


def test_scanner_flags_foreign_aadhaar_without_spaces() -> None:
    response = "Aadhaar on record: 123456789012."
    result = scan_tool_response_for_pii(response, _ctx(), "loan_details")
    assert result["aadhaar"] == {"123456789012"}


def test_scanner_ignores_callers_own_aadhaar_last_4_match() -> None:
    # CRM commonly returns Aadhaar masked as ``XXXX-XXXX-1234``. When the
    # caller's session has ``aadhaar_last_4`` populated, any 12-digit run
    # ending in those 4 digits must be treated as the caller's own.
    response = "Your Aadhaar on record: 9999 8888 1234"
    ctx = _ctx(aadhaar_last_4="1234")
    result = scan_tool_response_for_pii(response, ctx, "loan_details")
    assert result["aadhaar"] == set()


def test_scanner_ignores_callers_full_aadhaar_regardless_of_spacing() -> None:
    response = "Your Aadhaar: 123456789012. Please confirm."
    ctx = _ctx(aadhaar="1234 5678 9012")  # stored with spaces
    result = scan_tool_response_for_pii(response, ctx, "loan_details")
    assert result["aadhaar"] == set()


def test_scanner_aadhaar_regex_does_not_match_phone(fresh_counter: Counter) -> None:
    # A bare 10-digit phone must not fire the aadhaar regex — only phone.
    response = "Contact number: 8888877777"
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result["phone"] == {"8888877777"}
    assert result["aadhaar"] == set()
    assert fresh_counter.labels(tool="loan_details", pii_class="aadhaar")._value.get() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Email class
# ─────────────────────────────────────────────────────────────────────────────


def test_scanner_flags_foreign_email(fresh_counter: Counter) -> None:
    response = "Forwarded to raj+loans@example.com for review."
    result = scan_tool_response_for_pii(response, _ctx(), "loan_details")
    assert result["email"] == {"raj+loans@example.com"}
    assert fresh_counter.labels(tool="loan_details", pii_class="email")._value.get() == 1


def test_scanner_ignores_callers_own_email_case_insensitive() -> None:
    response = "Statement sent to YOU@EXAMPLE.COM. Check your inbox."
    ctx = _ctx(email="you@example.com")
    result = scan_tool_response_for_pii(response, ctx, "loan_details")
    assert result["email"] == set()


# ─────────────────────────────────────────────────────────────────────────────
# Multi-class per-label counter isolation
# ─────────────────────────────────────────────────────────────────────────────


def test_scanner_counter_labels_include_pii_class(fresh_counter: Counter) -> None:
    response = (
        "Ref: ABCDE1234F, mobile 8888877777, Aadhaar 1234 5678 9012, " "ping foreign@example.com."
    )
    result = scan_tool_response_for_pii(response, _ctx("9999988888"), "loan_details")
    assert result["phone"] == {"8888877777"}
    assert result["pan"] == {"ABCDE1234F"}
    assert result["aadhaar"] == {"123456789012"}
    assert result["email"] == {"foreign@example.com"}
    for cls in ("phone", "pan", "aadhaar", "email"):
        assert (
            fresh_counter.labels(tool="loan_details", pii_class=cls)._value.get() == 1
        ), f"counter not incremented for pii_class={cls}"


# ─────────────────────────────────────────────────────────────────────────────
# Robustness
# ─────────────────────────────────────────────────────────────────────────────


def test_scanner_handles_non_string_response() -> None:
    # str() coercion means dict/list responses still get scanned.
    result = scan_tool_response_for_pii(
        {"note": "call 8888877777 urgently"}, _ctx("9999988888"), "loan_details"
    )
    assert result["phone"] == {"8888877777"}


def test_scanner_handles_none_response() -> None:
    result = scan_tool_response_for_pii(None, _ctx(), "loan_details")
    assert result == _empty_by_class()


def test_scanner_skips_when_caller_has_no_phone() -> None:
    # SessionContext construction blocks this upstream, but if a bug
    # ever produces a ctx with empty phone we must not false-positive
    # on EVERY number in the response.
    ctx = _ctx(phone="")
    result = scan_tool_response_for_pii("8888877777 ABCDE1234F", ctx, "loan_details")
    assert result == _empty_by_class()
