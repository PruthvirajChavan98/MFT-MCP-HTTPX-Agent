from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


class SessionContextError(ValueError):
    """Raised when a raw session dict cannot produce a well-formed
    SessionContext (missing identity anchors, malformed loans, etc.).

    Callers at the decorator boundary catch this and surface the
    canonical AUTH_REJECT_MESSAGE rather than leaking the underlying
    defect to the caller or to logs-as-error-messages.
    """


@dataclass(frozen=True, slots=True)
class LoanRef:
    loan_number: str
    status: str | None
    product_code: str | None
    raw: Mapping[str, Any]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LoanRef":
        loan_number = str(data.get("loan_number", "")).strip()
        if not loan_number:
            raise SessionContextError("LoanRef requires non-empty loan_number")
        status_val = data.get("status")
        product_val = data.get("product_code")
        return cls(
            loan_number=loan_number,
            status=str(status_val) if status_val is not None else None,
            product_code=str(product_val) if product_val is not None else None,
            raw=MappingProxyType(dict(data)),
        )


@dataclass(frozen=True, slots=True)
class SessionContext:
    session_id: str
    customer_id: str
    phone_number: str
    access_token: str
    loans: tuple[LoanRef, ...]
    app_id: str | None
    user_details: Mapping[str, Any]

    @classmethod
    def from_session_dict(cls, session_id: str, raw: Mapping[str, Any]) -> "SessionContext":
        """Construct a SessionContext from a raw Redis session dict.

        The caller MUST have already asserted auth_state == "authenticated"
        — this factory builds the typed view, not the auth decision.

        Raises SessionContextError when any required identity anchor is
        missing or malformed. The decorator catches the error and maps
        it to AUTH_REJECT_MESSAGE.
        """
        customer_id = str(raw.get("customer_id", "")).strip()
        phone_number = str(raw.get("phone_number", "")).strip()
        access_token = str(raw.get("access_token", "")).strip()
        if not customer_id:
            raise SessionContextError("session missing customer_id")
        if not phone_number:
            raise SessionContextError("session missing phone_number")
        if not access_token:
            raise SessionContextError("session missing access_token")

        loans_raw = raw.get("loans") or []
        if not isinstance(loans_raw, list):
            raise SessionContextError("session.loans must be a list")
        loans = tuple(LoanRef.from_dict(entry) for entry in loans_raw if isinstance(entry, dict))

        app_id_raw = raw.get("app_id")
        app_id = str(app_id_raw).strip() if app_id_raw else None
        app_id = app_id or None

        user_details_raw = raw.get("user_details") or {}
        if not isinstance(user_details_raw, dict):
            user_details_raw = {}

        return cls(
            session_id=session_id,
            customer_id=customer_id,
            phone_number=phone_number,
            access_token=access_token,
            loans=loans,
            app_id=app_id,
            user_details=MappingProxyType(dict(user_details_raw)),
        )
