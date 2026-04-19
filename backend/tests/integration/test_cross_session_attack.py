"""Live cross-session attack test (GD6 Phase R3, RR2 auto-discovery).

Automates the semi-manual verification step from the GD6 plan. Two
customer sessions authenticate against the running mock CRM, then
session A tries to reference session B's loan via ``select_loan``. The
test asserts the MCP tool returns the canonical ownership-rejection
string and — critically — that session A's ``app_id`` is NOT flipped
to B's loan number.

Run with the stack up:

    make local-up
    make -C backend test-integration
    # or manually:
    MCP_SERVER_URL=http://localhost:8050/sse \\
        uv run pytest tests/integration/ -m integration -v

## Phone discovery

If ``INTEGRATION_PHONE_A`` / ``INTEGRATION_PHONE_B`` are set, they
win. Otherwise the test probes a fixed pool of known mock-CRM seeds
(``_PROBE_POOL`` below) and auto-selects the first two that the CRM
accepts. Fewer than two acceptable phones → skip with a clear
message pointing at the env-var override.

## OTP delivery

The mock CRM accepts any OTP ``INTEGRATION_OTP_BYPASS`` value
(default ``123456``, matching the mock CRM's development bypass).
"""

from __future__ import annotations

import os

import pytest
from fastmcp import Client

pytestmark = pytest.mark.integration


# Known-good probe pool — phones that the mock CRM at
# test-mock-crm.pruthvirajchavan.codes has seeded with distinct
# customers + loans. Extend when the mock seed set changes. Tests
# that need two distinct customers will pick the first two that
# pass `generate_otp`.
_PROBE_POOL: tuple[str, ...] = (
    "9000000001",
    "9000000002",
    "9000000003",
    "9999900001",
    "9999900002",
)

_DEFAULT_OTP_BYPASS = "123456"


def _otp_bypass() -> str:
    return (
        os.environ.get("INTEGRATION_OTP_BYPASS", _DEFAULT_OTP_BYPASS).strip() or _DEFAULT_OTP_BYPASS
    )


async def _phone_is_accepted(client: Client, phone: str) -> bool:
    """True when the mock CRM's generate_otp for ``phone`` succeeds."""
    try:
        resp = await client.call_tool(
            "generate_otp",
            {"user_input": phone, "session_id": f"probe_{phone}"},
        )
    except Exception:
        return False
    text = str(resp.data).lower()
    return "otp" in text and "sent" in text


async def _discover_two_phones(client: Client) -> tuple[str, str]:
    """Return two phones the mock CRM accepts.

    Order of precedence:
    1. Env vars ``INTEGRATION_PHONE_A`` and ``INTEGRATION_PHONE_B``
       (both required if set).
    2. Probe ``_PROBE_POOL`` in order; pick the first two successes.

    Skips the test with a useful message if neither path yields two
    distinct phones."""
    env_a = os.environ.get("INTEGRATION_PHONE_A", "").strip()
    env_b = os.environ.get("INTEGRATION_PHONE_B", "").strip()
    if env_a and env_b and env_a != env_b:
        return env_a, env_b

    accepted: list[str] = []
    for phone in _PROBE_POOL:
        if await _phone_is_accepted(client, phone):
            accepted.append(phone)
        if len(accepted) >= 2:
            return accepted[0], accepted[1]

    pytest.skip(
        "Could not auto-discover two phones the mock CRM accepts. "
        "Probed: {pool}. Set INTEGRATION_PHONE_A and INTEGRATION_PHONE_B "
        "to override.".format(pool=", ".join(_PROBE_POOL))
    )


async def _authenticate_session(client: Client, session_id: str, phone: str) -> list[dict]:
    """Run the full OTP flow for one session; return the loans list."""
    otp = _otp_bypass()
    gen = await client.call_tool("generate_otp", {"user_input": phone, "session_id": session_id})
    assert (
        "OTP" in str(gen.data) or "sent" in str(gen.data).lower()
    ), f"generate_otp failed for {phone}: {gen.data!r}"

    val = await client.call_tool("validate_otp", {"otp": otp, "session_id": session_id})
    val_text = str(val.data)
    assert (
        "success" in val_text.lower() or "Logged in" in val_text
    ), f"validate_otp failed for {phone} with OTP {otp}: {val_text!r}"

    loans_resp = await client.call_tool("list_loans", {"session_id": session_id})
    loans_text = str(loans_resp.data)
    rows = [r for r in loans_text.split("\n") if "|" in r][1:]
    loans = [{"loan_number": r.split("|")[0]} for r in rows if r.split("|")[0].strip()]
    assert loans, f"no loans returned for {phone}; got {loans_text!r}"
    return loans


@pytest.mark.asyncio
async def test_cross_session_select_loan_rejected() -> None:
    url = os.environ.get("MCP_SERVER_URL", "http://localhost:8050/sse")
    session_a = "integ_sess_a"
    session_b = "integ_sess_b"

    async with Client(url) as client:
        phone_a, phone_b = await _discover_two_phones(client)

        loans_a = await _authenticate_session(client, session_a, phone_a)
        loans_b = await _authenticate_session(client, session_b, phone_b)

        loan_a = loans_a[0]["loan_number"]
        loan_b = loans_b[0]["loan_number"]
        if loan_a == loan_b:
            pytest.skip(
                f"Both discovered phones own the same loan ({loan_a}). "
                f"Cross-session test needs distinct loans — set "
                f"INTEGRATION_PHONE_A/B to phones with disjoint loans."
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
