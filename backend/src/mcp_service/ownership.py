from __future__ import annotations

import logging

from prometheus_client import Counter

from .session_context import LoanRef, SessionContext

log = logging.getLogger(name="mcp_ownership")


OWNERSHIP_REJECTIONS_TOTAL = Counter(
    "agent_ownership_rejections_total",
    "Tool-level ownership rejections, labelled by tool and reason.",
    ["tool", "reason"],
)


class OwnershipError(Exception):
    """Raised when the caller references a resource they do not own.

    Carries a human-readable ``message`` the MCP tool layer surfaces
    verbatim, plus a ``reason`` tag for metrics. The MCP tool catches
    this and returns ``message`` as the tool response — the agent LLM
    then renders a natural-language refusal for the end user.
    """

    def __init__(self, message: str, *, reason: str, tool: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason
        self.tool = tool or "unknown"
        OWNERSHIP_REJECTIONS_TOTAL.labels(tool=self.tool, reason=reason).inc()


_NOT_OWNED_MESSAGE = (
    "That loan doesn't appear on your account. Please use list_loans to see your "
    "available loans and then select_loan with the correct loan number."
)

_NO_ACTIVE_LOAN_MESSAGE = (
    "No active loan is selected. Please run list_loans, then select_loan with a "
    "loan number from your account before requesting loan details."
)


def verify_loan_ownership(
    ctx: SessionContext, loan_number: str, *, tool: str | None = None
) -> LoanRef:
    """Return the ``LoanRef`` from ``ctx.loans`` matching ``loan_number``.

    Raises ``OwnershipError`` when the loan is not present on the session.
    This helper is the ONLY place the ``loan_number in session.loans``
    predicate should appear — centralising it means "which loans a
    session may reference" is a single line of code to audit.
    """
    target = (loan_number or "").strip()
    if not target:
        raise OwnershipError(_NOT_OWNED_MESSAGE, reason="missing_loan_number", tool=tool)
    for loan in ctx.loans:
        if loan.loan_number == target:
            return loan
    log.info(
        "ownership: deny tool=%s customer=%s requested=%s known=%s",
        tool or "unknown",
        ctx.customer_id,
        target,
        [loan.loan_number for loan in ctx.loans],
    )
    raise OwnershipError(_NOT_OWNED_MESSAGE, reason="loan_not_owned", tool=tool)


def active_loan_or_raise(ctx: SessionContext, *, tool: str | None = None) -> LoanRef:
    """Return the currently-selected loan, or raise ``OwnershipError``.

    Use this INSTEAD of reading ``ctx.app_id`` directly. The helper
    re-verifies the selected ``app_id`` is still a member of ``ctx.loans``
    — that closes the "loans array tampering" and "stale app_id" bug
    classes in one place.
    """
    if not ctx.app_id:
        raise OwnershipError(_NO_ACTIVE_LOAN_MESSAGE, reason="no_active_loan", tool=tool)
    for loan in ctx.loans:
        if loan.loan_number == ctx.app_id:
            return loan
    log.warning(
        "ownership: app_id not in loans tool=%s customer=%s app_id=%s known=%s",
        tool or "unknown",
        ctx.customer_id,
        ctx.app_id,
        [loan.loan_number for loan in ctx.loans],
    )
    raise OwnershipError(_NOT_OWNED_MESSAGE, reason="app_id_not_owned", tool=tool)
