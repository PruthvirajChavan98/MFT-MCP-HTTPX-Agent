from __future__ import annotations

from types import MappingProxyType

import pytest

from src.mcp_service.ownership import (
    OwnershipError,
    active_loan_or_raise,
    verify_loan_ownership,
)
from src.mcp_service.session_context import LoanRef, SessionContext


def _loans(*numbers: str) -> tuple[LoanRef, ...]:
    return tuple(
        LoanRef(
            loan_number=n,
            status="ACTIVE",
            product_code="PL",
            raw=MappingProxyType({"loan_number": n}),
        )
        for n in numbers
    )


def _ctx(
    *,
    customer_id: str = "CUST-42",
    loans: tuple[LoanRef, ...] = (),
    app_id: str | None = None,
) -> SessionContext:
    return SessionContext(
        session_id="sess_1",
        customer_id=customer_id,
        phone_number="9999988888",
        access_token="tok_abc",
        loans=loans,
        app_id=app_id,
        user_details=MappingProxyType({"id": customer_id}),
    )


# ─────────────────────────────────────────────────────────────────────────────
# verify_loan_ownership
# ─────────────────────────────────────────────────────────────────────────────


def test_verify_loan_ownership_happy_path() -> None:
    ctx = _ctx(loans=_loans("LN-001", "LN-002"))
    loan = verify_loan_ownership(ctx, "LN-001", tool="select_loan")
    assert loan.loan_number == "LN-001"


def test_verify_loan_ownership_cross_session_rejects() -> None:
    # Customer B's loan seen by customer A → deny
    ctx_a = _ctx(loans=_loans("LN-A1", "LN-A2"))
    with pytest.raises(OwnershipError) as ei:
        verify_loan_ownership(ctx_a, "LN-B1", tool="select_loan")
    assert ei.value.reason == "loan_not_owned"
    assert ei.value.tool == "select_loan"


def test_verify_loan_ownership_empty_input_rejects() -> None:
    ctx = _ctx(loans=_loans("LN-001"))
    with pytest.raises(OwnershipError) as ei:
        verify_loan_ownership(ctx, "", tool="select_loan")
    assert ei.value.reason == "missing_loan_number"


def test_verify_loan_ownership_whitespace_only_rejects() -> None:
    ctx = _ctx(loans=_loans("LN-001"))
    with pytest.raises(OwnershipError) as ei:
        verify_loan_ownership(ctx, "   ", tool="select_loan")
    assert ei.value.reason == "missing_loan_number"


def test_verify_loan_ownership_trims_whitespace_before_match() -> None:
    ctx = _ctx(loans=_loans("LN-001"))
    loan = verify_loan_ownership(ctx, "  LN-001  ", tool="select_loan")
    assert loan.loan_number == "LN-001"


# ─────────────────────────────────────────────────────────────────────────────
# active_loan_or_raise
# ─────────────────────────────────────────────────────────────────────────────


def test_active_loan_or_raise_happy_path() -> None:
    ctx = _ctx(loans=_loans("LN-001", "LN-002"), app_id="LN-001")
    loan = active_loan_or_raise(ctx, tool="loan_details")
    assert loan.loan_number == "LN-001"


def test_active_loan_or_raise_requires_select_loan() -> None:
    ctx = _ctx(loans=_loans("LN-001"), app_id=None)
    with pytest.raises(OwnershipError) as ei:
        active_loan_or_raise(ctx, tool="loan_details")
    assert ei.value.reason == "no_active_loan"


def test_active_loan_or_raise_validates_app_id_still_present() -> None:
    # Defence against "loans array tampering" — app_id may still carry a
    # loan number that no longer appears in ctx.loans. Reject rather than
    # trust the stale app_id pointer.
    ctx = _ctx(loans=_loans("LN-002"), app_id="LN-001")
    with pytest.raises(OwnershipError) as ei:
        active_loan_or_raise(ctx, tool="loan_details")
    assert ei.value.reason == "app_id_not_owned"


def test_ownership_error_carries_tool_label() -> None:
    ctx = _ctx(loans=_loans("LN-001"), app_id=None)
    with pytest.raises(OwnershipError) as ei:
        active_loan_or_raise(ctx, tool="dashboard_home")
    assert ei.value.tool == "dashboard_home"
    assert "select_loan" in ei.value.message
