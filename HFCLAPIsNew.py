# import os
# import httpx
# from typing import Optional, Any, Dict

# from Loggers.StdOutLogger import StdoutLogger
# from redis_session_store import RedisSessionStore
# from token_reducer import JsonConverter

# conv = JsonConverter(sep=".")
# log = StdoutLogger(name="hfcl_api")


# def _valid_session_id(session_id: object) -> str:
#     sid = str(session_id).strip() if session_id is not None else ""
#     if not sid or sid.lower() in {"null", "none"}:
#         raise ValueError(f"Invalid session_id: {session_id!r}")
#     return sid


# class HeroFincorpAPIs:
#     """
#     Wraps Bearer endpoints.

#     Output policy (token-safe + token-cheap):
#     - Public methods return VSC (string) ALWAYS.
#     - Token fields are stripped from output.
#     - IMPORTANT: we re-hydrate token/app_id from Redis on every request.
#     """

#     def __init__(
#         self,
#         session_id: str,
#         session_store: Optional[RedisSessionStore] = None,
#         base_url: Optional[str] = None,
#     ):
#         self.session_id = _valid_session_id(session_id)
#         self.logger = log
#         self.base_url = (base_url or os.getenv("CRM_BASE_URL", "http://localhost:8080")).rstrip("/")

#         self.session_store = session_store or RedisSessionStore()

#         # cached (will be refreshed every request)
#         self.bearer_token: Optional[str] = None
#         self.app_id: Optional[str] = None
#         self.loan_id: Optional[str] = None
#         self.phone_number: Optional[str] = None

#         self._hydrate()

#     def _hydrate(self) -> None:
#         s = self.session_store.get(self.session_id) or {}
#         self.bearer_token = s.get("access_token")
#         self.app_id = s.get("app_id")
#         self.loan_id = s.get("loan_id")
#         self.phone_number = s.get("phone_number")

#     def _url(self, path: str) -> str:
#         if not path.startswith("/"):
#             path = "/" + path
#         return f"{self.base_url}{path}"

#     def _headers(self) -> Dict[str, str]:
#         # ALWAYS hydrate before building headers
#         self._hydrate()
#         if not self.bearer_token:
#             return {}
#         return {
#             "Authorization": f"Bearer {self.bearer_token}",
#             "Content-Type": "application/json",
#             "Accept": "application/json",
#         }

#     def _check_context(self) -> Optional[dict]:
#         self._hydrate()
#         if not self.bearer_token:
#             return {"error": "Authentication required. Please log in with OTP first."}
#         if not self.app_id:
#             return {"error": "No app_id found in session. Please log in."}
#         return None

#     # -------------------------
#     # Output helpers: sanitize + VSC
#     # -------------------------
#     @staticmethod
#     def _sanitize(obj: Any) -> Any:
#         """
#         Strip secrets from tool output (never leak tokens) + normalize list-heavy payloads
#         to keep VSC readable.

#         Rules:
#         - Drop token-like fields anywhere.
#         - Recursively sanitize dicts/lists.
#         - If both 'loans' and 'all_loans' exist and are identical lists, drop 'all_loans'
#         (avoids duplicate huge JSON blobs in VSC).
#         - Optionally: if a list is *empty*, keep it as [] (converter will stringify unless exploded).
#         """
#         if isinstance(obj, dict):
#             clean: Dict[str, Any] = {}

#             for k, v in obj.items():
#                 lk = str(k).lower()

#                 # hard drop secrets
#                 if lk in {"access_token", "token", "refresh_token", "id_token", "authorization"}:
#                     continue

#                 clean[k] = HeroFincorpAPIs._sanitize(v)

#             # de-dupe common dashboard shape
#             try:
#                 if "loans" in clean and "all_loans" in clean:
#                     loans_v = clean.get("loans")
#                     all_loans_v = clean.get("all_loans")
#                     if isinstance(loans_v, list) and isinstance(all_loans_v, list):
#                         if loans_v == all_loans_v:
#                             del clean["all_loans"]
#             except Exception:
#                 # never fail sanitize
#                 pass

#             return clean

#         if isinstance(obj, list):
#             return [HeroFincorpAPIs._sanitize(x) for x in obj]

#         return obj

#     def _to_vsc(self, obj: Any, explode_key: Optional[str] = None) -> str:
#         obj = self._sanitize(obj)
#         if not isinstance(obj, (dict, list)):
#             obj = {"value": "" if obj is None else obj}

#         vsc, _ = conv.json_to_vsc_text(
#             obj,
#             include_header=True,
#             preserve_key_order=True,
#             explode_key=explode_key,
#         )
#         return vsc

#     # -------------------------
#     # HTTP plumbing (internal returns JSON-ish)
#     # -------------------------
#     def _handle(self, resp: httpx.Response) -> Any:
#         ok = resp.status_code in (200, 201, 204, 208)
#         ctype = (resp.headers.get("content-type") or "").lower()

#         if ok:
#             try:
#                 out = resp.json()
#                 if isinstance(out, dict):
#                     out.setdefault("status_code", resp.status_code)
#                     return out
#                 return {"status_code": resp.status_code, "data": out}
#             except Exception:
#                 return {"status_code": resp.status_code, "raw": resp.text[:5000], "content_type": ctype}

#         # error path
#         # Cloudflare 5xx returns HTML; keep it trimmed
#         return {
#             "status_code": resp.status_code,
#             "error": resp.text[:5000],
#             "content_type": ctype,
#         }

#     def _request(self, method: str, path: str, json_body: Optional[dict] = None) -> Any:
#         # hydrate before context check
#         self._hydrate()

#         # home usually needs auth too, but allow it to return clean error
#         ctx_err = self._check_context()
#         if ctx_err and path not in ("/herofin-service/home", "/herofin-service/home/"):
#             return ctx_err

#         url = self._url(path)
#         try:
#             timeout = httpx.Timeout(30.0, connect=10.0)
#             with httpx.Client(timeout=timeout, follow_redirects=True) as client:
#                 headers = self._headers()
#                 if not headers:
#                     return {"error": "Authentication Token missing. Please login."}

#                 resp = client.request(method, url, headers=headers, json=json_body)
#                 self.logger.info(f"{method} {url} - {resp.status_code}")
#                 return self._handle(resp)
#         except Exception as e:
#             self.logger.error(f"Request error: {e}")
#             return {"error": str(e)}

#     # -------------------------
#     # REST endpoints (Public: VSC-only)
#     # -------------------------
#     def get_dashboard_home(self) -> str:
#         out = self._request("GET", "/herofin-service/home")
#         if isinstance(out, dict) and out.get("status_code") == 404:
#             out = self._request("GET", "/herofin-service/home/")
#         return self._to_vsc(out, explode_key="loans")

#     def get_loan_details(self) -> str:
#         self._hydrate()
#         if not self.app_id:
#             return self._to_vsc({"error": "No app_id in session."})
#         return self._to_vsc(self._request("GET", f"/herofin-service/loan/details/{self.app_id}/"), explode_key=("loans", "all_loans"))

#     def get_foreclosure_details(self) -> str:
#         self._hydrate()
#         if not self.app_id:
#             return self._to_vsc({"error": "No app_id in session."})
#         return self._to_vsc(self._request("GET", f"/herofin-service/loan/foreclosuredetails/{self.app_id}/"))

#     def get_overdue_details(self) -> str:
#         self._hydrate()
#         if not self.app_id:
#             return self._to_vsc({"error": "No app_id in session."})
#         return self._to_vsc(self._request("GET", f"/herofin-service/loan/overdue-details/{self.app_id}/"))

#     def get_noc_details(self) -> str:
#         self._hydrate()
#         if not self.app_id:
#             return self._to_vsc({"error": "No app_id in session."})
#         return self._to_vsc(self._request("GET", f"/herofin-service/loan/noc-details/{self.app_id}/"))

#     def get_repayment_schedule(self) -> str:
#         """
#         Your curl shows DIRECT works. So:
#         - prefer app_id
#         - fallback to loan_id
#         - explode installments into rows
#         """
#         self._hydrate()
#         if not self.app_id and not self.loan_id:
#             return self._to_vsc({"error": "No app_id/loan_id in session."})

#         candidates = []
#         if self.app_id:
#             candidates.append(str(self.app_id))
#         if self.loan_id:
#             candidates.append(str(self.loan_id))

#         last: Any = None
#         for ident in candidates:
#             for path in (
#                 f"/herofin-service/loan/repayment-schedule/{ident}/",
#                 f"/herofin-service/loan/repayment-schedule/{ident}",
#             ):
#                 out = self._request("GET", path)
#                 last = out
#                 if isinstance(out, dict) and out.get("status_code") in (200, 201):
#                     # explode installments so you get full table (not JSON-in-a-cell)
#                     return self._to_vsc(out, explode_key="installments")
#                 if isinstance(out, dict) and out.get("status_code") == 404:
#                     continue

#         return self._to_vsc({"error": "repayment schedule failed", "tried": candidates, "last": last})

#     def download_welcome_letter(self) -> str:
#         return self._to_vsc(self._request("GET", "/herofin-service/download/welcome-letter/"))

#     def download_soa(self, start_date: str, end_date: str) -> str:
#         payload = {"start_date": start_date, "end_date": end_date}
#         return self._to_vsc(self._request("POST", "/herofin-service/download/soa/", json_body=payload))

#     def initiate_transaction(
#         self,
#         amount: str,
#         otp: str,
#         payment_type: str = "EMI",
#         payment_mode: str = "UPI",
#         latitude: str = "0",
#         longitude: str = "0",
#         emi_count: str = "1",
#     ) -> str:
#         self._hydrate()
#         if not self.app_id:
#             return self._to_vsc({"error": "app_id missing in session"})
#         if not self.phone_number:
#             return self._to_vsc({"error": "phone_number missing in session"})

#         payload = {
#             "phone_number": self.phone_number,
#             "otp": otp,
#             "amount": amount,
#             "paymentType": payment_type,
#             "PaymentMode": payment_mode,
#             "loan_app_id": self.app_id,
#             "latitude": latitude,
#             "longitude": longitude,
#             "emiCount": emi_count,
#         }
#         return self._to_vsc(self._request("POST", "/payments/initiate_transaction/", json_body=payload))

#     def profile_phone_generate_otp(self, new_phone: str) -> str:
#         payload = {"phone_number": new_phone}
#         out = self._request("PUT", "/herofin-service/profiles/?update=phone_number", json_body=payload)
#         return self._to_vsc(out)

#     def profile_phone_validate_otp(self, new_phone: str, otp: str) -> str:
#         payload = {"phone_number": new_phone, "otp": otp}
#         out = self._request("PUT", "/herofin-service/profiles/?update=phone_number", json_body=payload)

#         # Update Redis if token refreshes or phone changes (token never returned to caller)
#         if isinstance(out, dict):
#             token = out.get("access_token") or out.get("token")
#             if token:
#                 self.session_store.update(self.session_id, {"access_token": token, "phone_number": new_phone})
#             elif out.get("status") == "success":
#                 self.session_store.update(self.session_id, {"phone_number": new_phone})

#         return self._to_vsc(out)




import os
import httpx
from typing import Optional, Any, Dict

from Loggers.StdOutLogger import StdoutLogger
from redis_session_store import RedisSessionStore
from token_reducer import JsonConverter, ToonOptions

conv = JsonConverter(sep=".")
log = StdoutLogger(name="hfcl_api")


def _valid_session_id(session_id: object) -> str:
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid


class HeroFincorpAPIs:
    """
    Wraps Bearer endpoints.

    Output policy (token-safe + token-cheap):
    - Public methods return TOON (string) by default (token-optimized, structure-preserving).
    - If TOON unavailable, fallback to VSC (CSV-like text).
    - Token fields are stripped from output.
    - IMPORTANT: we re-hydrate token/app_id from Redis on every request.
    """

    def __init__(
        self,
        session_id: str,
        session_store: Optional[RedisSessionStore] = None,
        base_url: Optional[str] = None,
    ):
        self.session_id = _valid_session_id(session_id)
        self.logger = log
        self.base_url = (base_url or os.getenv("CRM_BASE_URL", "http://localhost:8080")).rstrip("/")

        self.session_store = session_store or RedisSessionStore()

        # cached (will be refreshed every request)
        self.bearer_token: Optional[str] = None
        self.app_id: Optional[str] = None
        self.loan_id: Optional[str] = None
        self.phone_number: Optional[str] = None

        self._hydrate()

    def _hydrate(self) -> None:
        s = self.session_store.get(self.session_id) or {}
        self.bearer_token = s.get("access_token")
        self.app_id = s.get("app_id")
        self.loan_id = s.get("loan_id")
        self.phone_number = s.get("phone_number")

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _headers(self) -> Dict[str, str]:
        # ALWAYS hydrate before building headers
        self._hydrate()
        if not self.bearer_token:
            return {}
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _check_context(self) -> Optional[dict]:
        self._hydrate()
        if not self.bearer_token:
            return {"error": "Authentication required. Please log in with OTP first."}
        if not self.app_id:
            return {"error": "No app_id found in session. Please log in."}
        return None

    # -------------------------
    # Output helpers: sanitize + VSC/TOON
    # -------------------------
    @staticmethod
    def _sanitize(obj: Any) -> Any:
        """
        Strip secrets from tool output (never leak tokens) + normalize list-heavy payloads
        to keep text output readable.

        Rules:
        - Drop token-like fields anywhere.
        - Recursively sanitize dicts/lists.
        - If both 'loans' and 'all_loans' exist and are identical lists, drop 'all_loans'
          (avoids duplicate huge JSON blobs).
        - If a list is empty, keep it as [] (converter will stringify unless exploded).
        """
        if isinstance(obj, dict):
            clean: Dict[str, Any] = {}

            for k, v in obj.items():
                lk = str(k).lower()

                # hard drop secrets
                if lk in {"access_token", "token", "refresh_token", "id_token", "authorization"}:
                    continue

                clean[k] = HeroFincorpAPIs._sanitize(v)

            # de-dupe common dashboard shape
            try:
                if "loans" in clean and "all_loans" in clean:
                    loans_v = clean.get("loans")
                    all_loans_v = clean.get("all_loans")
                    if isinstance(loans_v, list) and isinstance(all_loans_v, list):
                        if loans_v == all_loans_v:
                            del clean["all_loans"]
            except Exception:
                # never fail sanitize
                pass

            return clean

        if isinstance(obj, list):
            return [HeroFincorpAPIs._sanitize(x) for x in obj]

        return obj

    def _to_vsc(self, obj: Any, explode_key: Optional[str] = None) -> str:
        """
        Legacy/CSV-friendly output: sanitized JSON -> VSC (CSV text, header + rows).
        Kept as fallback and for non-LLM consumers.
        """
        obj = self._sanitize(obj)
        if not isinstance(obj, (dict, list)):
            obj = {"value": "" if obj is None else obj}

        vsc, _ = conv.json_to_vsc_text(
            obj,
            include_header=True,
            preserve_key_order=True,
            explode_key=explode_key,
        )
        return vsc

    def _to_toon(self, obj: Any, options: Optional[ToonOptions] = None) -> str:
        """
        Structure-preserving TOON output:
        - sanitize -> pass nested JSON as-is to TOON encoder
        - NO flattening, NO explode_key, NO tabular reshaping
        - Falls back to JSON (pretty) if TOON unavailable
        """
        obj = self._sanitize(obj)

        # Ensure top-level is JSON-serializable object/array
        if not isinstance(obj, (dict, list)):
            obj = {"value": "" if obj is None else obj}

        try:
            return conv.json_to_toon_text(
                obj,
                options=options or ToonOptions(
                    delimiter="|",
                    indent=2,
                    length_marker=""  # no length markers to stay close to YAML-like output
                ),
            )
        except RuntimeError:
            # Hard fallback: pretty JSON so nesting is still 100% intact
            import json
            self.logger.warning("TOON unavailable, falling back to pretty JSON")
            return json.dumps(obj, ensure_ascii=False, indent=2)

    # -------------------------
    # HTTP plumbing (internal returns JSON-ish)
    # -------------------------
    def _handle(self, resp: httpx.Response) -> Any:
        ok = resp.status_code in (200, 201, 204, 208)
        ctype = (resp.headers.get("content-type") or "").lower()

        if ok:
            try:
                out = resp.json()
                if isinstance(out, dict):
                    out.setdefault("status_code", resp.status_code)
                    return out
                return {"status_code": resp.status_code, "data": out}
            except Exception:
                return {"status_code": resp.status_code, "raw": resp.text[:5000], "content_type": ctype}

        # error path
        # Cloudflare 5xx returns HTML; keep it trimmed
        return {
            "status_code": resp.status_code,
            "error": resp.text[:5000],
            "content_type": ctype,
        }

    def _request(self, method: str, path: str, json_body: Optional[dict] = None) -> Any:
        # hydrate before context check
        self._hydrate()

        # home usually needs auth too, but allow it to return clean error
        ctx_err = self._check_context()
        if ctx_err and path not in ("/herofin-service/home", "/herofin-service/home/"):
            return ctx_err

        url = self._url(path)
        try:
            timeout = httpx.Timeout(30.0, connect=10.0)
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                headers = self._headers()
                if not headers:
                    return {"error": "Authentication Token missing. Please login."}

                resp = client.request(method, url, headers=headers, json=json_body)
                self.logger.info(f"{method} {url} - {resp.status_code}")
                return self._handle(resp)
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return {"error": str(e)}
        
    @staticmethod
    def _force_nested_loans(obj: Any) -> Any:
        """
        Make `loans` non-tabular for TOON so it renders as a nested list instead of a table.
        """
        if isinstance(obj, dict) and isinstance(obj.get("loans"), list):
            new_obj = dict(obj)
            new_obj["loans"] = [{"loan": l} for l in obj["loans"]]
            return new_obj
        return obj

    # -------------------------
    # REST endpoints (Public: TOON-first, fallback VSC)
    # -------------------------
    def get_dashboard_home(self) -> str:
        out = self._request("GET", "/herofin-service/home")
        if isinstance(out, dict) and out.get("status_code") == 404:
            out = self._request("GET", "/herofin-service/home/")
        # sanitize once, then force nested loans, then TOON
        out = self._sanitize(out)
        out = self._force_nested_loans(out)
        return self._to_toon(out)

    def get_loan_details(self) -> str:
        self._hydrate()
        if not self.app_id:
            return self._to_toon({"error": "No app_id in session."})
        out = self._request("GET", f"/herofin-service/loan/details/{self.app_id}/")
        # 'loans' / 'all_loans' deduped in _sanitize; structure preserved in TOON.
        return self._to_toon(out)

    def get_foreclosure_details(self) -> str:
        self._hydrate()
        if not self.app_id:
            return self._to_toon({"error": "No app_id in session."})
        out = self._request("GET", f"/herofin-service/loan/foreclosuredetails/{self.app_id}/")
        return self._to_toon(out)

    def get_overdue_details(self) -> str:
        self._hydrate()
        if not self.app_id:
            return self._to_toon({"error": "No app_id in session."})
        out = self._request("GET", f"/herofin-service/loan/overdue-details/{self.app_id}/")
        return self._to_toon(out)

    def get_noc_details(self) -> str:
        self._hydrate()
        if not self.app_id:
            return self._to_toon({"error": "No app_id in session."})
        out = self._request("GET", f"/herofin-service/loan/noc-details/{self.app_id}/")
        return self._to_toon(out)

    def get_repayment_schedule(self) -> str:
        """
        Your curl shows DIRECT works. So:
        - prefer app_id
        - fallback to loan_id
        - For TOON, keep installments as a nested list; models can parse tabular rows.
        """
        self._hydrate()
        if not self.app_id and not self.loan_id:
            return self._to_toon({"error": "No app_id/loan_id in session."})

        candidates = []
        if self.app_id:
            candidates.append(str(self.app_id))
        if self.loan_id:
            candidates.append(str(self.loan_id))

        last: Any = None
        for ident in candidates:
            for path in (
                f"/herofin-service/loan/repayment-schedule/{ident}/",
                f"/herofin-service/loan/repayment-schedule/{ident}",
            ):
                out = self._request("GET", path)
                last = out
                if isinstance(out, dict) and out.get("status_code") in (200, 201):
                    # Let TOON encode installments as a table-like array, no explode needed.
                    return self._to_toon(out)
                if isinstance(out, dict) and out.get("status_code") == 404:
                    continue

        return self._to_toon({"error": "repayment schedule failed", "tried": candidates, "last": last})

    def download_welcome_letter(self) -> str:
        out = self._request("GET", "/herofin-service/download/welcome-letter/")
        return self._to_toon(out)

    def download_soa(self, start_date: str, end_date: str) -> str:
        payload = {"start_date": start_date, "end_date": end_date}
        out = self._request("POST", "/herofin-service/download/soa/", json_body=payload)
        return self._to_toon(out)

    def initiate_transaction(
        self,
        amount: str,
        otp: str,
        payment_type: str = "EMI",
        payment_mode: str = "UPI",
        latitude: str = "0",
        longitude: str = "0",
        emi_count: str = "1",
    ) -> str:
        self._hydrate()
        if not self.app_id:
            return self._to_toon({"error": "app_id missing in session"})
        if not self.phone_number:
            return self._to_toon({"error": "phone_number missing in session"})

        payload = {
            "phone_number": self.phone_number,
            "otp": otp,
            "amount": amount,
            "paymentType": payment_type,
            "PaymentMode": payment_mode,
            "loan_app_id": self.app_id,
            "latitude": latitude,
            "longitude": longitude,
            "emiCount": emi_count,
        }
        out = self._request("POST", "/payments/initiate_transaction/", json_body=payload)
        return self._to_toon(out)

    def profile_phone_generate_otp(self, new_phone: str) -> str:
        payload = {"phone_number": new_phone}
        out = self._request("PUT", "/herofin-service/profiles/?update=phone_number", json_body=payload)
        return self._to_toon(out)

    def profile_phone_validate_otp(self, new_phone: str, otp: str) -> str:
        payload = {"phone_number": new_phone, "otp": otp}
        out = self._request("PUT", "/herofin-service/profiles/?update=phone_number", json_body=payload)

        # Update Redis if token refreshes or phone changes (token never returned to caller)
        if isinstance(out, dict):
            token = out.get("access_token") or out.get("token")
            if token:
                self.session_store.update(self.session_id, {"access_token": token, "phone_number": new_phone})
            elif out.get("status") == "success":
                self.session_store.update(self.session_id, {"phone_number": new_phone})

        return self._to_toon(out)
