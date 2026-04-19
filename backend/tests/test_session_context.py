from __future__ import annotations

import pytest

from src.mcp_service.session_context import (
    LoanRef,
    SessionContext,
    SessionContextError,
)

# ─────────────────────────────────────────────────────────────────────────────
# LoanRef
# ─────────────────────────────────────────────────────────────────────────────


def test_loan_ref_from_dict_happy_path() -> None:
    loan = LoanRef.from_dict(
        {
            "loan_number": "LN-001",
            "status": "ACTIVE",
            "product_code": "PL",
            "extra_field": "keep_me",
        }
    )
    assert loan.loan_number == "LN-001"
    assert loan.status == "ACTIVE"
    assert loan.product_code == "PL"
    assert loan.raw["extra_field"] == "keep_me"


def test_loan_ref_rejects_missing_loan_number() -> None:
    with pytest.raises(SessionContextError):
        LoanRef.from_dict({"status": "ACTIVE"})


def test_loan_ref_is_frozen() -> None:
    loan = LoanRef.from_dict({"loan_number": "LN-1", "status": None, "product_code": None})
    with pytest.raises(AttributeError):
        loan.loan_number = "LN-2"  # type: ignore[misc]


def test_loan_ref_raw_is_read_only() -> None:
    loan = LoanRef.from_dict({"loan_number": "LN-1"})
    with pytest.raises(TypeError):
        loan.raw["loan_number"] = "hacked"  # type: ignore[index]


# ─────────────────────────────────────────────────────────────────────────────
# SessionContext
# ─────────────────────────────────────────────────────────────────────────────


def _authenticated_session_dict(**overrides: object) -> dict:
    base = {
        "customer_id": "CUST-42",
        "phone_number": "9999988888",
        "access_token": "tok_abc",
        "loans": [
            {"loan_number": "LN-001", "status": "ACTIVE", "product_code": "PL"},
            {"loan_number": "LN-002", "status": "CLOSED", "product_code": "HL"},
        ],
        "app_id": "LN-001",
        "user_details": {"id": "CUST-42", "name": "Test"},
        "auth_state": "authenticated",
    }
    base.update(overrides)
    return base


def test_session_context_from_dict_happy_path() -> None:
    ctx = SessionContext.from_session_dict("sess_1", _authenticated_session_dict())
    assert ctx.session_id == "sess_1"
    assert ctx.customer_id == "CUST-42"
    assert ctx.phone_number == "9999988888"
    assert ctx.access_token == "tok_abc"
    assert ctx.app_id == "LN-001"
    assert len(ctx.loans) == 2
    assert ctx.loans[0].loan_number == "LN-001"
    assert ctx.user_details["name"] == "Test"


def test_session_context_is_frozen() -> None:
    ctx = SessionContext.from_session_dict("sess_1", _authenticated_session_dict())
    with pytest.raises(AttributeError):
        ctx.customer_id = "CUST-99"  # type: ignore[misc]


def test_session_context_loans_tuple_is_immutable() -> None:
    ctx = SessionContext.from_session_dict("sess_1", _authenticated_session_dict())
    assert isinstance(ctx.loans, tuple)
    with pytest.raises(TypeError):
        ctx.loans[0] = LoanRef.from_dict({"loan_number": "EVIL"})  # type: ignore[index]


def test_session_context_user_details_is_read_only() -> None:
    ctx = SessionContext.from_session_dict("sess_1", _authenticated_session_dict())
    with pytest.raises(TypeError):
        ctx.user_details["name"] = "hacked"  # type: ignore[index]


def test_session_context_missing_customer_id_raises() -> None:
    with pytest.raises(SessionContextError, match="customer_id"):
        SessionContext.from_session_dict("sess_1", _authenticated_session_dict(customer_id=""))


def test_session_context_missing_phone_number_raises() -> None:
    with pytest.raises(SessionContextError, match="phone_number"):
        SessionContext.from_session_dict("sess_1", _authenticated_session_dict(phone_number=""))


def test_session_context_missing_access_token_raises() -> None:
    with pytest.raises(SessionContextError, match="access_token"):
        SessionContext.from_session_dict("sess_1", _authenticated_session_dict(access_token=""))


def test_session_context_app_id_optional() -> None:
    ctx = SessionContext.from_session_dict("sess_1", _authenticated_session_dict(app_id=None))
    assert ctx.app_id is None


def test_session_context_empty_loans_allowed() -> None:
    # A logged-in customer with zero loans is a legitimate (if unusual) state.
    ctx = SessionContext.from_session_dict("sess_1", _authenticated_session_dict(loans=[]))
    assert ctx.loans == ()


def test_session_context_rejects_non_list_loans() -> None:
    with pytest.raises(SessionContextError, match="loans"):
        SessionContext.from_session_dict("sess_1", _authenticated_session_dict(loans="LN-001"))


def test_session_context_ignores_malformed_loan_entries() -> None:
    # Non-dict entries in the list are silently skipped — we don't want a
    # single stray CRM surprise to block the entire session.
    ctx = SessionContext.from_session_dict(
        "sess_1",
        _authenticated_session_dict(
            loans=[
                {"loan_number": "LN-001"},
                "oops_string_entry",
                None,
                {"loan_number": "LN-002"},
            ]
        ),
    )
    assert [loan.loan_number for loan in ctx.loans] == ["LN-001", "LN-002"]
