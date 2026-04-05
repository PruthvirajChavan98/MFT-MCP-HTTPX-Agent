from __future__ import annotations

import asyncio
import json as _json
import logging
import uuid
from typing import Any, Dict, Optional

import httpx

from .config import CRM_BASE_URL, DOWNLOAD_PROXY_BASE_URL, DOWNLOAD_TOKEN_TTL_SECONDS
from .session_store import RedisSessionStore
from .session_store import valid_session_id as _valid_session_id
from .utils import JsonConverter, ToonOptions

conv = JsonConverter(sep=".")
log = logging.getLogger(name="mft_api")

_CRM_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)

# ---------------------------------------------------------------------------
# Module-level async HTTP client singleton
# ---------------------------------------------------------------------------
_http_client: httpx.AsyncClient | None = None
_http_lock = asyncio.Lock()


async def _get_http_client() -> httpx.AsyncClient:
    global _http_client

    if _http_client is not None:
        return _http_client

    async with _http_lock:
        if _http_client is None:
            _http_client = httpx.AsyncClient(
                timeout=_CRM_TIMEOUT,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
            log.info("Initialized async HTTP client for core API")
    return _http_client


async def _close_http_client() -> None:
    global _http_client

    async with _http_lock:
        if _http_client is not None:
            await _http_client.aclose()
            _http_client = None
            log.info("Closed async HTTP client for core API")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Core CRM API wrapper — fully async
# ---------------------------------------------------------------------------
class MockFinTechAPIs:
    def __init__(self, session_id: str, session_store: Optional[RedisSessionStore] = None):
        self.session_id = _valid_session_id(session_id)
        self.logger = log
        self.base_url = CRM_BASE_URL
        self.session_store = session_store or RedisSessionStore()
        self.bearer_token: Optional[str] = None
        self.app_id: Optional[str] = None
        self.loan_id: Optional[str] = None
        self.phone_number: Optional[str] = None
        self._hydrated: bool = False

    async def _hydrate(self) -> None:
        """Load session state from Redis once per instance lifetime."""
        if self._hydrated:
            return
        s = await self.session_store.get(self.session_id) or {}
        self.bearer_token = s.get("access_token")
        self.app_id = s.get("app_id")
        self.loan_id = s.get("loan_id")
        self.phone_number = s.get("phone_number")
        self._hydrated = True

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    async def _headers(self) -> Dict[str, str]:
        await self._hydrate()
        if not self.bearer_token:
            return {}
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _check_context(self) -> Optional[dict]:
        await self._hydrate()
        if not self.bearer_token:
            return {"error": "Auth token missing."}
        if not self.app_id:
            s = await self.session_store.get(self.session_id) or {}
            if s.get("loans"):
                return {
                    "error": "No loan selected. Call list_loans() then select_loan(loan_number)."
                }
            return {"error": "app_id missing."}
        return None

    def _to_toon(self, obj: Any) -> str:
        if not isinstance(obj, (dict, list)):
            obj = {"value": obj}
        try:
            return conv.json_to_toon_text(
                obj, options=ToonOptions(delimiter="|", indent=2, length_marker="")
            )
        except RuntimeError:
            return _json.dumps(obj, indent=2)

    async def _download(
        self,
        method: str,
        path: str,
        doc_type: str,
        json_body: Optional[dict] = None,
        require_app_id: bool = False,
    ) -> dict:
        await self._hydrate()
        if not self.bearer_token:
            return {"error": "Auth token missing."}
        if require_app_id:
            ctx_err = await self._check_context()
            if ctx_err:
                return ctx_err

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": "application/pdf",
        }
        if json_body:
            headers["Content-Type"] = "application/json"

        try:
            client = await _get_http_client()
            async with client.stream(
                method, self._url(path), headers=headers, json=json_body
            ) as resp:
                self.logger.info("%s %s - %d", method, path, resp.status_code)

                if resp.status_code not in (200, 201):
                    await resp.aread()
                    try:
                        err = resp.json()
                    except Exception:
                        err = resp.text[:1000]
                    return {"error": err, "status_code": resp.status_code}

                hint = resp.headers.get("x-password-hint", "")
                disposition = resp.headers.get("content-disposition", "")
                filename = ""
                if 'filename="' in disposition:
                    filename = disposition.split('filename="')[1].rstrip('"')

            # CRM confirmed the document is available — generate a one-time
            # download token so the user can fetch the PDF via a browser link.
            token = uuid.uuid4().hex
            redis_key = f"dl_token:{token}"
            token_payload = _json.dumps(
                {
                    "bearer_token": self.bearer_token,
                    "method": method,
                    "path": path,
                    "json_body": _json.dumps(json_body) if json_body else None,
                    "doc_type": doc_type,
                    "filename": filename,
                    "password_hint": hint,
                }
            )
            await self.session_store.set_raw(
                redis_key, token_payload, ex=DOWNLOAD_TOKEN_TTL_SECONDS
            )

            download_url = f"{DOWNLOAD_PROXY_BASE_URL}/api/download/{token}"

            return {
                "status": "ready",
                "document_type": doc_type,
                "download_url": download_url,
                "password_hint": hint,
                "filename": filename,
            }
        except Exception as e:
            return {"error": str(e)}

    async def _request(self, method: str, path: str, json_body: Optional[dict] = None) -> Any:
        await self._hydrate()
        ctx_err = await self._check_context()
        if ctx_err and "home" not in path:
            return ctx_err

        try:
            client = await _get_http_client()
            resp = await client.request(
                method, self._url(path), headers=await self._headers(), json=json_body
            )
            self.logger.info("%s %s - %d", method, path, resp.status_code)
            try:
                return resp.json()
            except Exception:
                return {"status_code": resp.status_code, "raw": resp.text[:1000]}
        except Exception as e:
            return {"error": str(e)}

    async def get_dashboard_home(self) -> str:
        return self._to_toon(await self._request("GET", "/mockfin-service/home"))

    async def get_loan_details(self) -> str:
        if not self.app_id:
            await self._hydrate()
        if not self.app_id:
            return self._to_toon({"error": "No app_id"})
        return self._to_toon(
            await self._request("GET", f"/mockfin-service/loan/details/{self.app_id}/")
        )

    async def get_foreclosure_details(self) -> str:
        if not self.app_id:
            await self._hydrate()
        if not self.app_id:
            return self._to_toon({"error": "No app_id"})
        return self._to_toon(
            await self._request("GET", f"/mockfin-service/loan/foreclosuredetails/{self.app_id}/")
        )

    async def get_overdue_details(self) -> str:
        if not self.app_id:
            await self._hydrate()
        if not self.app_id:
            return self._to_toon({"error": "No app_id"})
        return self._to_toon(
            await self._request("GET", f"/mockfin-service/loan/overdue-details/{self.app_id}/")
        )

    async def get_noc_details(self) -> str:
        if not self.app_id:
            await self._hydrate()
        if not self.app_id:
            return self._to_toon({"error": "No app_id"})
        return self._to_toon(
            await self._request("GET", f"/mockfin-service/loan/noc-details/{self.app_id}/")
        )

    async def get_repayment_schedule(self) -> str:
        if not self.app_id:
            await self._hydrate()
        ident = self.app_id or self.loan_id
        if not ident:
            return self._to_toon({"error": "No app_id/loan_id"})
        return self._to_toon(
            await self._request("GET", f"/mockfin-service/loan/repayment-schedule/{ident}/")
        )

    async def download_welcome_letter(self) -> str:
        result = await self._download(
            "GET", "/mockfin-service/download/welcome-letter/", doc_type="welcome-letter"
        )
        if "error" not in result:
            return self._to_toon(result)
        # CRM unavailable in demo — generate mock letter from loan details
        loan: dict = {}
        if not self.app_id:
            await self._hydrate()
        if self.app_id:
            raw = await self._request("GET", f"/mockfin-service/loan/details/{self.app_id}/")
            if isinstance(raw, dict) and "error" not in raw:
                loan = raw
        return self._to_toon(self._build_mock_welcome_letter(loan))

    def _build_mock_welcome_letter(self, loan: dict) -> dict:
        import datetime

        loan_no = (
            loan.get("loan_number") or loan.get("applicationId") or self.app_id or "RNTWL-XXXXXX"
        )
        amount = loan.get("loanAmount") or loan.get("sanctionedAmount") or "₹X,XX,XXX"
        tenure = loan.get("tenure") or loan.get("loanTenure") or "XX months"
        rate = loan.get("roi") or loan.get("interestRate") or "X.XX%"
        emi = loan.get("emi") or loan.get("monthlyEMI") or "₹X,XXX"
        issued = datetime.date.today().strftime("%d %B %Y")
        phone = self.phone_number or "XXXXXXXXXX"

        content = f"""## Welcome Letter — Mock Fin Tech

**Date:** {issued} | **Loan Number:** {loan_no} | **Mobile:** {phone}

---

Dear Valued Customer,

We are pleased to welcome you as a customer of **Mock Fin Tech** and thank you for choosing us for your financing needs.

### Loan Sanction Summary

| Field | Details |
|---|---|
| Loan Number | {loan_no} |
| Sanctioned Amount | {amount} |
| Tenure | {tenure} |
| Rate of Interest | {rate} p.a. |
| Monthly EMI | {emi} |

### Important Notes

- Your EMI will be debited on the due date from your registered bank account.
- For queries, visit [mockfintech.example/servicing](https://mockfintech.example/servicing) or call **1800-XXX-XXXX** (toll-free).
- Please keep this letter for your records.

Yours sincerely,
**Mock Fin Tech — Customer Relations**

*This is a mock document generated for demonstration purposes only. It does not constitute a legal agreement.*
"""
        return {
            "status": "ready",
            "document_type": "welcome-letter",
            "note": "Mock letter generated (PDF endpoint unavailable in demo environment)",
            "content": content,
        }

    async def download_soa(self, start_date: str, end_date: str) -> str:
        if not self.app_id:
            await self._hydrate()
        if not self.app_id:
            return self._to_toon(
                {"error": "No loan selected. Call list_loans() then select_loan(loan_number)."}
            )
        result = await self._download(
            "POST",
            "/mockfin-service/download/soa/",
            doc_type="soa",
            json_body={"app_id": self.app_id, "start_date": start_date, "end_date": end_date},
        )
        if "error" not in result:
            return self._to_toon(result)
        # CRM unavailable in demo — generate mock SOA from loan + repayment schedule
        loan: dict = {}
        schedule: dict = {}
        raw_loan = await self._request("GET", f"/mockfin-service/loan/details/{self.app_id}/")
        if isinstance(raw_loan, dict) and "error" not in raw_loan:
            loan = raw_loan
        raw_sched = await self._request(
            "GET", f"/mockfin-service/loan/repayment-schedule/{self.app_id}/"
        )
        if isinstance(raw_sched, dict) and "error" not in raw_sched:
            schedule = raw_sched
        return self._to_toon(self._build_mock_soa(start_date, end_date, loan, schedule))

    def _build_mock_soa(self, start_date: str, end_date: str, loan: dict, schedule: dict) -> dict:
        import datetime

        loan_no = (
            loan.get("loan_number") or loan.get("applicationId") or self.app_id or "RNTWL-XXXXXX"
        )
        amount = loan.get("loanAmount") or loan.get("sanctionedAmount") or "—"
        rate = loan.get("roi") or loan.get("interestRate") or "—"
        phone = self.phone_number or "XXXXXXXXXX"
        issued = datetime.date.today().strftime("%d %B %Y")

        # Parse date bounds
        start_dt: datetime.date | None = None
        end_dt: datetime.date | None = None
        try:
            start_dt = datetime.date.fromisoformat(start_date)
            end_dt = datetime.date.fromisoformat(end_date)
        except ValueError:
            pass

        # Extract instalment rows from repayment schedule that fall in range
        rows: list[dict] = []
        # The CRM may nest instalments under various keys; try common ones
        for key in ("instalments", "installments", "schedule", "repaymentSchedule", "data"):
            candidate = schedule.get(key)
            if isinstance(candidate, list):
                rows = candidate
                break
        if not rows and isinstance(schedule, list):
            rows = schedule  # type: ignore[assignment]

        tx_lines: list[str] = []
        for row in rows:
            due_str = row.get("dueDate") or row.get("due_date") or row.get("date") or ""
            try:
                due_dt = datetime.date.fromisoformat(str(due_str)[:10])
            except (ValueError, TypeError):
                continue
            if start_dt and end_dt and not (start_dt <= due_dt <= end_dt):
                continue
            debit = row.get("emi") or row.get("amount") or row.get("instalment") or "—"
            credit = row.get("paid") or row.get("amountPaid") or "—"
            status = row.get("status") or ""
            tx_lines.append(f"| {due_str} | EMI instalment | {debit} | {credit} | {status} |")

        if not tx_lines:
            tx_lines = ["| — | No transactions in selected period | — | — | — |"]

        tx_table = "\n".join(tx_lines)

        content = f"""## Statement of Account — Mock Fin Tech

**As of:** {issued} | **Account:** {loan_no} | **Mobile:** {phone}
**Period:** {start_date} to {end_date}

---

### Account Summary

| Field | Details |
|---|---|
| Loan Number | {loan_no} |
| Sanctioned Amount | {amount} |
| Rate of Interest | {rate} p.a. |

---

### Transaction History

| Date | Description | Debit | Credit | Status |
|---|---|---|---|---|
{tx_table}

---

*This is a mock statement generated for demonstration purposes only.*
"""
        return {
            "status": "ready",
            "document_type": "soa",
            "note": "Mock SOA generated (PDF endpoint unavailable in demo environment)",
            "content": content,
        }

    async def initiate_transaction(self, amount: str, otp: str, payment_mode: str = "UPI") -> str:
        if not self.app_id:
            await self._hydrate()
        payload = {
            "phone_number": self.phone_number,
            "otp": otp,
            "amount": amount,
            "PaymentMode": payment_mode,
            "loan_app_id": self.app_id,
        }
        return self._to_toon(
            await self._request("POST", "/payments/initiate_transaction/", json_body=payload)
        )

    async def profile_phone_generate_otp(self, new_phone: str) -> str:
        return self._to_toon(
            await self._request(
                "PUT",
                "/mockfin-service/profiles/?update=phone_number",
                json_body={"phone_number": new_phone},
            )
        )

    async def profile_phone_validate_otp(self, new_phone: str, otp: str) -> str:
        return self._to_toon(
            await self._request(
                "PUT",
                "/mockfin-service/profiles/?update=phone_number",
                json_body={"phone_number": new_phone, "otp": otp},
            )
        )
