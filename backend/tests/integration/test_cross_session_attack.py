"""Live cross-session attack test (GD6 Phase R3).

Automates the semi-manual verification step from the GD6 plan. Two
customer sessions authenticate against the running mock CRM, then
session A tries to reference session B's loan via ``select_loan``. The
test asserts the MCP tool returns the canonical ownership-rejection
string and — critically — that session A's ``app_id`` is NOT flipped
to B's loan number.

Run with the stack up:

    make local-up
    MCP_SERVER_URL=http://localhost:8050/sse \\
        uv run pytest tests/integration/ -m integration -v

The phone numbers and their owned loan numbers are supplied via the
``INTEGRATION_PHONE_A`` / ``INTEGRATION_PHONE_B`` env vars (both
required, so the test can run against any deployment's mock CRM seed
without hard-coding). If either is missing the test skips with a hint.
"""

from __future__ import annotations

import os

import pytest
from fastmcp import Client

pytestmark = pytest.mark.integration


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(
            f"{name} not set — export it with a phone the mock CRM "
            f"recognises, e.g. INTEGRATION_PHONE_A=9999900001"
        )
    return value


async def _authenticate_session(
    client: Client, session_id: str, phone: str, otp: str = "123456"
) -> list[dict]:
    """Run the full OTP flow for one session; return the loans list."""
    gen = await client.call_tool("generate_otp", {"user_input": phone, "session_id": session_id})
    assert (
        "OTP" in gen.data or "sent" in str(gen.data).lower()
    ), f"generate_otp failed for {phone}: {gen.data!r}"

    val = await client.call_tool("validate_otp", {"otp": otp, "session_id": session_id})
    val_text = str(val.data)
    assert (
        "success" in val_text.lower() or "Logged in" in val_text
    ), f"validate_otp failed for {phone}: {val_text!r}"

    loans_resp = await client.call_tool("list_loans", {"session_id": session_id})
    loans_text = str(loans_resp.data)
    # Format: "loan_number|status|product_code|active\nLN-XXX|...|..."
    rows = [r for r in loans_text.split("\n") if "|" in r][1:]
    loans = [{"loan_number": r.split("|")[0]} for r in rows if r.split("|")[0].strip()]
    assert loans, f"no loans returned for {phone}; got {loans_text!r}"
    return loans


@pytest.mark.asyncio
async def test_cross_session_select_loan_rejected() -> None:
    phone_a = _required_env("INTEGRATION_PHONE_A")
    phone_b = _required_env("INTEGRATION_PHONE_B")
    url = os.environ.get("MCP_SERVER_URL", "http://localhost:8050/sse")

    session_a = "integ_sess_a"
    session_b = "integ_sess_b"

    async with Client(url) as client:
        loans_a = await _authenticate_session(client, session_a, phone_a)
        loans_b = await _authenticate_session(client, session_b, phone_b)

        loan_a = loans_a[0]["loan_number"]
        loan_b = loans_b[0]["loan_number"]
        assert loan_a != loan_b, (
            "test precondition: both phones must own different loans; " f"got {loan_a} == {loan_b}"
        )

        # Cross-session attack: A tries to select B's loan.
        attack = await client.call_tool(
            "select_loan",
            {"loan_number": loan_b, "session_id": session_a},
        )
        attack_text = str(attack.data).lower()
        assert "doesn't appear" in attack_text, (
            f"GD6 REGRESSION — cross-session select_loan was accepted "
            f"by the live stack. Got: {attack_text!r}"
        )

        # And the victim's app_id must NOT have been flipped to B's loan.
        resp = await client.call_tool("list_loans", {"session_id": session_a})
        rows = [r for r in str(resp.data).split("\n") if "|" in r][1:]
        active_rows = [r for r in rows if r.endswith("|yes")]
        assert not active_rows or all(r.split("|")[0] == loan_a for r in active_rows), (
            f"GD6 REGRESSION — session A's active loan changed after the "
            f"cross-session attempt. rows={rows}"
        )


@pytest.mark.asyncio
async def test_unauthenticated_tool_call_rejected() -> None:
    """A fresh session (no OTP validated) must fail the decorator check
    on every authenticated tool. Pick one representative tool."""
    url = os.environ.get("MCP_SERVER_URL", "http://localhost:8050/sse")
    session_fresh = "integ_sess_fresh"

    async with Client(url) as client:
        resp = await client.call_tool("loan_details", {"session_id": session_fresh})
        text = str(resp.data).lower()
        assert "log in" in text or "generate_otp" in text, (
            f"GD6 REGRESSION — loan_details accepted an unauthenticated " f"session. Got: {text!r}"
        )
