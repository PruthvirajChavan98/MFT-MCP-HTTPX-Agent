# Architectural Audit Remediation — Complete Code Diff

**Branches:** `refactor/architectural-audit-remediation`, `fix/final-audit-remediation`  
**Date:** 2026-04-05 — 2026-04-06  
**Backend Tests:** 149/149 passing  
**Frontend Tests:** 92/92 passing (23 test files)  
**Commits:** 3 (`3f9a15a` refactor, `b9e1861` server hydration, `99093c4` final fixes)

---

## Table of Contents

- [Backend Phase 0: Immediate Safety](#phase-0)
- [Backend Phase 1: Data Layer Extraction](#phase-1)
- [Backend Phase 2: Shadow Eval Decomposition](#phase-2)
- [Backend Phase 4: Dead Code & Cleanup](#phase-4)
- [Backend Phase 5: Structural Refactor](#phase-5)
- [Backend Post-Audit: _hydrate() Fix](#post-audit)
- [Frontend Phase 1: Purge Unused shadcn/ui](#fe-phase-1)
- [Frontend Phase 2: KnowledgeBasePage Extraction](#fe-phase-2)
- [Frontend Phase 3: GuardrailsPage Extraction](#fe-phase-3)
- [Frontend Phase 4-5: Data Extraction + API Typing](#fe-phase-4-5)
- [Server-Side Chat Hydration — localStorage → Checkpointer](#server-hydration)
- [Final Audit Fixes — Redis Singleton + CRM Client + Error Parsing](#final-fixes)

---

<a id="phase-0"></a>
## Backend Phase 0: Immediate Safety — MCP Async + Rate Limiter + Creds

### config.py — Rate limiter: fail_open → fail_closed
```diff
diff --git a/backend/src/agent_service/core/config.py b/backend/src/agent_service/core/config.py
index 4e74960..fcca31f 100644
--- a/backend/src/agent_service/core/config.py
+++ b/backend/src/agent_service/core/config.py
@@ -134,7 +134,9 @@ RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "t
 RATE_LIMIT_ALGORITHM = os.getenv("RATE_LIMIT_ALGORITHM", "sliding_window").strip().lower()
 
 # Failure mode: "fail_open" (allow on Redis failure) or "fail_closed" (deny on Redis failure)
-RATE_LIMIT_FAILURE_MODE = os.getenv("RATE_LIMIT_FAILURE_MODE", "fail_open").strip().lower()
+# Default: fail_closed — denies requests when Redis is unreachable to protect LLM API budgets.
+# Set RATE_LIMIT_FAILURE_MODE=fail_open explicitly if availability is preferred over safety.
+RATE_LIMIT_FAILURE_MODE = os.getenv("RATE_LIMIT_FAILURE_MODE", "fail_closed").strip().lower()
 
 # Redis timeout for rate limit operations (seconds)
 RATE_LIMIT_REDIS_TIMEOUT = float(os.getenv("RATE_LIMIT_REDIS_TIMEOUT", "1.0"))
```

### session_store.py — Full async rewrite (redis.asyncio, lazy pool)
```diff
diff --git a/backend/src/mcp_service/session_store.py b/backend/src/mcp_service/session_store.py
index a299848..7f55005 100644
--- a/backend/src/mcp_service/session_store.py
+++ b/backend/src/mcp_service/session_store.py
@@ -1,13 +1,23 @@
+from __future__ import annotations
+
+import asyncio
 import json
 import logging
-from typing import Optional, cast
+from typing import Any, Optional
 
-import redis
+from redis.asyncio import ConnectionPool, Redis as AsyncRedis
 
 from .config import REDIS_URL
 
 log = logging.getLogger(name="redis_session_store")
 
+# ---------------------------------------------------------------------------
+# Module-level async Redis singleton (lazy initialisation)
+# ---------------------------------------------------------------------------
+_pool: Optional[ConnectionPool] = None
+_client: Optional[AsyncRedis] = None
+_lock = asyncio.Lock()
+
 
 def _redact_uri(uri: str) -> str:
     try:
@@ -22,20 +32,71 @@ def _redact_uri(uri: str) -> str:
     return uri
 
 
+async def get_redis(redis_uri: Optional[str] = None) -> AsyncRedis:
+    """Return (and lazily create) the module-level async Redis client."""
+    global _pool, _client
+
+    if _client is not None:
+        return _client
+
+    async with _lock:
+        if _client is not None:
+            return _client
+
+        uri = redis_uri or REDIS_URL
+        _pool = ConnectionPool.from_url(
+            uri,
+            decode_responses=True,
+            encoding="utf-8",
+            max_connections=20,
+            health_check_interval=30,
+        )
+        _client = AsyncRedis(connection_pool=_pool)
+        await _client.ping()
+        log.info("Connected to Redis: %s", _redact_uri(uri))
+
+    return _client
+
+
+async def close_redis() -> None:
+    """Shutdown the module-level async Redis connection pool."""
+    global _pool, _client
+
+    async with _lock:
+        if _client is not None:
+            await _client.aclose()
+            _client = None
+        if _pool is not None:
+            await _pool.disconnect()
+            _pool = None
+        log.info("Closed async Redis client")
+
+
+# ---------------------------------------------------------------------------
+# Strict session ID validator (raises on invalid — used by API wrappers)
+# ---------------------------------------------------------------------------
+def valid_session_id(session_id: object) -> str:
+    """Validate and return a non-empty session ID string. Raises ValueError if invalid."""
+    sid = str(session_id).strip() if session_id is not None else ""
+    if not sid or sid.lower() in {"null", "none"}:
+        raise ValueError(f"Invalid session_id: {session_id!r}")
+    return sid
+
+
+# ---------------------------------------------------------------------------
+# Session store — thin async wrapper over the module-level Redis client
+# ---------------------------------------------------------------------------
 class RedisSessionStore:
-    def __init__(self, redis_uri: Optional[str] = None):
-        self.redis_uri = redis_uri or REDIS_URL
-        self.client: Optional[redis.Redis] = None
-        try:
-            c = redis.from_url(self.redis_uri, decode_responses=True)
-            c.ping()
-            self.client = c
-            log.info("✅ Connected to Redis: %s", _redact_uri(self.redis_uri))
-        except Exception as e:
-            log.error("❌ Redis connect failed: %s", e)
-            raise RuntimeError(f"Could not connect to Redis: {e}") from e
-
-    def _valid_session_id(self, session_id: object) -> Optional[str]:
+    """Async Redis session store used by MCP tool implementations."""
+
+    def __init__(self, redis_uri: Optional[str] = None) -> None:
+        self._redis_uri = redis_uri
+
+    async def _redis(self) -> AsyncRedis:
+        return await get_redis(self._redis_uri)
+
+    @staticmethod
+    def _valid_session_id(session_id: object) -> Optional[str]:
         if session_id is None:
             return None
         sid = str(session_id).strip()
@@ -43,35 +104,43 @@ class RedisSessionStore:
             return None
         return sid
 
-    def set(self, session_id: str, data: dict):
+    async def set(self, session_id: str, data: dict) -> None:
         sid = self._valid_session_id(session_id)
         if not sid:
             return
-        self.client.set(sid, json.dumps(data, ensure_ascii=False))  # type: ignore
+        r = await self._redis()
+        await r.set(sid, json.dumps(data, ensure_ascii=False))
         log.info("[Redis] SET %s | Keys: %s", sid, list(data.keys()))
 
-    def get(self, session_id: str) -> Optional[dict]:
+    async def get(self, session_id: str) -> Optional[dict]:
         sid = self._valid_session_id(session_id)
         if not sid:
             return None
-        data = cast(Optional[str], self.client.get(sid))  # type: ignore
+        r = await self._redis()
+        data: Optional[str] = await r.get(sid)  # type: ignore[assignment]
         if not data:
             log.warning("[Redis] MISS %s", sid)
             return None
         log.info("[Redis] HIT %s", sid)
         return json.loads(data)
 
-    def update(self, session_id: str, updates: dict):
+    async def update(self, session_id: str, updates: dict) -> None:
         sid = self._valid_session_id(session_id)
         if not sid:
             return
-        current = self.get(sid) or {}
+        current = await self.get(sid) or {}
         current.update(updates)
-        self.set(sid, current)
+        await self.set(sid, current)
 
-    def delete(self, session_id: str):
+    async def delete(self, session_id: str) -> None:
         sid = self._valid_session_id(session_id)
         if not sid:
             return
-        self.client.delete(sid)  # type: ignore
+        r = await self._redis()
+        await r.delete(sid)
         log.info("[Redis] DEL %s", sid)
+
+    async def set_raw(self, key: str, value: Any, *, ex: int) -> None:
+        """Set an arbitrary key with TTL — used for download tokens."""
+        r = await self._redis()
+        await r.set(key, value, ex=ex)
```

### auth_api.py — Async httpx + removed hardcoded "crm" creds + consolidated _valid_session_id
```diff
diff --git a/backend/src/mcp_service/auth_api.py b/backend/src/mcp_service/auth_api.py
index e4c84dc..c080520 100644
--- a/backend/src/mcp_service/auth_api.py
+++ b/backend/src/mcp_service/auth_api.py
@@ -1,3 +1,6 @@
+from __future__ import annotations
+
+import asyncio
 import logging
 import os
 from typing import Any, Dict, Optional
@@ -5,7 +8,7 @@ from typing import Any, Dict, Optional
 import httpx
 
 from .config import CRM_BASE_URL
-from .session_store import RedisSessionStore
+from .session_store import RedisSessionStore, valid_session_id as _valid_session_id
 from .utils import JsonConverter
 
 conv = JsonConverter(sep=".")
@@ -13,21 +16,65 @@ log = logging.getLogger(name="mft_auth")
 
 _AUTH_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)
 
+# ---------------------------------------------------------------------------
+# Module-level async HTTP client singleton
+# ---------------------------------------------------------------------------
+_http_client: httpx.AsyncClient | None = None
+_http_lock = asyncio.Lock()
+
+
+async def _get_http_client() -> httpx.AsyncClient:
+    global _http_client
+
+    if _http_client is not None:
+        return _http_client
+
+    async with _http_lock:
+        if _http_client is None:
+            _http_client = httpx.AsyncClient(
+                timeout=_AUTH_TIMEOUT,
+                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
+                follow_redirects=True,
+            )
+            log.info("Initialized async HTTP client for auth API")
+    return _http_client
+
+
+async def _close_http_client() -> None:
+    global _http_client
+
+    async with _http_lock:
+        if _http_client is not None:
+            await _http_client.aclose()
+            _http_client = None
+            log.info("Closed async HTTP client for auth API")
 
-def _valid_session_id(session_id: object) -> str:
-    sid = str(session_id).strip() if session_id is not None else ""
-    if not sid or sid.lower() in {"null", "none"}:
-        raise ValueError(f"Invalid session_id: {session_id!r}")
-    return sid
 
+# ---------------------------------------------------------------------------
+# Helpers
+# ---------------------------------------------------------------------------
 
+
+def _load_basic_auth() -> httpx.BasicAuth:
+    """Load CRM credentials from env vars. Fails loudly if unset."""
+    user = os.environ.get("BASIC_AUTH_USERNAME")
+    pwd = os.environ.get("BASIC_AUTH_PASSWORD")
+    if not user or not pwd:
+        raise RuntimeError(
+            "BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD environment variables are required. "
+            "Set them before starting the MCP server."
+        )
+    return httpx.BasicAuth(user, pwd)
+
+
+# ---------------------------------------------------------------------------
+# Auth API wrapper — fully async
+# ---------------------------------------------------------------------------
 class MockFinTechAuthAPIs:
     def __init__(self, session_id: str, session_store: Optional[RedisSessionStore] = None):
         self.session_id = _valid_session_id(session_id)
         self.base_url = CRM_BASE_URL
-        user = os.getenv("BASIC_AUTH_USERNAME", "crm")
-        pwd = os.getenv("BASIC_AUTH_PASSWORD", "crm")
-        self.auth = httpx.BasicAuth(user, pwd)
+        self.auth = _load_basic_auth()
         self.logger = log
         self.session_store = session_store or RedisSessionStore()
 
@@ -42,47 +89,47 @@ class MockFinTechAuthAPIs:
         )
         return vsc
 
-    def generate_otp(self, user_input: str) -> str:
+    async def generate_otp(self, user_input: str) -> str:
         headers = {"Content-Type": "application/json", "Accept": "application/json"}
         phone_number = (user_input or "").strip()
         if not phone_number:
             return self._to_vsc({"error": "phone_number is required"})
 
-        self.session_store.update(self.session_id, {"phone_number": phone_number})
+        await self.session_store.update(self.session_id, {"phone_number": phone_number})
 
         try:
-            with httpx.Client(
-                auth=self.auth, headers=headers, follow_redirects=True, timeout=_AUTH_TIMEOUT
-            ) as client:
-                resp = client.post(
-                    self._url("/mockfin-service/otp/generate_new/"),
-                    json={"phone_number": phone_number},
+            client = await _get_http_client()
+            resp = await client.post(
+                self._url("/mockfin-service/otp/generate_new/"),
+                json={"phone_number": phone_number},
+                headers=headers,
+                auth=self.auth,
+            )
+            self.logger.info("POST otp/generate_new - %d", resp.status_code)
+
+            try:
+                resp_json = resp.json() if resp.text else {}
+            except Exception:
+                resp_json = {}
+
+            if resp.status_code in (200, 201):
+                return self._to_vsc(
+                    {
+                        "status": "OTP Sent",
+                        "phone_number": phone_number,
+                        "message": resp_json.get("message") or "OTP sent.",
+                    }
                 )
-                self.logger.info("POST otp/generate_new - %d", resp.status_code)
-
-                try:
-                    resp_json = resp.json() if resp.text else {}
-                except Exception:
-                    resp_json = {}
-
-                if resp.status_code in (200, 201):
-                    return self._to_vsc(
-                        {
-                            "status": "OTP Sent",
-                            "phone_number": phone_number,
-                            "message": resp_json.get("message") or "OTP sent.",
-                        }
-                    )
-                return self._to_vsc({"status_code": resp.status_code, "error": resp.text[:5000]})
+            return self._to_vsc({"status_code": resp.status_code, "error": resp.text[:5000]})
         except Exception as e:
             self.logger.error("OTP Gen Error: %s", e)
             return self._to_vsc({"error": str(e)})
 
-    def validate_otp(self, otp: str) -> str:
+    async def validate_otp(self, otp: str) -> str:
         headers = {"Content-Type": "application/json", "Accept": "application/json"}
         otp = (otp or "").strip()
 
-        session_data = self.session_store.get(self.session_id) or {}
+        session_data = await self.session_store.get(self.session_id) or {}
         phone_number = (session_data.get("phone_number") or "").strip()
 
         if not phone_number:
@@ -90,57 +137,60 @@ class MockFinTechAuthAPIs:
 
         payload = {"phone_number": phone_number, "otp": otp}
         try:
-            with httpx.Client(
-                auth=self.auth, headers=headers, follow_redirects=True, timeout=_AUTH_TIMEOUT
-            ) as client:
-                resp = client.post(self._url("/mockfin-service/otp/validate_new/"), json=payload)
-                self.logger.info("POST otp/validate_new - %d", resp.status_code)
-
-                if resp.status_code not in (200, 201):
-                    return self._to_vsc(
-                        {"status_code": resp.status_code, "error": resp.text[:5000]}
-                    )
-
-                auth_data = resp.json() if resp.text else {}
-                access_token = auth_data.get("access_token") or auth_data.get("token")
-
-                if not access_token:
-                    return self._to_vsc({"status": "failed", "error": "No token in response."})
-
-                loans: list = auth_data.get("loans") or []
-
-                updates: Dict[str, Any] = {
-                    "access_token": access_token,
-                    "phone_number": phone_number,
-                    "user_details": auth_data.get("user", {}),
-                    "loans": loans,
-                }
-
-                # Auto-select the active loan when there is exactly one
-                if len(loans) == 1:
-                    updates["app_id"] = loans[0].get("loan_number")
-
-                self.session_store.update(self.session_id, updates)
-                self.logger.info("✅ Session %s authenticated.", self.session_id)
-
-                result: Dict[str, Any] = {
-                    "status": "success",
-                    "message": "Logged in.",
-                    "user_details": updates["user_details"],
-                    "loans": loans,
-                }
-                if len(loans) == 1:
-                    result["active_loan"] = loans[0].get("loan_number")
-                elif len(loans) > 1:
-                    result["hint"] = (
-                        "Multiple loans found. Call list_loans() then select_loan(loan_number)."
-                    )
-
-                return self._to_vsc(result)
+            client = await _get_http_client()
+            resp = await client.post(
+                self._url("/mockfin-service/otp/validate_new/"),
+                json=payload,
+                headers=headers,
+                auth=self.auth,
+            )
+            self.logger.info("POST otp/validate_new - %d", resp.status_code)
+
+            if resp.status_code not in (200, 201):
+                return self._to_vsc(
+                    {"status_code": resp.status_code, "error": resp.text[:5000]}
+                )
+
+            auth_data = resp.json() if resp.text else {}
+            access_token = auth_data.get("access_token") or auth_data.get("token")
+
+            if not access_token:
+                return self._to_vsc({"status": "failed", "error": "No token in response."})
+
+            loans: list = auth_data.get("loans") or []
+
+            updates: Dict[str, Any] = {
+                "access_token": access_token,
+                "phone_number": phone_number,
+                "user_details": auth_data.get("user", {}),
+                "loans": loans,
+            }
+
+            # Auto-select the active loan when there is exactly one
+            if len(loans) == 1:
+                updates["app_id"] = loans[0].get("loan_number")
+
+            await self.session_store.update(self.session_id, updates)
+            self.logger.info("Session %s authenticated.", self.session_id)
+
+            result: Dict[str, Any] = {
+                "status": "success",
+                "message": "Logged in.",
+                "user_details": updates["user_details"],
+                "loans": loans,
+            }
+            if len(loans) == 1:
+                result["active_loan"] = loans[0].get("loan_number")
+            elif len(loans) > 1:
+                result["hint"] = (
+                    "Multiple loans found. Call list_loans() then select_loan(loan_number)."
+                )
+
+            return self._to_vsc(result)
         except Exception as e:
             self.logger.error("OTP Validate Error: %s", e)
             return self._to_vsc({"error": str(e)})
 
-    def is_logged_in(self) -> bool:
-        data = self.session_store.get(self.session_id) or {}
+    async def is_logged_in(self) -> bool:
+        data = await self.session_store.get(self.session_id) or {}
         return bool(data.get("access_token"))
```

### core_api.py — Async httpx + hydrate-once fix + consolidated _valid_session_id
```diff
diff --git a/backend/src/mcp_service/core_api.py b/backend/src/mcp_service/core_api.py
index 317e838..a1dc966 100644
--- a/backend/src/mcp_service/core_api.py
+++ b/backend/src/mcp_service/core_api.py
@@ -1,3 +1,6 @@
+from __future__ import annotations
+
+import asyncio
 import json as _json
 import logging
 import uuid
@@ -6,7 +9,7 @@ from typing import Any, Dict, Optional
 import httpx
 
 from .config import CRM_BASE_URL, DOWNLOAD_PROXY_BASE_URL, DOWNLOAD_TOKEN_TTL_SECONDS
-from .session_store import RedisSessionStore
+from .session_store import RedisSessionStore, valid_session_id as _valid_session_id
 from .utils import JsonConverter, ToonOptions
 
 conv = JsonConverter(sep=".")
@@ -14,14 +17,47 @@ log = logging.getLogger(name="mft_api")
 
 _CRM_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)
 
+# ---------------------------------------------------------------------------
+# Module-level async HTTP client singleton
+# ---------------------------------------------------------------------------
+_http_client: httpx.AsyncClient | None = None
+_http_lock = asyncio.Lock()
+
+
+async def _get_http_client() -> httpx.AsyncClient:
+    global _http_client
+
+    if _http_client is not None:
+        return _http_client
+
+    async with _http_lock:
+        if _http_client is None:
+            _http_client = httpx.AsyncClient(
+                timeout=_CRM_TIMEOUT,
+                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
+            )
+            log.info("Initialized async HTTP client for core API")
+    return _http_client
+
 
-def _valid_session_id(session_id: object) -> str:
-    sid = str(session_id).strip() if session_id is not None else ""
-    if not sid or sid.lower() in {"null", "none"}:
-        raise ValueError(f"Invalid session_id: {session_id!r}")
-    return sid
+async def _close_http_client() -> None:
+    global _http_client
 
+    async with _http_lock:
+        if _http_client is not None:
+            await _http_client.aclose()
+            _http_client = None
+            log.info("Closed async HTTP client for core API")
 
+
+# ---------------------------------------------------------------------------
+# Helpers
+# ---------------------------------------------------------------------------
+
+
+# ---------------------------------------------------------------------------
+# Core CRM API wrapper — fully async
+# ---------------------------------------------------------------------------
 class MockFinTechAPIs:
     def __init__(self, session_id: str, session_store: Optional[RedisSessionStore] = None):
         self.session_id = _valid_session_id(session_id)
@@ -32,22 +68,26 @@ class MockFinTechAPIs:
         self.app_id: Optional[str] = None
         self.loan_id: Optional[str] = None
         self.phone_number: Optional[str] = None
-        self._hydrate()
+        self._hydrated: bool = False
 
-    def _hydrate(self) -> None:
-        s = self.session_store.get(self.session_id) or {}
+    async def _hydrate(self) -> None:
+        """Load session state from Redis once per instance lifetime."""
+        if self._hydrated:
+            return
+        s = await self.session_store.get(self.session_id) or {}
         self.bearer_token = s.get("access_token")
         self.app_id = s.get("app_id")
         self.loan_id = s.get("loan_id")
         self.phone_number = s.get("phone_number")
+        self._hydrated = True
 
     def _url(self, path: str) -> str:
         if not path.startswith("/"):
             path = "/" + path
         return f"{self.base_url}{path}"
 
-    def _headers(self) -> Dict[str, str]:
-        self._hydrate()
+    async def _headers(self) -> Dict[str, str]:
+        await self._hydrate()
         if not self.bearer_token:
             return {}
         return {
@@ -56,12 +96,12 @@ class MockFinTechAPIs:
             "Accept": "application/json",
         }
 
-    def _check_context(self) -> Optional[dict]:
-        self._hydrate()
+    async def _check_context(self) -> Optional[dict]:
+        await self._hydrate()
         if not self.bearer_token:
             return {"error": "Auth token missing."}
         if not self.app_id:
-            s = self.session_store.get(self.session_id) or {}
+            s = await self.session_store.get(self.session_id) or {}
             if s.get("loans"):
                 return {
                     "error": "No loan selected. Call list_loans() then select_loan(loan_number)."
@@ -77,11 +117,9 @@ class MockFinTechAPIs:
                 obj, options=ToonOptions(delimiter="|", indent=2, length_marker="")
             )
         except RuntimeError:
-            import json
-
-            return json.dumps(obj, indent=2)
+            return _json.dumps(obj, indent=2)
 
-    def _download(
+    async def _download(
         self,
         method: str,
         path: str,
@@ -89,11 +127,11 @@ class MockFinTechAPIs:
         json_body: Optional[dict] = None,
         require_app_id: bool = False,
     ) -> dict:
-        self._hydrate()
+        await self._hydrate()
         if not self.bearer_token:
             return {"error": "Auth token missing."}
         if require_app_id:
-            ctx_err = self._check_context()
+            ctx_err = await self._check_context()
             if ctx_err:
                 return ctx_err
 
@@ -105,25 +143,25 @@ class MockFinTechAPIs:
             headers["Content-Type"] = "application/json"
 
         try:
-            with httpx.Client(timeout=_CRM_TIMEOUT) as client:
-                with client.stream(
-                    method, self._url(path), headers=headers, json=json_body
-                ) as resp:
-                    self.logger.info("%s %s - %d", method, path, resp.status_code)
-
-                    if resp.status_code not in (200, 201):
-                        resp.read()
-                        try:
-                            err = resp.json()
-                        except Exception:
-                            err = resp.text[:1000]
-                        return {"error": err, "status_code": resp.status_code}
-
-                    hint = resp.headers.get("x-password-hint", "")
-                    disposition = resp.headers.get("content-disposition", "")
-                    filename = ""
-                    if 'filename="' in disposition:
-                        filename = disposition.split('filename="')[1].rstrip('"')
+            client = await _get_http_client()
+            async with client.stream(
+                method, self._url(path), headers=headers, json=json_body
+            ) as resp:
+                self.logger.info("%s %s - %d", method, path, resp.status_code)
+
+                if resp.status_code not in (200, 201):
+                    await resp.aread()
+                    try:
+                        err = resp.json()
+                    except Exception:
+                        err = resp.text[:1000]
+                    return {"error": err, "status_code": resp.status_code}
+
+                hint = resp.headers.get("x-password-hint", "")
+                disposition = resp.headers.get("content-disposition", "")
+                filename = ""
+                if 'filename="' in disposition:
+                    filename = disposition.split('filename="')[1].rstrip('"')
 
             # CRM confirmed the document is available — generate a one-time
             # download token so the user can fetch the PDF via a browser link.
@@ -140,10 +178,8 @@ class MockFinTechAPIs:
                     "password_hint": hint,
                 }
             )
-            self.session_store.client.set(  # type: ignore[union-attr]
-                redis_key,
-                token_payload,
-                ex=DOWNLOAD_TOKEN_TTL_SECONDS,
+            await self.session_store.set_raw(
+                redis_key, token_payload, ex=DOWNLOAD_TOKEN_TTL_SECONDS
             )
 
             download_url = f"{DOWNLOAD_PROXY_BASE_URL}/api/download/{token}"
@@ -158,72 +194,86 @@ class MockFinTechAPIs:
         except Exception as e:
             return {"error": str(e)}
 
-    def _request(self, method: str, path: str, json_body: Optional[dict] = None) -> Any:
-        self._hydrate()
-        ctx_err = self._check_context()
+    async def _request(self, method: str, path: str, json_body: Optional[dict] = None) -> Any:
+        await self._hydrate()
+        ctx_err = await self._check_context()
         if ctx_err and "home" not in path:
             return ctx_err
 
         try:
-            with httpx.Client(timeout=_CRM_TIMEOUT) as client:
-                resp = client.request(
-                    method, self._url(path), headers=self._headers(), json=json_body
-                )
-                self.logger.info("%s %s - %d", method, path, resp.status_code)
-                try:
-                    return resp.json()
-                except Exception:
-                    return {"status_code": resp.status_code, "raw": resp.text[:1000]}
+            client = await _get_http_client()
+            resp = await client.request(
+                method, self._url(path), headers=await self._headers(), json=json_body
+            )
+            self.logger.info("%s %s - %d", method, path, resp.status_code)
+            try:
+                return resp.json()
+            except Exception:
+                return {"status_code": resp.status_code, "raw": resp.text[:1000]}
         except Exception as e:
             return {"error": str(e)}
 
-    def get_dashboard_home(self) -> str:
-        return self._to_toon(self._request("GET", "/mockfin-service/home"))
+    async def get_dashboard_home(self) -> str:
+        return self._to_toon(await self._request("GET", "/mockfin-service/home"))
 
-    def get_loan_details(self) -> str:
+    async def get_loan_details(self) -> str:
+        if not self.app_id:
+            await self._hydrate()
         if not self.app_id:
             return self._to_toon({"error": "No app_id"})
-        return self._to_toon(self._request("GET", f"/mockfin-service/loan/details/{self.app_id}/"))
+        return self._to_toon(
+            await self._request("GET", f"/mockfin-service/loan/details/{self.app_id}/")
+        )
 
-    def get_foreclosure_details(self) -> str:
+    async def get_foreclosure_details(self) -> str:
+        if not self.app_id:
+            await self._hydrate()
         if not self.app_id:
             return self._to_toon({"error": "No app_id"})
         return self._to_toon(
-            self._request("GET", f"/mockfin-service/loan/foreclosuredetails/{self.app_id}/")
+            await self._request("GET", f"/mockfin-service/loan/foreclosuredetails/{self.app_id}/")
         )
 
-    def get_overdue_details(self) -> str:
+    async def get_overdue_details(self) -> str:
+        if not self.app_id:
+            await self._hydrate()
         if not self.app_id:
             return self._to_toon({"error": "No app_id"})
         return self._to_toon(
-            self._request("GET", f"/mockfin-service/loan/overdue-details/{self.app_id}/")
+            await self._request("GET", f"/mockfin-service/loan/overdue-details/{self.app_id}/")
         )
 
-    def get_noc_details(self) -> str:
+    async def get_noc_details(self) -> str:
+        if not self.app_id:
+            await self._hydrate()
         if not self.app_id:
             return self._to_toon({"error": "No app_id"})
         return self._to_toon(
-            self._request("GET", f"/mockfin-service/loan/noc-details/{self.app_id}/")
+            await self._request("GET", f"/mockfin-service/loan/noc-details/{self.app_id}/")
         )
 
-    def get_repayment_schedule(self) -> str:
+    async def get_repayment_schedule(self) -> str:
+        if not self.app_id:
+            await self._hydrate()
         ident = self.app_id or self.loan_id
         if not ident:
             return self._to_toon({"error": "No app_id/loan_id"})
         return self._to_toon(
-            self._request("GET", f"/mockfin-service/loan/repayment-schedule/{ident}/")
+            await self._request("GET", f"/mockfin-service/loan/repayment-schedule/{ident}/")
         )
 
-    def download_welcome_letter(self) -> str:
-        result = self._download(
+    async def download_welcome_letter(self) -> str:
+        result = await self._download(
             "GET", "/mockfin-service/download/welcome-letter/", doc_type="welcome-letter"
         )
         if "error" not in result:
             return self._to_toon(result)
         # CRM unavailable in demo — generate mock letter from loan details
         loan: dict = {}
+        if not self.app_id:
+            await self._hydrate()
         if self.app_id:
-            raw = self._request("GET", f"/mockfin-service/loan/details/{self.app_id}/")
+            raw = await self._request("GET", f"/mockfin-service/loan/details/{self.app_id}/")
             if isinstance(raw, dict) and "error" not in raw:
                 loan = raw
         return self._to_toon(self._build_mock_welcome_letter(loan))
@@ -279,12 +329,14 @@ Yours sincerely,
             "content": content,
         }
 
-    def download_soa(self, start_date: str, end_date: str) -> str:
+    async def download_soa(self, start_date: str, end_date: str) -> str:
+        if not self.app_id:
+            await self._hydrate()
         if not self.app_id:
             return self._to_toon(
                 {"error": "No loan selected. Call list_loans() then select_loan(loan_number)."}
             )
-        result = self._download(
+        result = await self._download(
             "POST",
             "/mockfin-service/download/soa/",
             doc_type="soa",
@@ -295,10 +347,12 @@ Yours sincerely,
         # CRM unavailable in demo — generate mock SOA from loan + repayment schedule
         loan: dict = {}
         schedule: dict = {}
-        raw_loan = self._request("GET", f"/mockfin-service/loan/details/{self.app_id}/")
+        raw_loan = await self._request("GET", f"/mockfin-service/loan/details/{self.app_id}/")
         if isinstance(raw_loan, dict) and "error" not in raw_loan:
             loan = raw_loan
-        raw_sched = self._request("GET", f"/mockfin-service/loan/repayment-schedule/{self.app_id}/")
+        raw_sched = await self._request(
+            "GET", f"/mockfin-service/loan/repayment-schedule/{self.app_id}/"
+        )
         if isinstance(raw_sched, dict) and "error" not in raw_sched:
             schedule = raw_sched
         return self._to_toon(self._build_mock_soa(start_date, end_date, loan, schedule))
@@ -315,11 +369,13 @@ Yours sincerely,
         issued = datetime.date.today().strftime("%d %B %Y")
 
         # Parse date bounds
+        start_dt: datetime.date | None = None
+        end_dt: datetime.date | None = None
         try:
             start_dt = datetime.date.fromisoformat(start_date)
             end_dt = datetime.date.fromisoformat(end_date)
         except ValueError:
-            start_dt = end_dt = None
+            pass
 
         # Extract instalment rows from repayment schedule that fall in range
         rows: list[dict] = []
@@ -370,7 +426,7 @@ Yours sincerely,
 
 ### Transaction History
 
-| Date | Description | Debit (₹) | Credit (₹) | Status |
+| Date | Description | Debit | Credit | Status |
 |---|---|---|---|---|
 {tx_table}
 
@@ -385,7 +441,9 @@ Yours sincerely,
             "content": content,
         }
 
-    def initiate_transaction(self, amount: str, otp: str, payment_mode: str = "UPI") -> str:
+    async def initiate_transaction(self, amount: str, otp: str, payment_mode: str = "UPI") -> str:
+        if not self.app_id:
+            await self._hydrate()
         payload = {
             "phone_number": self.phone_number,
             "otp": otp,
@@ -394,21 +452,21 @@ Yours sincerely,
             "loan_app_id": self.app_id,
         }
         return self._to_toon(
-            self._request("POST", "/payments/initiate_transaction/", json_body=payload)
+            await self._request("POST", "/payments/initiate_transaction/", json_body=payload)
         )
 
-    def profile_phone_generate_otp(self, new_phone: str) -> str:
+    async def profile_phone_generate_otp(self, new_phone: str) -> str:
         return self._to_toon(
-            self._request(
+            await self._request(
                 "PUT",
                 "/mockfin-service/profiles/?update=phone_number",
                 json_body={"phone_number": new_phone},
             )
         )
 
-    def profile_phone_validate_otp(self, new_phone: str, otp: str) -> str:
+    async def profile_phone_validate_otp(self, new_phone: str, otp: str) -> str:
         return self._to_toon(
-            self._request(
+            await self._request(
                 "PUT",
                 "/mockfin-service/profiles/?update=phone_number",
                 json_body={"phone_number": new_phone, "otp": otp},
```

### server.py — All 14 tools async + FastMCP lifespan + dead code removed
```diff
diff --git a/backend/src/mcp_service/server.py b/backend/src/mcp_service/server.py
index 3fb5400..20a9aad 100644
--- a/backend/src/mcp_service/server.py
+++ b/backend/src/mcp_service/server.py
@@ -1,9 +1,15 @@
+from __future__ import annotations
+
 import logging
 import time
-from typing import Any, Optional
+from contextlib import asynccontextmanager
+from typing import Any, AsyncIterator, Optional
 
 from fastmcp import FastMCP
 
+from . import auth_api as _auth_api_mod
+from . import core_api as _core_api_mod
+from . import session_store as _session_store_mod
 from .auth_api import MockFinTechAuthAPIs
 from .config import MCP_SERVER_HOST, MCP_SERVER_PORT
 from .core_api import MockFinTechAPIs
@@ -12,47 +18,68 @@ from .session_store import RedisSessionStore
 
 log = logging.getLogger(name="mcp_server")
 
-mcp = FastMCP(name="MFT MCP Server")
+
+# ---------------------------------------------------------------------------
+# Lifespan — warm Redis on startup, close all async resources on shutdown
+# ---------------------------------------------------------------------------
+@asynccontextmanager
+async def lifespan(_app: Any) -> AsyncIterator[None]:
+    log.info("MCP lifespan: warming async Redis connection pool")
+    await _session_store_mod.get_redis()
+    yield
+    log.info("MCP lifespan: shutting down async resources")
+    await _auth_api_mod._close_http_client()
+    await _core_api_mod._close_http_client()
+    await _session_store_mod.close_redis()
+
+
+mcp = FastMCP(name="MFT MCP Server", lifespan=lifespan)
 session_store = RedisSessionStore()
 
 
-def _touch(session_id: str, tool_name: str, extra: Optional[dict] = None):
+# ---------------------------------------------------------------------------
+# Helpers
+# ---------------------------------------------------------------------------
+async def _touch(session_id: str, tool_name: str, extra: Optional[dict] = None) -> None:
     payload: dict[str, Any] = {"_last_tool": tool_name, "_last_touch_ts": time.time()}
     if extra:
         payload.update(extra)
-    session_store.update(session_id, payload)
+    await session_store.update(session_id, payload)
 
 
-def get_auth(session_id: str):
+def get_auth(session_id: str) -> MockFinTechAuthAPIs:
     return MockFinTechAuthAPIs(session_id, session_store=session_store)
 
 
-def get_api(session_id: str):
+def get_api(session_id: str) -> MockFinTechAPIs:
     return MockFinTechAPIs(session_id, session_store=session_store)
 
 
+# ---------------------------------------------------------------------------
+# MCP Tools — all async
+# ---------------------------------------------------------------------------
 @mcp.tool(name="generate_otp", description=_d("generate_otp"))
-def generate_otp(user_input: str, session_id: str) -> str:
-    _touch(session_id, "generate_otp")
-    return get_auth(session_id).generate_otp(user_input)
+async def generate_otp(user_input: str, session_id: str) -> str:
+    await _touch(session_id, "generate_otp")
+    return await get_auth(session_id).generate_otp(user_input)
 
 
 @mcp.tool(name="validate_otp", description=_d("validate_otp"))
-def validate_otp(otp: str, session_id: str) -> str:
-    _touch(session_id, "validate_otp")
-    return get_auth(session_id).validate_otp(otp)
+async def validate_otp(otp: str, session_id: str) -> str:
+    await _touch(session_id, "validate_otp")
+    return await get_auth(session_id).validate_otp(otp)
 
 
 @mcp.tool(name="is_logged_in", description=_d("is_logged_in"))
-def is_logged_in(session_id: str) -> dict:
-    _touch(session_id, "is_logged_in")
-    return {"logged_in": get_auth(session_id).is_logged_in()}
+async def is_logged_in(session_id: str) -> dict:
+    await _touch(session_id, "is_logged_in")
+    return {"logged_in": await get_auth(session_id).is_logged_in()}
 
 
 @mcp.tool(name="list_loans", description=_d("list_loans"))
-def list_loans(session_id: str) -> str:
-    _touch(session_id, "list_loans")
-    s = session_store.get(session_id) or {}
+async def list_loans(session_id: str) -> str:
+    await _touch(session_id, "list_loans")
+    s = await session_store.get(session_id) or {}
     loans = s.get("loans") or []
     active = s.get("app_id")
     if not loans:
@@ -67,92 +94,79 @@ def list_loans(session_id: str) -> str:
 
 
 @mcp.tool(name="select_loan", description=_d("select_loan"))
-def select_loan(loan_number: str, session_id: str) -> str:
-    _touch(session_id, "select_loan")
-    s = session_store.get(session_id) or {}
+async def select_loan(loan_number: str, session_id: str) -> str:
+    await _touch(session_id, "select_loan")
+    s = await session_store.get(session_id) or {}
     loans = s.get("loans") or []
     known = [loan.get("loan_number") for loan in loans]
     if loan_number not in known:
         return f"Loan '{loan_number}' not found. Available: {', '.join(str(x) for x in known)}"
-    session_store.update(session_id, {"app_id": loan_number})
+    await session_store.update(session_id, {"app_id": loan_number})
     return f"Active loan set to '{loan_number}'."
 
 
 @mcp.tool(name="dashboard_home", description=_d("dashboard_home"))
-def dashboard_home(session_id: str) -> str:
-    _touch(session_id, "dashboard_home")
-    return get_api(session_id).get_dashboard_home()
+async def dashboard_home(session_id: str) -> str:
+    await _touch(session_id, "dashboard_home")
+    return await get_api(session_id).get_dashboard_home()
 
 
 @mcp.tool(name="loan_details", description=_d("loan_details"))
-def loan_details(session_id: str) -> str:
-    _touch(session_id, "loan_details")
-    return get_api(session_id).get_loan_details()
+async def loan_details(session_id: str) -> str:
+    await _touch(session_id, "loan_details")
+    return await get_api(session_id).get_loan_details()
 
 
 @mcp.tool(name="foreclosure_details", description=_d("foreclosure_details"))
-def foreclosure_details(session_id: str) -> str:
-    _touch(session_id, "foreclosure_details")
-    return get_api(session_id).get_foreclosure_details()
+async def foreclosure_details(session_id: str) -> str:
+    await _touch(session_id, "foreclosure_details")
+    return await get_api(session_id).get_foreclosure_details()
 
 
 @mcp.tool(name="overdue_details", description=_d("overdue_details"))
-def overdue_details(session_id: str) -> str:
-    _touch(session_id, "overdue_details")
-    return get_api(session_id).get_overdue_details()
+async def overdue_details(session_id: str) -> str:
+    await _touch(session_id, "overdue_details")
+    return await get_api(session_id).get_overdue_details()
 
 
 @mcp.tool(name="noc_details", description=_d("noc_details"))
-def noc_details(session_id: str) -> str:
-    _touch(session_id, "noc_details")
-    return get_api(session_id).get_noc_details()
+async def noc_details(session_id: str) -> str:
+    await _touch(session_id, "noc_details")
+    return await get_api(session_id).get_noc_details()
 
 
 @mcp.tool(name="repayment_schedule", description=_d("repayment_schedule"))
-def repayment_schedule(session_id: str) -> str:
-    _touch(session_id, "repayment_schedule")
-    return get_api(session_id).get_repayment_schedule()
+async def repayment_schedule(session_id: str) -> str:
+    await _touch(session_id, "repayment_schedule")
+    return await get_api(session_id).get_repayment_schedule()
 
 
 @mcp.tool(name="download_welcome_letter", description=_d("download_welcome_letter"))
-def download_welcome_letter(session_id: str) -> str:
-    _touch(session_id, "download_welcome_letter")
-    return get_api(session_id).download_welcome_letter()
+async def download_welcome_letter(session_id: str) -> str:
+    await _touch(session_id, "download_welcome_letter")
+    return await get_api(session_id).download_welcome_letter()
 
 
 @mcp.tool(name="download_soa", description=_d("download_soa"))
-def download_soa(session_id: str, start_date: str, end_date: str) -> str:
-    _touch(session_id, "download_soa")
-    return get_api(session_id).download_soa(start_date, end_date)
+async def download_soa(session_id: str, start_date: str, end_date: str) -> str:
+    await _touch(session_id, "download_soa")
+    return await get_api(session_id).download_soa(start_date, end_date)
 
 
 @mcp.tool(
     name="logout",
     description="logout() -> str\nPurpose: Clear the current session authentication and access tokens.\nInput variables: (none)",
 )
-def logout(session_id: str) -> str:
-    _touch(session_id, "logout")
-    session_store.delete(session_id)
+async def logout(session_id: str) -> str:
+    await _touch(session_id, "logout")
+    await session_store.delete(session_id)
     return "Logged out successfully. Please reload the page or generate a new OTP to log in again."
 
 
-# @mcp.tool(name="initiate_transaction")
-# def initiate_transaction(amount: str, otp: str, session_id: str, payment_mode: str = "UPI") -> str:
-#     _touch(session_id, "initiate_transaction")
-#     return get_api(session_id).initiate_transaction(amount, otp, payment_mode)
-
-# @mcp.tool(name="profile_phone_generate_otp")
-# def profile_phone_generate_otp(session_id: str, new_phone: str) -> str:
-#     _touch(session_id, "profile_phone_generate_otp")
-#     return get_api(session_id).profile_phone_generate_otp(new_phone)
-
-# @mcp.tool(name="profile_phone_validate_otp")
-# def profile_phone_validate_otp(session_id: str, new_phone: str, otp: str) -> str:
-#     _touch(session_id, "profile_phone_validate_otp")
-#     return get_api(session_id).profile_phone_validate_otp(new_phone, otp)
-
-
-def main():
+# ---------------------------------------------------------------------------
+# Entrypoint
+# ---------------------------------------------------------------------------
+def main() -> None:
     log.info("Starting MCP Server on %s:%s", MCP_SERVER_HOST, MCP_SERVER_PORT)
     mcp.run(transport="sse", host=MCP_SERVER_HOST, port=MCP_SERVER_PORT)
 
```

### test_session_store.py — Async tests with FakeAsyncRedis
```diff
diff --git a/backend/tests/test_session_store.py b/backend/tests/test_session_store.py
index 851bd77..a2d7ec6 100644
--- a/backend/tests/test_session_store.py
+++ b/backend/tests/test_session_store.py
@@ -1,64 +1,82 @@
 import fakeredis
 import pytest
+import pytest_asyncio
 
+from src.mcp_service import session_store as session_store_mod
 from src.mcp_service.session_store import RedisSessionStore
 
 
-@pytest.fixture
-def mock_redis(monkeypatch):
-    # Mock the Redis client creation inside the class
+@pytest_asyncio.fixture
+async def mock_redis(monkeypatch):
+    """Provide a RedisSessionStore backed by fakeredis async client."""
     server = fakeredis.FakeServer()
+    fake_client = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
 
-    def fake_from_url(url, decode_responses=True):
-        return fakeredis.FakeStrictRedis(server=server, decode_responses=decode_responses)
+    # Patch the module-level singleton so _redis() returns our fake
+    monkeypatch.setattr(session_store_mod, "_client", fake_client)
 
-    monkeypatch.setattr("redis.from_url", fake_from_url)
+    store = RedisSessionStore()
+    yield store
 
-    # Initialize store (it will use the fake redis)
-    store = RedisSessionStore("redis://localhost:6379/0")
-    return store
+    # Cleanup: reset module-level singleton
+    monkeypatch.setattr(session_store_mod, "_client", None)
+    monkeypatch.setattr(session_store_mod, "_pool", None)
 
 
-def test_set_and_get(mock_redis):
+@pytest.mark.asyncio
+async def test_set_and_get(mock_redis):
     data = {"user": "test", "token": "123"}
-    mock_redis.set("sess_001", data)
+    await mock_redis.set("sess_001", data)
 
-    result = mock_redis.get("sess_001")
+    result = await mock_redis.get("sess_001")
     assert result == data
     assert result["user"] == "test"
 
 
-def test_get_missing_key(mock_redis):
-    result = mock_redis.get("non_existent")
+@pytest.mark.asyncio
+async def test_get_missing_key(mock_redis):
+    result = await mock_redis.get("non_existent")
     assert result is None
 
 
-def test_update_existing_session(mock_redis):
-    mock_redis.set("sess_002", {"step": 1})
-    mock_redis.update("sess_002", {"step": 2, "new_field": "ok"})
+@pytest.mark.asyncio
+async def test_update_existing_session(mock_redis):
+    await mock_redis.set("sess_002", {"step": 1})
+    await mock_redis.update("sess_002", {"step": 2, "new_field": "ok"})
 
-    result = mock_redis.get("sess_002")
+    result = await mock_redis.get("sess_002")
     assert result["step"] == 2
     assert result["new_field"] == "ok"
 
 
-def test_update_creates_if_missing(mock_redis):
+@pytest.mark.asyncio
+async def test_update_creates_if_missing(mock_redis):
     # Update on a missing key acts like set (starts with empty dict)
-    mock_redis.update("sess_003", {"started": True})
-    result = mock_redis.get("sess_003")
+    await mock_redis.update("sess_003", {"started": True})
+    result = await mock_redis.get("sess_003")
     assert result["started"] is True
 
 
-def test_delete(mock_redis):
-    mock_redis.set("sess_004", {"foo": "bar"})
-    mock_redis.delete("sess_004")
-    assert mock_redis.get("sess_004") is None
+@pytest.mark.asyncio
+async def test_delete(mock_redis):
+    await mock_redis.set("sess_004", {"foo": "bar"})
+    await mock_redis.delete("sess_004")
+    assert await mock_redis.get("sess_004") is None
 
 
-def test_invalid_session_ids(mock_redis):
+@pytest.mark.asyncio
+async def test_invalid_session_ids(mock_redis):
     # Should safely do nothing or return None
-    mock_redis.set(None, {})
-    assert mock_redis.get(None) is None
+    await mock_redis.set(None, {})
+    assert await mock_redis.get(None) is None
 
-    mock_redis.set("   ", {})
-    assert mock_redis.get("   ") is None
+    await mock_redis.set("   ", {})
+    assert await mock_redis.get("   ") is None
+
+
+@pytest.mark.asyncio
+async def test_set_raw_with_ttl(mock_redis):
+    await mock_redis.set_raw("dl_token:abc123", '{"data":"test"}', ex=600)
+    r = await session_store_mod.get_redis()
+    val = await r.get("dl_token:abc123")
+    assert val == '{"data":"test"}'
```

---

<a id="phase-1"></a>
## Backend Phase 1: Data Layer Extraction — AdminAnalyticsRepo

### repo.py — NEW: 15 SQL query methods
```diff
```

### admin_analytics/overview.py
```diff
diff --git a/backend/src/agent_service/api/admin_analytics/overview.py b/backend/src/agent_service/api/admin_analytics/overview.py
index 6899188..e59b0d2 100644
--- a/backend/src/agent_service/api/admin_analytics/overview.py
+++ b/backend/src/agent_service/api/admin_analytics/overview.py
@@ -6,7 +6,7 @@ from fastapi import APIRouter, Depends, Query, Request
 
 from src.agent_service.api.admin_auth import require_admin_key
 
-from .utils import _pg_rows
+from .repo import analytics_repo
 
 router = APIRouter(
     prefix="/agent/admin/analytics",
@@ -18,17 +18,7 @@ router = APIRouter(
 @router.get("/overview")
 async def overview(request: Request):
     pool = request.app.state.pool
-    rows = await _pg_rows(
-        pool,
-        """
-        SELECT
-            COUNT(*)                                              AS traces,
-            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
-            AVG(COALESCE(latency_ms, 0))                         AS avg_latency_ms,
-            MAX(started_at)                                      AS last_active
-        FROM eval_traces
-        """,
-    )
+    rows = await analytics_repo.fetch_overview_stats(pool)
     row = rows[0] if rows else {}
     traces = int(row.get("traces") or 0)
     success = int(row.get("success_count") or 0)
@@ -43,22 +33,5 @@ async def overview(request: Request):
 @router.get("/users")
 async def users(request: Request, limit: int = Query(default=120, ge=1, le=1000)):
     pool = request.app.state.pool
-    rows = await _pg_rows(
-        pool,
-        """
-        SELECT
-            session_id,
-            COUNT(*) AS trace_count,
-            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
-            SUM(CASE WHEN status = 'error'   THEN 1 ELSE 0 END) AS error_count,
-            AVG(COALESCE(latency_ms, 0))                         AS avg_latency_ms,
-            MAX(started_at)                                      AS last_active
-        FROM eval_traces
-        WHERE session_id IS NOT NULL AND started_at IS NOT NULL
-        GROUP BY session_id
-        ORDER BY trace_count DESC
-        LIMIT $1
-        """,
-        limit,
-    )
+    rows = await analytics_repo.fetch_users(pool, limit=limit)
     return {"items": rows, "count": len(rows), "limit": limit}
```

### admin_analytics/conversations.py
```diff
diff --git a/backend/src/agent_service/api/admin_analytics/conversations.py b/backend/src/agent_service/api/admin_analytics/conversations.py
index 0ffacd2..9939ae0 100644
--- a/backend/src/agent_service/api/admin_analytics/conversations.py
+++ b/backend/src/agent_service/api/admin_analytics/conversations.py
@@ -10,7 +10,8 @@ from fastapi import APIRouter, Depends, HTTPException, Query, Request
 from src.agent_service.api.admin_auth import require_admin_key
 from src.agent_service.core.config import ADMIN_CURSOR_APIS_V2
 
-from .utils import _decode_cursor, _encode_cursor, _extract_question_preview, _pg_rows
+from .repo import analytics_repo
+from .utils import _decode_cursor, _encode_cursor, _extract_question_preview
 
 router = APIRouter(
     prefix="/agent/admin/analytics",
@@ -48,38 +49,12 @@ async def conversations(
 
         pool = request.app.state.pool
         search_pat = f"%{normalized_search}%" if normalized_search else None
-        rows = await _pg_rows(
+        rows = await analytics_repo.fetch_conversations(
             pool,
-            """
-            SELECT
-                t.session_id,
-                MAX(t.started_at) AS started_at,
-                COUNT(*) AS message_count,
-                (array_agg(t.model    ORDER BY t.started_at DESC))[1] AS model,
-                (array_agg(t.provider ORDER BY t.started_at DESC))[1] AS provider,
-                (array_agg(t.inputs_json ORDER BY t.started_at DESC))[1] AS inputs_json
-            FROM eval_traces t
-            WHERE t.session_id IS NOT NULL
-              AND t.started_at IS NOT NULL
-              AND (
-                $1::text IS NULL
-                OR LOWER(t.session_id)  LIKE $1
-                OR LOWER(COALESCE(t.inputs_json::text, '')) LIKE $1
-                OR LOWER(COALESCE(t.final_output, '')) LIKE $1
-              )
-            GROUP BY t.session_id
-            HAVING (
-                $2::timestamptz IS NULL
-                OR MAX(t.started_at) < $2
-                OR (MAX(t.started_at) = $2 AND t.session_id < $3)
-            )
-            ORDER BY started_at DESC, t.session_id DESC
-            LIMIT $4
-            """,
-            search_pat,
-            cursor_started_at,
-            cursor_session_id or "",
-            limit + 1,
+            search_pat=search_pat,
+            cursor_started_at=cursor_started_at,
+            cursor_session_id=cursor_session_id or "",
+            limit=limit + 1,
         )
 
         has_more = len(rows) > limit
```

### admin_analytics/guardrails.py
```diff
diff --git a/backend/src/agent_service/api/admin_analytics/guardrails.py b/backend/src/agent_service/api/admin_analytics/guardrails.py
index cdad630..16b75a9 100644
--- a/backend/src/agent_service/api/admin_analytics/guardrails.py
+++ b/backend/src/agent_service/api/admin_analytics/guardrails.py
@@ -15,7 +15,8 @@ from src.agent_service.api.admin_auth import require_admin_key
 from src.agent_service.core.config import SHADOW_TRACE_DLQ_KEY, SHADOW_TRACE_QUEUE_KEY
 from src.agent_service.core.session_utils import get_redis
 
-from .utils import _coerce_guardrail_float, _json_load_maybe, _parse_iso_timestamp, _pg_rows
+from .repo import analytics_repo
+from .utils import _coerce_guardrail_float, _json_load_maybe, _parse_iso_timestamp
 
 router = APIRouter(
     prefix="/agent/admin/analytics",
@@ -70,42 +71,6 @@ def _extract_inline_guard_fields(row: dict[str, Any]) -> tuple[str | None, str |
     return decision, reason_code, risk_score
 
 
-async def _load_guardrail_trace_rows(
-    pool: Any,
-    *,
-    limit: int,
-    tenant_id: str,
-    session_id: str | None = None,
-    start: datetime | None = None,
-    end: datetime | None = None,
-) -> list[dict[str, Any]]:
-    return await _pg_rows(
-        pool,
-        """
-        SELECT
-            trace_id, session_id, endpoint, started_at, meta_json,
-            inline_guard_decision, inline_guard_reason_code, inline_guard_risk_score
-        FROM eval_traces
-        WHERE started_at IS NOT NULL
-          AND ($1::text IS NULL OR session_id = $1)
-          AND ($2 = 'default' OR case_id = $2)
-          AND ($3::timestamptz IS NULL OR started_at >= $3)
-          AND ($4::timestamptz IS NULL OR started_at <= $4)
-          AND (
-            inline_guard_decision IS NOT NULL
-            OR meta_json::text LIKE '%"inline_guard"%'
-          )
-        ORDER BY started_at DESC
-        LIMIT $5
-        """,
-        session_id,
-        tenant_id,
-        start,
-        end,
-        limit,
-    )
-
-
 def _as_guardrail_event(row: dict[str, Any]) -> dict[str, Any] | None:
     decision, reason_code, risk_score = _extract_inline_guard_fields(row)
     if not decision:
@@ -170,7 +135,7 @@ async def guardrails(
     try:
         pool = request.app.state.pool
         fetch_cap = min(max(offset + limit + 1000, 2000), 10000)
-        rows = await _load_guardrail_trace_rows(
+        rows = await analytics_repo.fetch_guardrail_trace_rows(
             pool,
             limit=fetch_cap,
             tenant_id=tenant_id,
@@ -225,7 +190,7 @@ async def guardrails_summary(
     started = time.perf_counter()
     try:
         pool = request.app.state.pool
-        rows = await _load_guardrail_trace_rows(pool, limit=20000, tenant_id=tenant_id)
+        rows = await analytics_repo.fetch_guardrail_trace_rows(pool, limit=20000, tenant_id=tenant_id)
         events = [evt for row in rows if (evt := _as_guardrail_event(row)) is not None]
 
         total_events = len(events)
@@ -273,7 +238,7 @@ async def guardrails_trends(
     try:
         pool = request.app.state.pool
         start = datetime.now(timezone.utc) - timedelta(hours=hours)
-        rows = await _load_guardrail_trace_rows(
+        rows = await analytics_repo.fetch_guardrail_trace_rows(
             pool,
             limit=20000,
             tenant_id=tenant_id,
@@ -371,29 +336,8 @@ async def guardrails_judge_summary(
     limit_failures: int = Query(default=20, ge=1, le=100),
 ):
     pool = request.app.state.pool
-    aggregate_rows = await _pg_rows(
-        pool,
-        """
-        SELECT
-            COUNT(*) AS total_evals,
-            AVG(COALESCE(helpfulness, 0))       AS avg_helpfulness,
-            AVG(COALESCE(faithfulness, 0))       AS avg_faithfulness,
-            AVG(COALESCE(policy_adherence, 0))   AS avg_policy_adherence
-        FROM shadow_judge_evals
-        """,
-    )
-    failure_rows = await _pg_rows(
-        pool,
-        """
-        SELECT trace_id, session_id, model, summary,
-               helpfulness, faithfulness, policy_adherence, evaluated_at
-        FROM shadow_judge_evals
-        WHERE policy_adherence < 0.5 OR faithfulness < 0.5 OR helpfulness < 0.5
-        ORDER BY evaluated_at DESC
-        LIMIT $1
-        """,
-        limit_failures,
-    )
+    aggregate_rows = await analytics_repo.fetch_shadow_judge_aggregates(pool)
+    failure_rows = await analytics_repo.fetch_shadow_judge_failures(pool, limit_failures)
 
     row = aggregate_rows[0] if aggregate_rows else {}
     return {
```

### admin_analytics/traces.py
```diff
diff --git a/backend/src/agent_service/api/admin_analytics/traces.py b/backend/src/agent_service/api/admin_analytics/traces.py
index 2f52d47..63d43f2 100644
--- a/backend/src/agent_service/api/admin_analytics/traces.py
+++ b/backend/src/agent_service/api/admin_analytics/traces.py
@@ -15,13 +15,13 @@ from src.agent_service.api.admin_auth import require_admin_key
 from src.agent_service.core.follow_ups import normalize_follow_up_content
 from src.agent_service.eval_store.status import build_eval_status_payload
 
+from .repo import analytics_repo
 from .utils import (
     _decode_cursor,
     _encode_cursor,
     _extract_question_preview,
     _json_load_maybe,
     _parse_iso_timestamp,
-    _pg_rows,
 )
 
 router = APIRouter(
@@ -152,36 +152,9 @@ async def _load_session_eval_statuses(
     if not unique_trace_ids:
         return {}
 
-    trace_rows = await _pg_rows(
-        pool,
-        """
-        SELECT trace_id, meta_json, ended_at, updated_at
-        FROM eval_traces
-        WHERE trace_id = ANY($1::text[])
-        """,
-        unique_trace_ids,
-    )
-    inline_rows = await _pg_rows(
-        pool,
-        """
-        SELECT trace_id, metric_name, score, passed
-        FROM eval_results
-        WHERE trace_id = ANY($1::text[])
-        ORDER BY trace_id ASC, metric_name ASC
-        """,
-        unique_trace_ids,
-    )
-    shadow_rows = await _pg_rows(
-        pool,
-        """
-        SELECT DISTINCT ON (trace_id)
-               trace_id, helpfulness, faithfulness, policy_adherence, summary, evaluated_at
-        FROM shadow_judge_evals
-        WHERE trace_id = ANY($1::text[])
-        ORDER BY trace_id ASC, evaluated_at DESC
-        """,
-        unique_trace_ids,
-    )
+    trace_rows = await analytics_repo.fetch_session_eval_traces(pool, unique_trace_ids)
+    inline_rows = await analytics_repo.fetch_session_eval_results(pool, unique_trace_ids)
+    shadow_rows = await analytics_repo.fetch_session_shadow_judges(pool, unique_trace_ids)
 
     trace_by_id = {str(row["trace_id"]): row for row in trace_rows}
     shadow_by_id = {str(row["trace_id"]): row for row in shadow_rows}
@@ -282,11 +255,7 @@ async def _checkpoint_trace_detail(request: Request, trace_id: str) -> dict[str,
 
 
 async def _eval_trace_detail(pool: Any, trace_id: str) -> dict[str, Any] | None:
-    trace_rows = await _pg_rows(
-        pool,
-        "SELECT * FROM eval_traces WHERE trace_id = $1",
-        trace_id,
-    )
+    trace_rows = await analytics_repo.fetch_trace_by_id(pool, trace_id)
     if not trace_rows:
         return None
 
@@ -294,39 +263,17 @@ async def _eval_trace_detail(pool: Any, trace_id: str) -> dict[str, Any] | None:
     for key in ("inputs_json", "tags_json", "meta_json"):
         trace_obj[key] = _json_load_maybe(trace_obj.get(key))
 
-    event_rows = await _pg_rows(
-        pool,
-        "SELECT * FROM eval_events WHERE trace_id = $1 ORDER BY seq ASC",
-        trace_id,
-    )
+    event_rows = await analytics_repo.fetch_trace_events(pool, trace_id)
     for event in event_rows:
         event["payload_json"] = _json_load_maybe(event.get("payload_json"))
         event["meta_json"] = _json_load_maybe(event.get("meta_json"))
 
-    eval_rows = await _pg_rows(
-        pool,
-        """
-        SELECT r.*,
-               ARRAY_AGG(ere.event_key) FILTER (WHERE ere.event_key IS NOT NULL)
-                 AS evidence_event_keys
-        FROM eval_results r
-        LEFT JOIN eval_result_evidence ere ON ere.eval_id = r.eval_id
-        WHERE r.trace_id = $1
-        GROUP BY r.eval_id
-        """,
-        trace_id,
-    )
+    eval_rows = await analytics_repo.fetch_trace_eval_results(pool, trace_id)
     for eval_row in eval_rows:
         eval_row["meta_json"] = _json_load_maybe(eval_row.get("meta_json"))
         eval_row["evidence_json"] = _json_load_maybe(eval_row.get("evidence_json"))
 
-    shadow_rows = await _pg_rows(
-        pool,
-        """SELECT helpfulness, faithfulness, policy_adherence, summary, evaluated_at
-           FROM shadow_judge_evals WHERE trace_id = $1
-           ORDER BY evaluated_at DESC LIMIT 1""",
-        trace_id,
-    )
+    shadow_rows = await analytics_repo.fetch_trace_shadow_judge(pool, trace_id)
     shadow_judge = dict(shadow_rows[0]) if shadow_rows else None
     if shadow_judge and shadow_judge.get("evaluated_at"):
         evaluated_at = shadow_judge["evaluated_at"]
@@ -475,19 +422,7 @@ async def session_traces(
 
     if not items:
         # Fallback for sessions with missing checkpointer data: reconstruct from eval_traces.
-        rows = await _pg_rows(
-            pool,
-            """
-            SELECT trace_id, started_at, inputs_json, final_output,
-                   status, model, provider, meta_json
-            FROM eval_traces
-            WHERE session_id = $1
-            ORDER BY started_at ASC
-            LIMIT $2
-            """,
-            session_id,
-            limit,
-        )
+        rows = await analytics_repo.fetch_session_traces_fallback(pool, session_id, limit)
         for idx, row in enumerate(rows, start=1):
             started_at = _parse_iso_timestamp(row.get("started_at"))
             timestamp = int(started_at.timestamp() * 1000) if started_at else 0
@@ -570,38 +505,14 @@ async def traces(
 
         pool = request.app.state.pool
         search_pat = f"%{normalized_search}%" if normalized_search else None
-        rows = await _pg_rows(
+        rows = await analytics_repo.fetch_traces_page(
             pool,
-            """
-            SELECT
-                trace_id, case_id, session_id, provider, model, endpoint,
-                started_at, ended_at, latency_ms, status, error,
-                inputs_json, final_output, meta_json
-            FROM eval_traces
-            WHERE started_at IS NOT NULL
-              AND ($1::text IS NULL OR LOWER(COALESCE(status, '')) = $1)
-              AND ($2::text IS NULL OR COALESCE(model, '') = $2)
-              AND (
-                $3::text IS NULL
-                OR LOWER(trace_id) LIKE $3
-                OR LOWER(COALESCE(session_id, '')) LIKE $3
-                OR LOWER(COALESCE(inputs_json::text, '')) LIKE $3
-                OR LOWER(COALESCE(final_output, '')) LIKE $3
-              )
-              AND (
-                $4::timestamptz IS NULL
-                OR started_at < $4
-                OR (started_at = $4 AND trace_id < $5)
-              )
-            ORDER BY started_at DESC, trace_id DESC
-            LIMIT $6
-            """,
-            normalized_status,
-            normalized_model,
-            search_pat,
-            cursor_started_at,
-            cursor_trace_id or "",
-            limit + 1,
+            status=normalized_status,
+            model=normalized_model,
+            search_pat=search_pat,
+            cursor_started_at=cursor_started_at,
+            cursor_trace_id=cursor_trace_id or "",
+            limit=limit + 1,
         )
 
         has_more = len(rows) > limit
```

### admin_analytics/utils.py
```diff
diff --git a/backend/src/agent_service/api/admin_analytics/utils.py b/backend/src/agent_service/api/admin_analytics/utils.py
index 28fb6de..9100009 100644
--- a/backend/src/agent_service/api/admin_analytics/utils.py
+++ b/backend/src/agent_service/api/admin_analytics/utils.py
@@ -14,20 +14,14 @@ logger = logging.getLogger(__name__)
 
 
 def _json_load_maybe(value: Any) -> Any:
-    if not isinstance(value, str):
-        return value
-    stripped = value.strip()
-    if not stripped:
-        return value
-    if (stripped.startswith("{") and stripped.endswith("}")) or (
-        stripped.startswith("[") and stripped.endswith("]")
-    ):
-        try:
-            return json.loads(stripped)
-        except Exception as exc:
-            logger.debug("_json_load_maybe parse fallback: %s", exc)
-            return value
-    return value
+    """Attempt to parse a JSON string; return the original value on failure.
+
+    Delegates to the canonical implementation in eval_store.status to avoid
+    duplicated parsing logic (see architectural audit Phase 1 consolidation).
+    """
+    from src.agent_service.eval_store.status import json_load_maybe
+
+    return json_load_maybe(value)
 
 
 def _encode_cursor(payload: dict[str, Any]) -> str:
```

### Test mock target updates
```diff
diff --git a/backend/tests/test_admin_conversations_contract.py b/backend/tests/test_admin_conversations_contract.py
index 5896b34..33b3595 100644
--- a/backend/tests/test_admin_conversations_contract.py
+++ b/backend/tests/test_admin_conversations_contract.py
@@ -6,6 +6,7 @@ from types import SimpleNamespace
 import pytest
 
 import src.agent_service.api.admin_analytics.conversations as conversations_mod
+import src.agent_service.api.admin_analytics.repo as repo_mod
 import src.agent_service.api.admin_analytics.traces as traces_mod
 
 
@@ -46,7 +47,7 @@ async def test_conversations_cursor_contract_returns_next_cursor(monkeypatch):
         assert args[3] == 3  # limit_plus_one
         return rows
 
-    monkeypatch.setattr(conversations_mod, "_pg_rows", _fake_pg_rows)
+    monkeypatch.setattr(repo_mod, "_pg_rows", _fake_pg_rows)
     fake_pool = object()
     request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))
 
@@ -124,7 +125,7 @@ async def test_traces_cursor_contract_returns_next_cursor(monkeypatch):
         assert args[5] == 3  # limit_plus_one
         return rows
 
-    monkeypatch.setattr(traces_mod, "_pg_rows", _fake_pg_rows)
+    monkeypatch.setattr(repo_mod, "_pg_rows", _fake_pg_rows)
     fake_pool = object()
     request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))
 
@@ -259,7 +260,7 @@ async def test_session_traces_adds_static_eval_status_for_assistant_messages(mon
             return []
         raise AssertionError(f"Unexpected query: {query}")
 
-    monkeypatch.setattr(traces_mod, "_pg_rows", _fake_pg_rows)
+    monkeypatch.setattr(repo_mod, "_pg_rows", _fake_pg_rows)
     request = SimpleNamespace(
         app=SimpleNamespace(state=SimpleNamespace(checkpointer=_FakeCheckpointer(), pool=object()))
     )
@@ -309,7 +310,7 @@ async def test_session_traces_reconstructs_from_eval_trace_when_checkpoint_missi
             return []
         raise AssertionError(f"Unexpected query: {query}")
 
-    monkeypatch.setattr(traces_mod, "_pg_rows", _fake_pg_rows)
+    monkeypatch.setattr(repo_mod, "_pg_rows", _fake_pg_rows)
     fake_pool = object()
     request = SimpleNamespace(
         app=SimpleNamespace(state=SimpleNamespace(checkpointer=_FakeCheckpointer(), pool=fake_pool))
diff --git a/backend/tests/test_admin_guardrails_analytics.py b/backend/tests/test_admin_guardrails_analytics.py
index 1453503..fce2a13 100644
--- a/backend/tests/test_admin_guardrails_analytics.py
+++ b/backend/tests/test_admin_guardrails_analytics.py
@@ -8,6 +8,7 @@ import pytest
 from fastapi import HTTPException
 
 import src.agent_service.api.admin_analytics.guardrails as guardrails_mod
+import src.agent_service.api.admin_analytics.repo as repo_mod
 
 
 @pytest.mark.asyncio
@@ -39,10 +40,10 @@ async def test_guardrails_events_support_filters_and_pagination():
     async def _fake_rows(pool, **kwargs):
         return rows
 
-    fake_pool = SimpleNamespace()  # pool unused because _load_guardrail_trace_rows is patched
+    fake_pool = SimpleNamespace()  # pool unused because fetch_guardrail_trace_rows is patched
     request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))
     monkeypatch = pytest.MonkeyPatch()
-    monkeypatch.setattr(guardrails_mod, "_load_guardrail_trace_rows", _fake_rows)
+    monkeypatch.setattr(repo_mod.analytics_repo, "fetch_guardrail_trace_rows", _fake_rows)
     response = await guardrails_mod.guardrails(
         request=request,
         tenant_id="tenant-a",
@@ -94,10 +95,10 @@ async def test_guardrails_trends_accepts_integer_hours():
         captured.update(kwargs)
         return rows
 
-    fake_pool = SimpleNamespace()  # pool unused because _load_guardrail_trace_rows is patched
+    fake_pool = SimpleNamespace()  # pool unused because fetch_guardrail_trace_rows is patched
     request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))
     monkeypatch = pytest.MonkeyPatch()
-    monkeypatch.setattr(guardrails_mod, "_load_guardrail_trace_rows", _fake_rows)
+    monkeypatch.setattr(repo_mod.analytics_repo, "fetch_guardrail_trace_rows", _fake_rows)
 
     response = await guardrails_mod.guardrails_trends(
         request=request,
@@ -118,9 +119,9 @@ async def test_guardrails_trends_returns_503_when_db_query_fails():
         raise RuntimeError("db unavailable")
 
     monkeypatch = pytest.MonkeyPatch()
-    monkeypatch.setattr(guardrails_mod, "_load_guardrail_trace_rows", _raise)
+    monkeypatch.setattr(repo_mod.analytics_repo, "fetch_guardrail_trace_rows", _raise)
 
-    fake_pool = SimpleNamespace()  # pool unused because _load_guardrail_trace_rows is patched
+    fake_pool = SimpleNamespace()  # pool unused because fetch_guardrail_trace_rows is patched
     request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))
 
     with pytest.raises(HTTPException) as exc_info:
```

---

<a id="phase-2"></a>
## Backend Phase 2: Shadow Eval Decomposition — 617 LOC → 5 modules

### eval/ sub-package (NEW files)
```diff
```

### shadow_eval.py — Rewritten as thin orchestrator
```diff
diff --git a/backend/src/agent_service/features/shadow_eval.py b/backend/src/agent_service/features/shadow_eval.py
index 470c6e8..78615cb 100644
--- a/backend/src/agent_service/features/shadow_eval.py
+++ b/backend/src/agent_service/features/shadow_eval.py
@@ -1,548 +1,44 @@
-# ===== src/agent_service/features/shadow_eval.py =====
+"""Shadow evaluation orchestrator.
+
+Ties together the eval sub-modules (collector, throttle, metrics, persistence)
+into a single entry point for the agent streaming pipeline.
+
+Public API (backward-compatible):
+    ShadowEvalCollector   — event collector dataclass
+    maybe_shadow_eval_commit — async orchestrator: decide → evaluate → persist
+    should_shadow_eval    — async sampling check
+"""
+
+from __future__ import annotations
 
-import asyncio
-import json
 import logging
 import os
-import random
-import re
-import time
-import uuid
-from copy import deepcopy
-from dataclasses import dataclass, field
-from datetime import datetime, timezone
-from typing import Any, Dict, List, Optional, Sequence, Set
-
-from langchain_core.messages import BaseMessage, HumanMessage
+from typing import Any, Dict, List, Optional
 
-from src.agent_service.core.config import ENABLE_LLM_JUDGE, JUDGE_MODEL_NAME
+from src.agent_service.core.config import ENABLE_LLM_JUDGE  # noqa: F401 — accessed by test via module attribute
 from src.agent_service.eval_store.embedder import EvalEmbedder
-from src.agent_service.eval_store.pg_store import EvalPgStore, get_shared_pool
-from src.agent_service.eval_store.ragas_judge import RagasJudge
+from src.agent_service.eval_store.pg_store import get_shared_pool
+
+from .eval.collector import ShadowEvalCollector
+from .eval.metrics import compute_llm_metrics, compute_non_llm_metrics
+from .eval.persistence import _commit_bundle
+from .eval.throttle import _shadow_eval_decision, should_shadow_eval
 
 log = logging.getLogger("shadow_eval")
-STORE = EvalPgStore()
-EMBEDDER = EvalEmbedder()
 
+# Stream config — used by external workers (eval_ingest, shadow_judge_worker)
 ROUTER_JOBS_STREAM_KEY = (os.getenv("ROUTER_JOBS_STREAM_KEY") or "router:jobs").strip()
 ROUTER_JOBS_STREAM_MAXLEN = int(os.getenv("ROUTER_JOBS_STREAM_MAXLEN") or "50000")
 
+# Capture mode for event filtering in the orchestrator
+SHADOW_EVAL_CAPTURE = (os.getenv("SHADOW_EVAL_CAPTURE") or "light").strip().lower()
+
 __all__ = [
     "ShadowEvalCollector",
     "maybe_shadow_eval_commit",
     "should_shadow_eval",
 ]
 
-# -----------------------------
-# Config (env)
-# -----------------------------
-SHADOW_EVAL_ENABLED = (os.getenv("SHADOW_EVAL_ENABLED") or "0").strip() == "1"
-SHADOW_EVAL_SAMPLE_RATE = float((os.getenv("SHADOW_EVAL_SAMPLE_RATE") or "0.05").strip())
-SHADOW_EVAL_MAX_PER_MIN = int((os.getenv("SHADOW_EVAL_MAX_PER_MIN") or "20").strip())
-SHADOW_EVAL_CAPTURE = (os.getenv("SHADOW_EVAL_CAPTURE") or "light").strip().lower()
-# Runtime trace capture is independent of sampled shadow eval.
-RUNTIME_TRACE_CAPTURE = (os.getenv("RUNTIME_TRACE_CAPTURE") or "full").strip().lower()
-
-# Judge Settings
-JUDGE_REASONING_EFFORT = os.getenv("JUDGE_REASONING_EFFORT", "low")
-
-# Safety caps
-MAX_EVENTS = int((os.getenv("SHADOW_EVAL_MAX_EVENTS") or "500").strip())
-MAX_TEXT = int((os.getenv("SHADOW_EVAL_MAX_TEXT") or "2000").strip())
-MAX_FINAL = int((os.getenv("SHADOW_EVAL_MAX_FINAL") or "200000").strip())
-
-# Optional rules override
-RULES_JSON = (os.getenv("SHADOW_EVAL_RULES_JSON") or "").strip()
-
-DEFAULT_RULES = [
-    {
-        "name": "StolenVehicleEmiFaq",
-        "when": r"(vehicle\s+is\s+stolen|stolen\s+vehicle|stop\s+my\s+emi|emi\s+presentation)",
-        "require_tool": "mock_fintech_knowledge_base",
-        "answer_pattern": r"(cannot\s*be\s*stopped|emi.*continue|continue\s*paying|credit\s*record|knowledge\s*base\s*error)",
-    }
-]
-
-
-def _utc_iso(dt: Optional[datetime] = None) -> str:
-    d = dt or datetime.now(timezone.utc)
-    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
-
-
-def _clip(s: Optional[str], n: int) -> str:
-    if not s:
-        return ""
-    s = str(s)
-    return s if len(s) <= n else s[:n] + f"…(truncated {len(s) - n} chars)"
-
-
-def _strip_html(s: str) -> str:
-    return re.sub(r"<[^>]+>", " ", s or "")
-
-
-def _normalize_text(s: str) -> str:
-    s = _strip_html(s or "")
-    s = s.lower()
-    s = re.sub(r"\s+", " ", s).strip()
-    return s
-
-
-def _load_rules() -> List[dict]:
-    if not RULES_JSON:
-        return DEFAULT_RULES
-    try:
-        obj = json.loads(RULES_JSON)
-        if isinstance(obj, list) and obj:
-            return [x for x in obj if isinstance(x, dict)]
-    except Exception as exc:
-        log.debug("Failed to parse SHADOW_EVAL_RULES_JSON, using defaults: %s", exc)
-    return DEFAULT_RULES
-
-
-# -----------------------------
-# Per-process throttle
-# -----------------------------
-_window_minute: int = 0
-_window_count: int = 0
-_throttle_lock = asyncio.Lock()
-
-
-async def _throttle_ok() -> bool:
-    global _window_minute, _window_count
-    now_min = int(time.time() // 60)
-    async with _throttle_lock:
-        if now_min != _window_minute:
-            _window_minute = now_min
-            _window_count = 0
-        if _window_count >= SHADOW_EVAL_MAX_PER_MIN:
-            return False
-        _window_count += 1
-        return True
-
-
-async def _shadow_eval_decision() -> tuple[bool, str]:
-    if not SHADOW_EVAL_ENABLED:
-        return False, "disabled"
-    if SHADOW_EVAL_SAMPLE_RATE <= 0:
-        return False, "disabled"
-    if random.random() > SHADOW_EVAL_SAMPLE_RATE:
-        return False, "sampled_out"
-    if not await _throttle_ok():
-        return False, "sampled_out"
-    return True, "eligible"
-
-
-async def should_shadow_eval() -> bool:
-    should_run, _ = await _shadow_eval_decision()
-    return should_run
-
-
-# -----------------------------
-# Collector
-# -----------------------------
-@dataclass
-class ShadowEvalCollector:
-    trace_id: str
-    session_id: str
-    question: str
-    provider: Optional[str]
-    model: Optional[str]
-    endpoint: str
-    started_at: datetime
-    tool_names: Set[str]
-
-    # Context Data for Judge
-    retrieved_context: List[str]
-    system_prompt: str
-    chat_history: List[str]
-    tool_definitions: str
-
-    # Internal state
-    _seq: int = 0
-    events: List[Dict[str, Any]] = field(default_factory=list)
-    final_parts: List[str] = field(default_factory=list)
-    error: Optional[str] = None
-    status: str = "success"
-
-    # Optional fields
-    case_id: Optional[str] = None
-    _router_outcome: Optional[Dict[str, Any]] = None
-    _inline_guard_decision: Optional[Dict[str, Any]] = None
-    _eval_lifecycle: Dict[str, Dict[str, Any]] = field(default_factory=dict)
-
-    def __init__(
-        self,
-        session_id: str,
-        question: str,
-        provider: Optional[str],
-        model: Optional[str],
-        endpoint: str,
-        system_prompt: str = "",
-        chat_history: List[BaseMessage] = None,  # type: ignore
-        tool_definitions: str = "",
-    ):
-        self.trace_id = uuid.uuid4().hex
-        self.session_id = session_id
-        self.case_id = None
-        self.question = question
-        self.provider = provider
-        self.model = model
-        self.endpoint = endpoint
-        self.started_at = datetime.now(timezone.utc)
-        self.tool_names = set()
-        self.retrieved_context = []
-
-        self.system_prompt = system_prompt
-        self.tool_definitions = tool_definitions
-
-        self.chat_history = []
-        if chat_history:
-            recent = chat_history[-5:]
-            for msg in recent:
-                role = "User" if isinstance(msg, HumanMessage) else "Assistant"
-                self.chat_history.append(f"{role}: {msg.content}")
-
-        self._seq = 0
-        self.events = []
-        self.final_parts = []
-        self.error = None
-        self.status = "success"
-        self._router_outcome = None
-        self._inline_guard_decision = None
-        self._eval_lifecycle = {}
-
-    def set_router_outcome(self, outcome: Dict[str, Any]) -> None:
-        """Store the router result to be saved with the trace."""
-        self._router_outcome = outcome
-
-    def set_inline_guard_decision(self, decision: Dict[str, Any]) -> None:
-        """Store inline guard decision metadata on the trace."""
-        self._inline_guard_decision = decision
-
-    def set_eval_lifecycle(
-        self,
-        branch: str,
-        state: str,
-        *,
-        reason: Optional[str] = None,
-        queued_at: Optional[str] = None,
-    ) -> None:
-        current = dict(self._eval_lifecycle.get(branch) or {})
-        payload: Dict[str, Any] = {
-            "state": state,
-            "updated_at": _utc_iso(),
-        }
-        if reason:
-            payload["reason"] = reason
-        elif current.get("reason") and current.get("state") == state:
-            payload["reason"] = current["reason"]
-
-        if branch == "shadow":
-            existing_queued_at = current.get("queued_at")
-            if queued_at:
-                payload["queued_at"] = queued_at
-            elif state in {"queued", "failed", "worker_backlog", "timed_out", "complete"}:
-                if existing_queued_at:
-                    payload["queued_at"] = existing_queued_at
-
-        self._eval_lifecycle[branch] = payload
-
-    def mark_shadow_judge_queued(self) -> None:
-        current = dict(self._eval_lifecycle.get("shadow") or {})
-        self.set_eval_lifecycle(
-            "shadow",
-            "queued",
-            reason="queued",
-            queued_at=str(current.get("queued_at") or _utc_iso()),
-        )
-
-    def eval_lifecycle(self) -> Dict[str, Dict[str, Any]]:
-        return deepcopy(self._eval_lifecycle)
-
-    def _next_seq(self) -> int:
-        self._seq += 1
-        return self._seq
-
-    def _add_event(
-        self,
-        event_type: str,
-        name: str,
-        text: Optional[str] = None,
-        payload: Optional[dict] = None,
-        meta: Optional[dict] = None,
-    ) -> None:
-        if len(self.events) >= MAX_EVENTS:
-            return
-        seq = self._next_seq()
-        self.events.append(
-            {
-                "trace_id": self.trace_id,
-                "seq": seq,
-                "event_key": f"{self.trace_id}:{seq}",
-                "ts": _utc_iso(),
-                "event_type": event_type,
-                "name": name,
-                "text": _clip(text, MAX_TEXT),
-                "payload": payload or {},
-                "meta": meta or {},
-            }
-        )
-
-    def _append_final(self, text: str) -> None:
-        if not text:
-            return
-        cur_len = sum(len(x) for x in self.final_parts)
-        if cur_len >= MAX_FINAL:
-            return
-        self.final_parts.append(text[: max(0, MAX_FINAL - cur_len)])
-
-    # ---------- event helpers ----------
-    def on_reasoning(self, token: str) -> None:
-        if RUNTIME_TRACE_CAPTURE == "full":
-            self._add_event("reasoning_token", "reasoning_token", text=token)
-
-    def on_token(self, token: str) -> None:
-        self._append_final(token)
-        if RUNTIME_TRACE_CAPTURE == "full":
-            self._add_event("token", "token", text=token)
-
-    def on_tool_start(self, tool: str, tool_input: Any) -> None:
-        self.tool_names.add(str(tool))
-        payload = tool_input if isinstance(tool_input, dict) else {"value": tool_input}
-        self._add_event(
-            "tool_start", "tool_start", text=str(tool), payload={"tool": tool, "input": payload}
-        )
-
-    def on_tool_end(self, tool: str, output: Any, tool_call_id: Any = None) -> None:
-        self.tool_names.add(str(tool))
-        out_str = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
-        self.retrieved_context.append(f"Tool <{tool}> Output: {out_str}")
-        payload = {"tool": tool, "tool_call_id": tool_call_id, "output": output}
-        self._add_event("tool_end", "tool_end", text=str(tool), payload=payload)
-
-    def on_done(self, final_output: str, error: Optional[str]) -> None:
-        # Persist the canonical final output rather than raw streamed chunks.
-        self.final_parts = [final_output] if final_output else []
-        if error:
-            self.status = "error"
-            self.error = _clip(error, 4000)
-            self._add_event("error", "error", text=self.error)
-        else:
-            self.status = "success"
-        self._add_event("done", "done", text=_clip(final_output, 2000))
-
-    def build_trace_dict(self) -> Dict[str, Any]:
-        ended_at = datetime.now(timezone.utc)
-        latency_ms = int((ended_at - self.started_at).total_seconds() * 1000)
-        final_output = "".join(self.final_parts) if self.final_parts else None
-
-        trace_data = {
-            "trace_id": self.trace_id,
-            "case_id": self.case_id,
-            "session_id": self.session_id,
-            "provider": self.provider,
-            "model": self.model,
-            "endpoint": self.endpoint,
-            "started_at": _utc_iso(self.started_at),
-            "ended_at": _utc_iso(ended_at),
-            "latency_ms": latency_ms,
-            "status": self.status,
-            "error": self.error,
-            "inputs": {"question": self.question},
-            "final_output": final_output,
-            "tags": {
-                "runtime_trace": True,
-                "runtime_capture": RUNTIME_TRACE_CAPTURE,
-                "shadow_eval_capture": SHADOW_EVAL_CAPTURE,
-            },
-            "meta": {
-                "system_prompt": self.system_prompt[:500],
-                "history_len": len(self.chat_history),
-            },
-        }
-
-        eval_lifecycle = self.eval_lifecycle()
-        if eval_lifecycle:
-            trace_data["meta"]["eval_lifecycle"] = eval_lifecycle
-
-        if self._inline_guard_decision:
-            trace_data["meta"]["inline_guard"] = self._inline_guard_decision
-
-        # Bake Router Result directly into Trace
-        if self._router_outcome:
-            r = self._router_outcome
-            trace_data["router_backend"] = r.get("backend")
-
-            # Sentiment
-            s = r.get("sentiment") or {}
-            trace_data["router_sentiment"] = s.get("label")
-            trace_data["router_sentiment_score"] = s.get("score")
-            trace_data["router_override"] = s.get("overridden")
-
-            # Reason
-            rs = r.get("reason") or {}
-            trace_data["router_reason"] = rs.get("label")
-            trace_data["router_reason_score"] = rs.get("score")
-
-        return trace_data
-
-
-def _metric(
-    trace_id: str,
-    metric_name: str,
-    passed: bool,
-    score: float,
-    reasoning: str,
-    evaluator_id: str = "shadow_eval",
-    meta: Optional[dict] = None,
-) -> Dict[str, Any]:
-    return {
-        "eval_id": uuid.uuid4().hex,
-        "trace_id": trace_id,
-        "metric_name": metric_name,
-        "score": float(score),
-        "passed": bool(passed),
-        "reasoning": reasoning,
-        "evaluator_id": evaluator_id,
-        "evidence": [],
-        "meta": meta or {},
-    }
-
-
-def compute_non_llm_metrics(
-    trace: Dict[str, Any],
-    events: Sequence[Dict[str, Any]],
-    tool_names: Set[str],
-) -> List[Dict[str, Any]]:
-    trace_id = str(trace.get("trace_id"))
-    question = str((trace.get("inputs") or {}).get("question") or "")
-    final_output = trace.get("final_output") or ""
-    norm_out = _normalize_text(str(final_output))
-    out: List[Dict[str, Any]] = []
-
-    ok_out = bool(str(final_output).strip())
-    out.append(
-        _metric(
-            trace_id,
-            "AnswerNonEmpty",
-            ok_out,
-            1.0 if ok_out else 0.0,
-            "final_output is non-empty" if ok_out else "final_output empty",
-        )
-    )
-
-    ok_status = (trace.get("status") == "success") and not trace.get("error")
-    out.append(
-        _metric(
-            trace_id,
-            "StreamOk",
-            ok_status,
-            1.0 if ok_status else 0.0,
-            "status=success" if ok_status else f"error={trace.get('error')}",
-        )
-    )
-
-    rules = _load_rules()
-    for r in rules:
-        name = str(r.get("name") or "rule")
-        when = r.get("when")
-        if when:
-            try:
-                if not re.search(when, question, flags=re.I):
-                    continue
-            except Exception as exc:
-                log.debug("Rule regex match failed for rule=%s: %s", name, exc)
-                continue
-
-        req_tool = str(r.get("require_tool") or "").strip()
-        if req_tool:
-            has = req_tool in tool_names
-            out.append(
-                _metric(
-                    trace_id,
-                    f"ToolMatch({req_tool})",
-                    has,
-                    1.0 if has else 0.0,
-                    f"Tool {req_tool} called" if has else "Missing tool call",
-                    meta={"rule": name},
-                )
-            )
-
-        pat = r.get("answer_pattern")
-        if pat:
-            try:
-                m = re.search(pat, norm_out, flags=re.I)
-                ok = m is not None
-                out.append(
-                    _metric(
-                        trace_id,
-                        "NormalizedRegexMatch",
-                        ok,
-                        1.0 if ok else 0.0,
-                        f"Matched pattern '{pat}'" if ok else "Failed pattern",
-                        meta={"rule": name},
-                    )
-                )
-            except Exception as e:
-                out.append(_metric(trace_id, "RegexError", False, 0.0, str(e)))
-    return out
-
-
-async def compute_llm_metrics(
-    trace: Dict[str, Any],
-    collector: ShadowEvalCollector,
-    openrouter_api_key: Optional[str] = None,
-    nvidia_api_key: Optional[str] = None,
-    groq_api_key: Optional[str] = None,
-    model_name: Optional[str] = None,
-    provider: Optional[str] = None,
-) -> List[Dict[str, Any]]:
-    if not ENABLE_LLM_JUDGE:
-        return []
-
-    trace_id = trace["trace_id"]
-    question = trace.get("inputs", {}).get("question", "")
-    answer = trace.get("final_output", "") or ""
-
-    if not answer:
-        return []
-
-    # Tool outputs captured by the collector map directly to RAGAS retrieved_contexts
-    contexts: List[str] = collector.retrieved_context or []
-
-    judge_model = model_name or trace.get("model") or JUDGE_MODEL_NAME
-
-    try:
-        judge = RagasJudge(
-            model_name=judge_model,
-            openrouter_api_key=openrouter_api_key,
-            nvidia_api_key=nvidia_api_key,
-            groq_api_key=groq_api_key,
-        )
-    except Exception as exc:
-        log.warning("[shadow_eval] RAGAS judge initialization failed trace=%s: %s", trace_id, exc)
-        return []
-
-    try:
-        return await judge.evaluate(question, answer, contexts, trace_id)
-    except Exception as exc:
-        log.warning("[shadow_eval] RAGAS evaluation failed trace=%s: %s", trace_id, exc)
-        return []
-
-
-async def _commit_bundle(
-    trace: Dict[str, Any], events: List[Dict[str, Any]], evals: List[Dict[str, Any]]
-) -> None:
-    pool = get_shared_pool()
-    if pool is None:
-        log.error("[shadow_eval] PostgreSQL pool not configured; skipping bundle commit")
-        return
-    await STORE.upsert_trace(pool, trace)
-    if events:
-        await STORE.upsert_events(pool, trace["trace_id"], events)
-    if evals:
-        await STORE.upsert_evals(pool, trace["trace_id"], evals)
-
 
 async def maybe_shadow_eval_commit(
     collector: ShadowEvalCollector,
@@ -560,7 +56,7 @@ async def maybe_shadow_eval_commit(
             return
 
         if SHADOW_EVAL_CAPTURE != "full":
-            events = [
+            events: List[Dict[str, Any]] = [
                 e
                 for e in collector.events
                 if e.get("event_type") in ("tool_start", "tool_end", "error", "done")
```

---

<a id="phase-4"></a>
## Backend Phase 4: Dead Code & Cleanup

### DELETED: common/logger.py, api/graphql.py
```diff
diff --git a/backend/src/agent_service/api/graphql.py b/backend/src/agent_service/api/graphql.py
deleted file mode 100644
index d9e81f2..0000000
--- a/backend/src/agent_service/api/graphql.py
+++ /dev/null
@@ -1,132 +0,0 @@
-from typing import List, Optional
-
-import strawberry
-from strawberry.scalars import JSON
-
-from src.agent_service.llm.catalog import model_service
-
-
-@strawberry.type
-class ParameterSpec:
-    name: str
-    type: str  # "enum", "boolean", "float", "int"
-    options: Optional[List[str]] = None
-    default: Optional[str] = None
-    min: Optional[float] = None
-    max: Optional[float] = None
-
-
-@strawberry.type
-class ModelPricing:
-    prompt: float
-    completion: float
-    unit: str
-
-
-@strawberry.type
-class Model:
-    id: str
-    name: str
-    # ✅ FIX: Expose provider field to frontend
-    provider: str
-    context_length: int
-    pricing: ModelPricing
-    supported_parameters: List[str]
-    parameter_specs: List[ParameterSpec]
-    modality: Optional[str] = None
-    type: Optional[str] = None
-    architecture: Optional[JSON] = None
-
-
-@strawberry.type
-class SubProviderCategory:
-    id: str
-    name: str
-    models: List[Model]
-
-
-@strawberry.type
-class ProviderCategory:
-    name: str
-    models: List[Model]
-    providers: Optional[List[SubProviderCategory]] = None
-
-
-VALID_PROVIDERS = {"groq", "nvidia", "openrouter"}
-REASONING_KEYS = {"reasoning", "reasoning_effort", "include_reasoning"}
-
-
-def _to_float(x) -> float:
-    try:
-        return float(x)
-    except Exception:
-        return 0.0
-
-
-@strawberry.type
-class Query:
-    @strawberry.field
-    async def models(
-        self,
-        provider: Optional[str] = None,
-    ) -> List[ProviderCategory]:
-        # Fetch all raw data from catalog service
-        all_data = await model_service.get_cached_data()
-
-        # Convert raw dicts to Strawberry Types
-        categories = []
-        for cat in all_data:
-            cat_name = cat.get("name")
-
-            # Filter if provider arg is present
-            if provider and cat_name != provider:
-                continue
-
-            raw_models = cat.get("models", [])
-            typed_models = []
-
-            for m in raw_models:
-                # Safe Parsing
-                pricing_dict = m.get("pricing", {}) or {}
-                pricing = ModelPricing(
-                    prompt=_to_float(pricing_dict.get("prompt")),
-                    completion=_to_float(pricing_dict.get("completion")),
-                    unit=str(pricing_dict.get("unit") or "1M tokens"),
-                )
-
-                specs = []
-                for s in m.get("parameter_specs", []) or []:
-                    specs.append(
-                        ParameterSpec(
-                            name=s.get("name", ""),
-                            type=s.get("type", "string"),
-                            options=s.get("options"),
-                            default=str(s.get("default")) if s.get("default") is not None else None,
-                            min=s.get("min"),
-                            max=s.get("max"),
-                        )
-                    )
-
-                typed_models.append(
-                    Model(
-                        id=m.get("id", ""),
-                        name=m.get("name", ""),
-                        provider=m.get("provider", cat_name),  # ✅ FIX: Map provider
-                        context_length=int(m.get("context_length") or 0),
-                        pricing=pricing,
-                        supported_parameters=m.get("supported_parameters", []),
-                        parameter_specs=specs,
-                        modality=m.get("modality"),
-                        type=m.get("type"),
-                        architecture=m.get("architecture"),
-                    )
-                )
-
-            if not cat_name:
-                continue
-            categories.append(ProviderCategory(name=cat_name, models=typed_models))
-
-        return categories
-
-
-schema = strawberry.Schema(query=Query)
diff --git a/backend/src/common/logger.py b/backend/src/common/logger.py
deleted file mode 100644
index 2fbae23..0000000
--- a/backend/src/common/logger.py
+++ /dev/null
@@ -1,22 +0,0 @@
-import logging
-import sys
-
-
-def configure_logger(name: str = "app", level: int = logging.INFO):
-    """
-    Standard Enterprise Logging Configuration.
-    Uses JSON formatting for production if needed, or standard text for dev.
-    """
-    logger = logging.getLogger(name)
-    logger.setLevel(level)
-
-    if not logger.handlers:
-        handler = logging.StreamHandler(sys.stdout)
-        formatter = logging.Formatter(
-            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
-        )
-        handler.setFormatter(formatter)
-        logger.addHandler(handler)
-        logger.propagate = False
-
-    return logger
```

### app_factory.py — Removed GraphQL mount + strawberry import
```diff
diff --git a/backend/src/agent_service/core/app_factory.py b/backend/src/agent_service/core/app_factory.py
index 970fd98..0f741e3 100644
--- a/backend/src/agent_service/core/app_factory.py
+++ b/backend/src/agent_service/core/app_factory.py
@@ -14,7 +14,6 @@ from typing import Optional
 from fastapi import FastAPI, Request
 from fastapi.middleware.cors import CORSMiddleware
 from langgraph.checkpoint.redis.aio import AsyncRedisSaver
-from strawberry.fastapi import GraphQLRouter
 
 from src.agent_service.api.admin import router as admin_router
 from src.agent_service.api.admin_analytics import router as admin_analytics_router
@@ -30,7 +29,6 @@ from src.agent_service.api.endpoints.sessions import router as sessions_router
 from src.agent_service.api.eval_ingest import router as eval_router
 from src.agent_service.api.eval_read import router as eval_read_router
 from src.agent_service.api.feedback import router as feedback_router
-from src.agent_service.api.graphql import schema
 from src.agent_service.core.config import (
     POSTGRES_DSN,
     POSTGRES_POOL_MAX,
@@ -222,9 +220,6 @@ class AppFactory:
     @staticmethod
     def _mount_routers(app: FastAPI) -> None:
         """Mount all API routers."""
-        graphql_app = GraphQLRouter(schema)
-        app.include_router(graphql_app, prefix="/graphql", tags=["graphql"])
-
         app.include_router(eval_router, prefix="/eval", tags=["evaluation"])
         app.include_router(eval_read_router, prefix="/eval", tags=["evaluation"])
 
```

### pyproject.toml — Removed strawberry-graphql dep
```diff
diff --git a/backend/pyproject.toml b/backend/pyproject.toml
index 252ae1a..eaf1ee5 100644
--- a/backend/pyproject.toml
+++ b/backend/pyproject.toml
@@ -28,7 +28,6 @@ dependencies = [
     "mcp>=1.0.0",
     "pdfplumber>=0.11.0",
     "redis>=5.0.0",
-    "strawberry-graphql>=0.240.0",
     "toon-format>=0.1.0",
     "uuid-utils",
     "uvicorn[standard]>=0.30.0",
```

### catalog.py — gpt-oss strings → infer_model_capabilities()
```diff
diff --git a/backend/src/agent_service/llm/catalog.py b/backend/src/agent_service/llm/catalog.py
index b19baca..528cd9f 100644
--- a/backend/src/agent_service/llm/catalog.py
+++ b/backend/src/agent_service/llm/catalog.py
@@ -228,18 +228,19 @@ class ModelService:
         return specs
 
     def _get_groq_specs(self, model_id: str) -> List[Dict[str, Any]]:
+        caps = infer_model_capabilities(model_id=model_id)
         specs = [
             {
                 "name": "temperature",
                 "type": "float",
                 "min": 0.0,
                 "max": 2.0,
-                "default": 0.6 if "gpt-oss" in (model_id or "").lower() else 0.7,
+                "default": 0.6 if caps.get("supports_reasoning_effort") else 0.7,
             },
             {"name": "max_tokens", "type": "int", "min": 1, "max": 32768},
         ]
         mid = (model_id or "").lower()
-        if "gpt-oss" in mid:
+        if caps.get("supports_reasoning_effort"):
             specs.append(
                 {
                     "name": "reasoning_effort",
```

---

<a id="phase-5"></a>
## Backend Phase 5: Structural Refactor — Directory + DI + ToolNode

### 5A: features/routing/ package (NEW)
```diff
```

### 5A: Old features/ files DELETED (moved to routing/)
```diff
diff --git a/backend/src/agent_service/features/answerability.py b/backend/src/agent_service/features/answerability.py
deleted file mode 100644
index 965bd49..0000000
--- a/backend/src/agent_service/features/answerability.py
+++ /dev/null
@@ -1,364 +0,0 @@
-from __future__ import annotations
-
-import asyncio
-import hashlib
-import json
-import logging
-import re
-from dataclasses import dataclass
-from typing import Any, Iterable, Optional
-
-import numpy as np
-
-from src.agent_service.core.config import (
-    NBFC_ROUTER_ANSWERABILITY_KB_HEURISTIC_THRESHOLD,
-    NBFC_ROUTER_ANSWERABILITY_KB_THRESHOLD,
-    NBFC_ROUTER_ANSWERABILITY_MARGIN,
-    NBFC_ROUTER_ANSWERABILITY_MAX_TOOLS,
-    NBFC_ROUTER_ANSWERABILITY_MCP_THRESHOLD,
-    NBFC_ROUTER_ANSWERABILITY_VECTOR_CACHE_SIZE,
-    NBFC_ROUTER_EMBED_MODEL,
-)
-from src.agent_service.llm.client import get_owner_embeddings
-from src.common.milvus_mgr import milvus_mgr
-
-log = logging.getLogger("nbfc.answerability")
-
-_KB_TOOL_NAME = "mock_fintech_knowledge_base"
-_TOKEN_RE = re.compile(r"[a-z0-9]+")
-_KB_HINT_RE = re.compile(
-    r"\b(emi|foreclose|foreclosure|part payment|partpay|loan|interest|charges|statement|"
-    r"customer care|support|kyc|nach|disbursal|approval|claim|stolen|repossession)\b",
-    re.IGNORECASE,
-)
-_STOPWORDS = {
-    "a",
-    "an",
-    "the",
-    "to",
-    "for",
-    "of",
-    "and",
-    "or",
-    "is",
-    "are",
-    "be",
-    "it",
-    "this",
-    "that",
-    "please",
-    "help",
-    "with",
-    "on",
-    "in",
-    "my",
-    "me",
-    "i",
-    "you",
-    "we",
-    "our",
-    "your",
-}
-
-
-@dataclass(slots=True, frozen=True)
-class ToolCandidate:
-    name: str
-    description: str
-    text: str
-
-
-def _norm_text(text: str) -> str:
-    return re.sub(r"\s+", " ", (text or "").strip())
-
-
-def _cosine(a: np.ndarray, b: np.ndarray) -> float:
-    an = a / (np.linalg.norm(a) + 1e-12)
-    bn = b / (np.linalg.norm(b) + 1e-12)
-    return float(np.dot(an, bn))
-
-
-def _tokenize(text: str) -> set[str]:
-    toks = {t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) > 1}
-    return {t for t in toks if t not in _STOPWORDS}
-
-
-def _answerability_decision(
-    *,
-    kb_answerable: bool,
-    kb_score: float,
-    mcp_answerable: bool,
-    mcp_score: float,
-    margin: float,
-    has_any_tools: bool,
-) -> tuple[str, str]:
-    if kb_answerable and mcp_answerable:
-        if kb_score >= (mcp_score + margin):
-            return "kb_answerable", "kb"
-        if mcp_score >= (kb_score + margin):
-            return "mcp_answerable", "mcp"
-        return "kb_and_mcp_answerable", "kb"
-    if kb_answerable:
-        return "kb_answerable", "kb"
-    if mcp_answerable:
-        return "mcp_answerable", "mcp"
-    if has_any_tools:
-        return "needs_general_llm", "llm"
-    return "insufficient_context", "llm"
-
-
-class QueryAnswerabilityClassifier:
-    """
-    Classifies whether a query is likely answerable via KB, MCP tools, both, or neither.
-
-    Output is intentionally structured for telemetry and routing introspection.
-    """
-
-    def __init__(
-        self,
-        *,
-        embed_model: str = NBFC_ROUTER_EMBED_MODEL,
-        kb_threshold: float = NBFC_ROUTER_ANSWERABILITY_KB_THRESHOLD,
-        kb_heuristic_threshold: float = NBFC_ROUTER_ANSWERABILITY_KB_HEURISTIC_THRESHOLD,
-        mcp_threshold: float = NBFC_ROUTER_ANSWERABILITY_MCP_THRESHOLD,
-        margin: float = NBFC_ROUTER_ANSWERABILITY_MARGIN,
-        max_tools: int = NBFC_ROUTER_ANSWERABILITY_MAX_TOOLS,
-        vector_cache_size: int = NBFC_ROUTER_ANSWERABILITY_VECTOR_CACHE_SIZE,
-    ):
-        self.embed_model = embed_model
-        self.kb_threshold = max(0.0, min(1.0, kb_threshold))
-        self.kb_heuristic_threshold = max(0.0, min(1.0, kb_heuristic_threshold))
-        self.mcp_threshold = max(0.0, min(1.0, mcp_threshold))
-        self.margin = max(0.0, min(0.5, margin))
-        self.max_tools = max(1, max_tools)
-        self.vector_cache_size = max(8, vector_cache_size)
-        self._tool_vector_cache: dict[str, list[np.ndarray]] = {}
-        self._cache_lock = asyncio.Lock()
-
-    @staticmethod
-    def _to_candidates(tools: Iterable[Any], *, max_tools: int) -> list[ToolCandidate]:
-        candidates: list[ToolCandidate] = []
-        for tool in tools:
-            name = str(getattr(tool, "name", "") or "").strip()
-            if not name:
-                continue
-            desc = str(getattr(tool, "description", "") or "").strip()
-            text = _norm_text(f"{name.replace('_', ' ')} {desc}".strip())
-            candidates.append(ToolCandidate(name=name, description=desc, text=text))
-            if len(candidates) >= max_tools:
-                break
-        return candidates
-
-    @staticmethod
-    def _lexical_score(query: str, tool_text: str) -> float:
-        q = _tokenize(query)
-        t = _tokenize(tool_text)
-        if not q or not t:
-            return 0.0
-        exact_overlap = len(q & t)
-
-        # Soft overlap handles variants like "validate" vs "validation".
-        fuzzy_overlap = 0
-        if exact_overlap < len(q):
-            for qtok in q:
-                if qtok in t or len(qtok) < 5:
-                    continue
-                if any(
-                    (qtok.startswith(ttok[:5]) or ttok.startswith(qtok[:5]))
-                    for ttok in t
-                    if len(ttok) >= 5
-                ):
-                    fuzzy_overlap += 1
-
-        blended_overlap = exact_overlap + (0.6 * fuzzy_overlap)
-        if blended_overlap <= 0:
-            return 0.0
-        recall = blended_overlap / len(q)
-        precision = blended_overlap / len(t)
-        return float((0.7 * recall) + (0.3 * precision))
-
-    def _tool_cache_key(self, candidates: list[ToolCandidate]) -> str:
-        payload = [{"name": c.name, "text": c.text} for c in candidates]
-        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
-
-    async def _get_tool_vectors(
-        self,
-        candidates: list[ToolCandidate],
-        *,
-        api_key: str,
-    ) -> list[np.ndarray]:
-        if not candidates:
-            return []
-
-        cache_key = self._tool_cache_key(candidates)
-        cached = self._tool_vector_cache.get(cache_key)
-        if cached is not None:
-            return cached
-
-        async with self._cache_lock:
-            cached = self._tool_vector_cache.get(cache_key)
-            if cached is not None:
-                return cached
-
-            emb = get_owner_embeddings(model=self.embed_model)
-            vectors = await emb.aembed_documents([c.text for c in candidates])
-            out = [np.asarray(v, dtype=np.float32) for v in vectors]
-            self._tool_vector_cache[cache_key] = out
-
-            while len(self._tool_vector_cache) > self.vector_cache_size:
-                self._tool_vector_cache.pop(next(iter(self._tool_vector_cache)))
-
-            return out
-
-    @staticmethod
-    def _kb_heuristic_score(query: str) -> float:
-        return 0.45 if _KB_HINT_RE.search(query or "") else 0.0
-
-    @staticmethod
-    async def _kb_vector_lookup(
-        query_vector: np.ndarray,
-    ) -> tuple[Optional[float], Optional[str], Optional[str]]:
-        """Look up the most similar FAQ using Milvus kb_faqs collection."""
-        if milvus_mgr.kb_faqs is None:
-            return None, None, "Milvus not initialized"
-        try:
-            # Convert numpy vector to a query string that Milvus will re-embed,
-            # OR use the pre-computed vector via a raw search.
-            # langchain-milvus doesn't expose pre-vector search directly on the VectorStore
-            # interface, so we use a minimal text query and let Milvus re-embed.
-            # For true pre-vector lookup, use pymilvus directly (out of scope here).
-            results = await milvus_mgr.kb_faqs.asimilarity_search_with_score(
-                "", k=1  # empty query — Milvus will return closest to zero-vector
-            )
-        except Exception as exc:  # noqa: BLE001
-            log.debug("KB vector lookup failed: %s", exc)
-            return None, None, str(exc)
-
-        if not results:
-            return None, None, None
-
-        doc, score = results[0]
-        try:
-            numeric_score = float(score)
-        except Exception as exc:
-            log.debug("KB vector score conversion failed: %s", exc)
-            numeric_score = None
-        question = doc.metadata.get("question")
-        return numeric_score, (str(question) if question else None), None
-
-    async def classify(
-        self,
-        query: str,
-        tools: Iterable[Any],
-        *,
-        api_key: Optional[str] = None,
-        query_vector: Optional[np.ndarray] = None,
-    ) -> dict[str, Any]:
-        q = _norm_text(query)
-        all_candidates = self._to_candidates(tools, max_tools=self.max_tools)
-        kb_available = any(c.name == _KB_TOOL_NAME for c in all_candidates)
-        mcp_candidates = [c for c in all_candidates if c.name != _KB_TOOL_NAME]
-        has_any_tools = bool(all_candidates)
-
-        # MCP lexical scoring
-        best_mcp_name = None
-        best_mcp_lex = 0.0
-        for c in mcp_candidates:
-            score = self._lexical_score(q, c.text)
-            if score > best_mcp_lex:
-                best_mcp_lex = score
-                best_mcp_name = c.name
-
-        query_vec = query_vector
-        vector_error = None
-        if query_vec is None:
-            try:
-                emb = get_owner_embeddings(model=self.embed_model)
-                query_vec = np.asarray(await emb.aembed_query(q), dtype=np.float32)
-            except Exception as exc:  # noqa: BLE001
-                log.warning("Query embedding failed: %s", exc)
-                vector_error = str(exc)
-                query_vec = None
-
-        # MCP semantic scoring
-        best_mcp_sem = None
-        if query_vec is not None and mcp_candidates:
-            try:
-                tool_vecs = await self._get_tool_vectors(
-                    mcp_candidates,
-                    api_key=api_key or "",
-                )
-                for idx, vec in enumerate(tool_vecs):
-                    sem_score = _cosine(query_vec, vec)
-                    if (best_mcp_sem is None) or (sem_score > best_mcp_sem):
-                        best_mcp_sem = sem_score
-                        best_mcp_name = mcp_candidates[idx].name
-            except Exception as exc:  # noqa: BLE001
-                log.warning("MCP tool vector scoring failed: %s", exc)
-                vector_error = str(exc)
-
-        if best_mcp_sem is not None:
-            mcp_score = float((0.75 * best_mcp_sem) + (0.25 * best_mcp_lex))
-            mcp_method = "hybrid"
-            mcp_threshold = self.mcp_threshold
-        else:
-            mcp_score = float(best_mcp_lex)
-            mcp_method = "lexical"
-            # Lexical-only mode is intentionally more permissive to support BYOK/no-key fallback.
-            mcp_threshold = min(self.mcp_threshold, 0.24)
-        mcp_answerable = bool(best_mcp_name) and (mcp_score >= mcp_threshold)
-
-        # KB scoring
-        kb_top_question = None
-        kb_error = None
-        kb_vector_score = None
-        if kb_available and query_vec is not None:
-            kb_vector_score, kb_top_question, kb_error = await self._kb_vector_lookup(query_vec)
-
-        kb_heur = self._kb_heuristic_score(q) if kb_available else 0.0
-        if kb_vector_score is not None:
-            kb_score = float(kb_vector_score)
-            kb_method = "semantic_vector"
-            kb_answerable = kb_score >= self.kb_threshold
-        else:
-            kb_score = float(kb_heur)
-            kb_method = "heuristic"
-            kb_answerable = kb_score >= self.kb_heuristic_threshold
-
-        label, recommended_path = _answerability_decision(
-            kb_answerable=kb_answerable,
-            kb_score=kb_score,
-            mcp_answerable=mcp_answerable,
-            mcp_score=mcp_score,
-            margin=self.margin,
-            has_any_tools=has_any_tools,
-        )
-
-        answerable = label in {"kb_answerable", "mcp_answerable", "kb_and_mcp_answerable"}
-        confidence = float(max(kb_score, mcp_score))
-
-        return {
-            "label": label,
-            "answerable": answerable,
-            "confidence": max(0.0, min(1.0, confidence)),
-            "recommended_path": recommended_path,
-            "kb": {
-                "available": kb_available,
-                "answerable": kb_answerable,
-                "score": kb_score,
-                "threshold": self.kb_threshold,
-                "method": kb_method,
-                "top_question": kb_top_question,
-                "error": kb_error,
-            },
-            "mcp": {
-                "available": bool(mcp_candidates),
-                "answerable": mcp_answerable,
-                "score": mcp_score,
-                "threshold": mcp_threshold,
-                "method": mcp_method,
-                "best_tool": best_mcp_name,
-            },
-            "tools_considered": len(all_candidates),
-            "vector_error": vector_error,
-        }
diff --git a/backend/src/agent_service/features/nbfc_router.py b/backend/src/agent_service/features/nbfc_router.py
deleted file mode 100644
index de2baf8..0000000
--- a/backend/src/agent_service/features/nbfc_router.py
+++ /dev/null
@@ -1,590 +0,0 @@
-from __future__ import annotations
-
-import asyncio
-import hashlib
-import json
-import logging
-import re
-from dataclasses import dataclass
-from typing import Any, Dict, List, Literal, Optional, Tuple
-
-import numpy as np
-from langchain_core.output_parsers import JsonOutputParser
-from pydantic import BaseModel
-
-from src.agent_service.core.config import (
-    NBFC_ROUTER_ANSWERABILITY_ENABLED,
-    NBFC_ROUTER_CHAT_MODEL,
-    NBFC_ROUTER_EMBED_MODEL,
-    NBFC_ROUTER_ENABLED,
-    NBFC_ROUTER_FALLBACK_REASON_SCORE,
-    NBFC_ROUTER_FALLBACK_SENTIMENT_SCORE,
-    NBFC_ROUTER_MODE,
-    NBFC_ROUTER_REASON_UNKNOWN_GATE,
-    NBFC_ROUTER_SENTIMENT_MARGIN,
-    NBFC_ROUTER_SENTIMENT_THRESHOLD,
-)
-from src.agent_service.core.session_utils import get_redis
-from src.agent_service.features.answerability import QueryAnswerabilityClassifier
-
-# Enterprise Imports (Use Factory, not raw classes)
-from src.agent_service.llm.client import get_llm, get_owner_embeddings
-
-from .prototypes_nbfc import REASON_PROTOTYPES, SENTIMENT_PROTOTYPES
-
-log = logging.getLogger("nbfc.router")
-
-# =============================================================================
-# Labels & Constants
-# =============================================================================
-
-SentimentLabel = Literal["positive", "neutral", "negative", "mixed", "unknown"]
-ReasonLabel = Literal[
-    "lead_intent_new_loan",
-    "eligibility_offer",
-    "loan_terms_rates",
-    "kyc_verification",
-    "otp_login_app_tech",
-    "application_status_approval",
-    "disbursal",
-    "emi_payment_reflecting",
-    "nach_autodebit_bounce",
-    "charges_fees_penalty",
-    "foreclosure_partpayment",
-    "statement_receipt",
-    "collections_harassment",
-    "fraud_security",
-    "customer_support",
-    "unknown",
-]
-VALID_SENTIMENT_LABELS: set[str] = {"positive", "neutral", "negative", "mixed", "unknown"}
-VALID_REASON_LABELS: set[str] = {
-    "lead_intent_new_loan",
-    "eligibility_offer",
-    "loan_terms_rates",
-    "kyc_verification",
-    "otp_login_app_tech",
-    "application_status_approval",
-    "disbursal",
-    "emi_payment_reflecting",
-    "nach_autodebit_bounce",
-    "charges_fees_penalty",
-    "foreclosure_partpayment",
-    "statement_receipt",
-    "collections_harassment",
-    "fraud_security",
-    "customer_support",
-    "unknown",
-}
-
-FORCE_LLM_RE = re.compile(r"\b(fraud|unauthorized|harass|harassment|threat|abuse)\b", re.I)
-PROFANITY_RE = re.compile(
-    r"\b(fuck|fucking|wtf|shit|madarchod|bhenchod|bc|mc|chutiya|gandu)\b", re.I
-)
-POS_CUES_RE = re.compile(
-    r"\b(thanks|thank you|thx|love|loved|awesome|amazing|great|super smooth|mast|bhadiya|badiya)\b|(❤️|😍|🔥|💯)",
-    re.I,
-)
-NEG_EMOTION_RE = re.compile(
-    r"\b(worst|pathetic|unacceptable|frustrat|pissed|angry|annoyed|harass|fraud|refund|charged twice)\b",
-    re.I,
-)
-FORECLOSE_RE = re.compile(r"\b(foreclose|foreclosure|preclose|part payment|partpay|noc)\b", re.I)
-QUESTION_RE = re.compile(r"(\?|how much|how to|charges|fee|process|kya|kaise|kitna|kitne)\b", re.I)
-OPS_INTENT_RE = re.compile(
-    r"\b(interest|rate|roi|emi|fee|charges|apply|status|approved|disburs|kyc|pan|otp|login|nach|statement|support)\b",
-    re.I,
-)
-
-# ... (Prototypes imported from module or defined here.
-# For brevity in this fix, we assume they are imported or re-defined.
-
-REASON_BOOSTS: List[Tuple[str, re.Pattern, float]] = [
-    (
-        "loan_terms_rates",
-        re.compile(r"\b(interest rate|roi|rate|tenure|emi|processing fee|charges)\b", re.I),
-        0.08,
-    ),
-    (
-        "disbursal",
-        re.compile(r"\b(approved|approval)\b.*\b(not received|not credited)\b", re.I),
-        0.10,
-    ),
-    ("kyc_verification", re.compile(r"\b(kyc|pan|aadhaar|verification)\b", re.I), 0.10),
-    ("otp_login_app_tech", re.compile(r"\b(otp|login|app)\b", re.I), 0.10),
-    ("collections_harassment", re.compile(r"\b(harass|recovery agent)\b", re.I), 0.12),
-    ("fraud_security", re.compile(r"\b(fraud|scam|unauthorized)\b", re.I), 0.12),
-]
-
-
-def _norm(s: str) -> str:
-    return re.sub(r"\s+", " ", (s or "").strip())
-
-
-def _cosine(a: np.ndarray, b: np.ndarray) -> float:
-    a = a / (np.linalg.norm(a) + 1e-12)
-    b = b / (np.linalg.norm(b) + 1e-12)
-    return float(np.dot(a, b))
-
-
-def _sha256_json(obj: Any) -> str:
-    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
-    return hashlib.sha256(blob).hexdigest()
-
-
-def _tone_override(text: str) -> Optional[Tuple[SentimentLabel, str]]:
-    t = text
-    has_pos = bool(POS_CUES_RE.search(t))
-    has_prof = bool(PROFANITY_RE.search(t))
-    has_neg = bool(NEG_EMOTION_RE.search(t))
-
-    if FORECLOSE_RE.search(t) and QUESTION_RE.search(t) and not has_neg and not has_prof:
-        return ("neutral", "foreclosure_inquiry")
-    if has_pos and (has_neg or has_prof):
-        return ("mixed", "pos+neg_emotion")
-    if has_pos:
-        return ("positive", "positive_cues")
-    if has_neg or has_prof:
-        return ("negative", "neg_emotion/profanity")
-    return None
-
-
-# =============================================================================
-# Caching
-# =============================================================================
-
-
-class _ProtoCache:
-    def _key(self, model: str, fp: str) -> str:
-        return f"agent:router:proto:{model}:{fp}"
-
-    async def load(self, model: str, fp: str) -> Optional[Dict[str, List[List[float]]]]:
-        redis = await get_redis()
-        payload = await redis.get(self._key(model, fp))
-        if not payload:
-            return None
-        try:
-            raw = json.loads(payload)
-            if not isinstance(raw, dict):
-                return None
-            out: Dict[str, List[List[float]]] = {}
-            for label, vecs in raw.items():
-                if not isinstance(label, str) or not isinstance(vecs, list):
-                    continue
-                norm_vecs: List[List[float]] = []
-                for vec in vecs:
-                    if isinstance(vec, list):
-                        norm_vecs.append([float(x) for x in vec])
-                out[label] = norm_vecs
-            return out
-        except Exception as exc:
-            log.debug("Proto cache load failed: %s", exc)
-            return None
-
-    async def save(self, model: str, fp: str, data: Dict[str, List[List[float]]]) -> None:
-        redis = await get_redis()
-        # Redis can only store serialized strings. Ensure ndarray-like inputs are cast to plain lists.
-        serializable = {
-            label: [[float(x) for x in vec] for vec in vecs] for label, vecs in data.items()
-        }
-        await redis.set(
-            self._key(model, fp),
-            json.dumps(serializable, ensure_ascii=False),
-            ex=30 * 24 * 60 * 60,
-        )
-
-
-@dataclass
-class _ProtoBank:
-    vectors: Dict[str, List[np.ndarray]]
-
-
-# =============================================================================
-# Embeddings Router
-# =============================================================================
-
-
-class EmbeddingsRouter:
-    def __init__(self, embed_model: str):
-        self.embed_model = embed_model
-        self.cache = _ProtoCache()
-        self._lock = asyncio.Lock()
-        self._ready = False
-        self._sent_bank: Optional[_ProtoBank] = None
-        self._reason_bank: Optional[_ProtoBank] = None
-
-    async def _build_bank(
-        self, protos: Dict[str, List[str]], cache_prefix: str, api_key: str
-    ) -> _ProtoBank:
-        fp = _sha256_json({"prefix": cache_prefix, "protos": protos})
-        cached = await self.cache.load(self.embed_model, fp)
-        if cached is not None:
-            out = {k: [np.asarray(v, dtype=np.float32) for v in vecs] for k, vecs in cached.items()}
-            return _ProtoBank(vectors=out)
-
-        # Generate fresh embeddings using Factory
-        emb = get_owner_embeddings(model=self.embed_model)
-
-        flat = []
-        labels = []
-        for lab, texts in protos.items():
-            for t in texts:
-                labels.append(lab)
-                flat.append(_norm(t))
-
-        vecs = await emb.aembed_documents(flat)
-
-        ser: Dict[str, List[List[float]]] = {}
-        out2: Dict[str, List[np.ndarray]] = {}
-        for lab, v in zip(labels, vecs, strict=False):
-            ser.setdefault(lab, []).append(v)
-            out2.setdefault(lab, []).append(np.asarray(v, dtype=np.float32))
-
-        await self.cache.save(self.embed_model, fp, ser)
-        return _ProtoBank(vectors=out2)
-
-    async def ensure_ready(self, api_key: str) -> None:
-        if self._ready:
-            return
-        async with self._lock:
-            if self._ready:
-                return
-            self._sent_bank = await self._build_bank(SENTIMENT_PROTOTYPES, "sentiment_v1", api_key)
-            self._reason_bank = await self._build_bank(REASON_PROTOTYPES, "reason_v1", api_key)
-            self._ready = True
-
-    async def _embed_query(self, text: str, api_key: str) -> np.ndarray:
-        emb = get_owner_embeddings(model=self.embed_model)
-        return np.asarray(await emb.aembed_query(_norm(text)), dtype=np.float32)
-
-    @staticmethod
-    def _score_vector(bank: _ProtoBank, vector: np.ndarray) -> List[Tuple[str, float]]:
-        scored = []
-        for label, vecs in bank.vectors.items():
-            scored.append((label, max(_cosine(vector, pv) for pv in vecs)))
-        scored.sort(key=lambda x: x[1], reverse=True)
-        return scored
-
-    async def classify_with_query_vector(
-        self, text: str, api_key: str
-    ) -> tuple[Dict[str, Any], np.ndarray]:
-        await self.ensure_ready(api_key)
-
-        query_vector = await self._embed_query(text, api_key)
-
-        # Sentiment
-        scored_s = self._score_vector(self._sent_bank, query_vector)  # type: ignore
-        best_s, score_s = scored_s[0]
-
-        label_s = best_s
-        if score_s < NBFC_ROUTER_SENTIMENT_THRESHOLD:
-            label_s = "unknown"
-        elif len(scored_s) > 1 and (scored_s[0][1] - scored_s[1][1]) < NBFC_ROUTER_SENTIMENT_MARGIN:
-            label_s = f"ambiguous:{scored_s[0][0]}|{scored_s[1][0]}"
-
-        ov = _tone_override(text)
-        if ov:
-            label_s = ov[0]
-
-        # Reason
-        need_reason = bool(OPS_INTENT_RE.search(text)) or label_s in ("negative", "mixed")
-        reason_res = None
-
-        if need_reason:
-            scored_r = self._score_vector(self._reason_bank, query_vector)  # type: ignore
-            # Boosts
-            bumps = {}
-            for lab, pat, bump in REASON_BOOSTS:
-                if pat.search(text):
-                    bumps[lab] = max(bumps.get(lab, 0.0), bump)
-
-            if bumps:
-                scored_r = [(lab, sc + bumps.get(lab, 0.0)) for lab, sc in scored_r]
-                scored_r.sort(key=lambda x: x[1], reverse=True)
-
-            best_r, score_r = scored_r[0]
-            label_r = best_r
-            if score_r < NBFC_ROUTER_REASON_UNKNOWN_GATE:
-                label_r = "unknown"
-
-            reason_res = {
-                "label": label_r,
-                "score": float(score_r),
-                "topk": [(lab, float(sc)) for lab, sc in scored_r[:3]],
-            }
-
-        return (
-            {
-                "sentiment": {"label": label_s, "score": float(score_s)},
-                "reason": reason_res,
-                "backend": "embeddings",
-            },
-            query_vector,
-        )
-
-    async def classify(self, text: str, api_key: str) -> Dict[str, Any]:
-        result, _ = await self.classify_with_query_vector(text, api_key)
-        return result
-
-
-# =============================================================================
-# LLM Router
-# =============================================================================
-
-
-class LLMRoute(BaseModel):
-    sentiment: SentimentLabel
-    reason: ReasonLabel
-    confidence: float
-    reason_confidence: float
-    short_rationale: Optional[str]
-
-
-class LLMRouter:
-    def __init__(self, chat_model: str):
-        self.chat_model = chat_model
-        self.system = (
-            "You are an NBFC chatbot router. Output JSON only.\n"
-            "Sentiment: positive, negative, neutral, mixed, unknown.\n"
-            "Reason: Choose from standard list or unknown."
-        )
-
-    async def classify(self, text: str, api_key: str) -> Dict[str, Any]:
-        llm = get_llm(model_name=self.chat_model, openrouter_api_key=api_key, temperature=0.0)
-
-        # Try structured output if available, else standard JSON parsing
-        try:
-            structured = llm.with_structured_output(LLMRoute)
-            out = await structured.ainvoke([("system", self.system), ("human", text)])
-        except Exception as exc_structured:
-            log.warning("LLM structured output failed, trying JSON fallback: %s", exc_structured)
-            try:
-                # Fallback
-                chain = llm | JsonOutputParser(pydantic_object=LLMRoute)
-                out = await chain.ainvoke([("system", self.system), ("human", text)])
-            except Exception as exc:
-                log.warning("LLM JSON fallback also failed: %s", exc)
-                return {
-                    "sentiment": {"label": "unknown", "score": 0.0},
-                    "reason": {
-                        "label": "unknown",
-                        "score": 0.0,
-                        "meta": {"rationale": None, "error": str(exc)},
-                    },
-                    "backend": f"llm_{self.chat_model}",
-                }
-
-        def _as_float(value: Any) -> float:
-            try:
-                return float(value)
-            except Exception:
-                return 0.0
-
-        # Convert to dict format (handle both BaseModel and dict) with safe defaults.
-        try:
-            if isinstance(out, dict):
-                sentiment_label = str(out.get("sentiment", "unknown")).strip().lower()
-                if sentiment_label not in VALID_SENTIMENT_LABELS:
-                    sentiment_label = "unknown"
-
-                reason_label = str(out.get("reason", "unknown")).strip().lower()
-                if reason_label not in VALID_REASON_LABELS:
-                    reason_label = "unknown"
-
-                s = {"label": sentiment_label, "score": _as_float(out.get("confidence", 0.0))}
-                r = {
-                    "label": reason_label,
-                    "score": _as_float(out.get("reason_confidence", 0.0)),
-                    "meta": {"rationale": out.get("short_rationale")},
-                }
-            else:
-                route: LLMRoute = out  # type: ignore
-                s = {"label": route.sentiment, "score": float(route.confidence)}
-                r = {
-                    "label": route.reason,
-                    "score": float(route.reason_confidence),
-                    "meta": {"rationale": route.short_rationale},
-                }
-        except Exception as exc:
-            log.warning("LLM route dict conversion failed: %s", exc)
-            return {
-                "sentiment": {"label": "unknown", "score": 0.0},
-                "reason": {
-                    "label": "unknown",
-                    "score": 0.0,
-                    "meta": {"rationale": None, "error": str(exc)},
-                },
-                "backend": f"llm_{self.chat_model}",
-            }
-
-        return {"sentiment": s, "reason": r, "backend": f"llm_{self.chat_model}"}
-
-
-# =============================================================================
-# Service
-# =============================================================================
-
-
-class NBFCClassifierService:
-    def __init__(self):
-        self.emb = EmbeddingsRouter(NBFC_ROUTER_EMBED_MODEL)
-        self.llm = LLMRouter(NBFC_ROUTER_CHAT_MODEL)
-        self.answerability = QueryAnswerabilityClassifier(embed_model=NBFC_ROUTER_EMBED_MODEL)
-
-    async def _safe_answerability(
-        self,
-        text: str,
-        *,
-        tools: Optional[List[Any]],
-        openrouter_api_key: Optional[str],
-        query_vector: Optional[np.ndarray] = None,
-    ) -> Dict[str, Any]:
-        if not NBFC_ROUTER_ANSWERABILITY_ENABLED:
-            return {
-                "disabled": True,
-                "label": "disabled",
-                "answerable": False,
-                "confidence": 0.0,
-                "recommended_path": "llm",
-            }
-        try:
-            return await self.answerability.classify(
-                text,
-                tools or [],
-                api_key=openrouter_api_key,
-                query_vector=query_vector,
-            )
-        except Exception as exc:  # noqa: BLE001
-            log.warning("Answerability classification failed: %s", exc)
-            return {
-                "label": "unknown",
-                "answerable": False,
-                "confidence": 0.0,
-                "recommended_path": "llm",
-                "error": str(exc),
-            }
-
-    async def classify(
-        self,
-        text: str,
-        openrouter_api_key: Optional[str] = None,
-        mode: Optional[str] = None,
-        tools: Optional[List[Any]] = None,
-    ) -> Dict[str, Any]:
-        if not NBFC_ROUTER_ENABLED:
-            return {"disabled": True, "backend": "disabled"}
-
-        t = _norm(text)
-        mode = mode or NBFC_ROUTER_MODE
-
-        if not openrouter_api_key:
-            answerability = await self._safe_answerability(
-                t,
-                tools=tools,
-                openrouter_api_key=None,
-            )
-            return {
-                "error": "OpenRouter Key required for router",
-                "backend": "router_unavailable",
-                "answerability": answerability,
-            }
-
-        # Embeddings First
-        e, query_vector = await self.emb.classify_with_query_vector(t, openrouter_api_key)
-
-        if mode == "embeddings":
-            e["answerability"] = await self._safe_answerability(
-                t,
-                tools=tools,
-                openrouter_api_key=openrouter_api_key,
-                query_vector=query_vector,
-            )
-            return e
-
-        # Force LLM check
-        force_llm = bool(FORCE_LLM_RE.search(t))
-
-        # Confidence check
-        s_score = e["sentiment"]["score"]
-        r_score = e["reason"]["score"] if e["reason"] else 1.0
-
-        low_conf = (s_score < NBFC_ROUTER_FALLBACK_SENTIMENT_SCORE) or (
-            r_score < NBFC_ROUTER_FALLBACK_REASON_SCORE
-        )
-
-        if mode == "llm" or force_llm or (mode == "hybrid" and low_conf):
-            llm_result = await self.llm.classify(t, openrouter_api_key)
-            llm_result["backend"] = (
-                f"hybrid->{llm_result['backend']}" if mode == "hybrid" else llm_result["backend"]
-            )
-            result = llm_result
-        else:
-            result = e
-
-        result["answerability"] = await self._safe_answerability(
-            t,
-            tools=tools,
-            openrouter_api_key=openrouter_api_key,
-            query_vector=query_vector,
-        )
-        return result
-
-    async def compare(
-        self,
-        text: str,
-        openrouter_api_key: Optional[str] = None,
-        tools: Optional[List[Any]] = None,
-    ) -> Dict[str, Any]:
-        t = _norm(text)
-        if not openrouter_api_key:
-            return {
-                "error": "Key required",
-                "answerability": await self._safe_answerability(
-                    t,
-                    tools=tools,
-                    openrouter_api_key=None,
-                ),
-            }
-        errors: Dict[str, str] = {}
-        query_vector: Optional[np.ndarray] = None
-
-        try:
-            e, query_vector = await self.emb.classify_with_query_vector(t, openrouter_api_key)
-        except Exception as exc:
-            log.warning("Embeddings classification failed during compare: %s", exc)
-            errors["embeddings"] = str(exc)
-            e = {
-                "sentiment": {"label": "unknown", "score": 0.0},
-                "reason": {"label": "unknown", "score": 0.0},
-                "backend": "embeddings",
-                "error": str(exc),
-            }
-
-        try:
-            llm_result = await self.llm.classify(t, openrouter_api_key)
-        except Exception as exc:
-            log.warning("LLM classification failed during compare: %s", exc)
-            errors["llm"] = str(exc)
-            llm_result = {
-                "sentiment": {"label": "unknown", "score": 0.0},
-                "reason": {"label": "unknown", "score": 0.0},
-                "backend": f"llm_{self.llm.chat_model}",
-                "error": str(exc),
-            }
-
-        result = {
-            "embeddings": e,
-            "llm": llm_result,
-            "answerability": await self._safe_answerability(
-                t,
-                tools=tools,
-                openrouter_api_key=openrouter_api_key,
-                query_vector=query_vector,
-            ),
-        }
-        if errors:
-            result["errors"] = errors
-        return result
-
-
-nbfc_router_service = NBFCClassifierService()
diff --git a/backend/src/agent_service/features/prototypes_nbfc.py b/backend/src/agent_service/features/prototypes_nbfc.py
deleted file mode 100644
index ee3eda2..0000000
--- a/backend/src/agent_service/features/prototypes_nbfc.py
+++ /dev/null
@@ -1,167 +0,0 @@
-from typing import Dict, List
-
-# =============================================================================
-# Sentiment Prototypes (Reference Vectors)
-# =============================================================================
-
-SENTIMENT_PROTOTYPES: Dict[str, List[str]] = {
-    "positive": [
-        "thank you so much",
-        "thanks for the help",
-        "great service",
-        "app is working perfectly",
-        "love the quick approval",
-        "received the money instantly, thanks",
-        "good experience",
-        "support was helpful",
-        "excellent app",
-        "mast hai",
-        "badiya hai",
-        "super smooth process",
-    ],
-    "negative": [
-        "this is a scam",
-        "fake app",
-        "fraud company",
-        "stop harassing me",
-        "i will complain to non-rbi",
-        "worst experience ever",
-        "customer care is useless",
-        "why did you deduct money",
-        "cheaters",
-        "bakwaas app",
-        "gandu",
-        "madarchod",
-        "bhenchod",
-        "bloody scammers",
-        "i want to close my loan immediately",
-        "stop calling my relatives",
-    ],
-    "neutral": [
-        "what is my outstanding balance?",
-        "how to pay emi?",
-        "change my mobile number",
-        "i want to foreclose",
-        "what are the charges?",
-        "when is the due date?",
-        "is this app safe?",
-        "how to apply for top up?",
-        "need noc",
-        "update my kyc",
-        "payment not reflecting",
-        "login issue",
-        "otp not coming",
-    ],
-}
-
-# =============================================================================
-# Reason Prototypes (Intent Classification)
-# =============================================================================
-
-REASON_PROTOTYPES: Dict[str, List[str]] = {
-    "lead_intent_new_loan": [
-        "I want a loan",
-        "apply for personal loan",
-        "how to get money?",
-        "need urgent cash",
-        "loan limit increase",
-        "top up loan available?",
-        "eligibility check",
-    ],
-    "application_status_approval": [
-        "check my application status",
-        "why is it rejected?",
-        "pending since yesterday",
-        "when will it be approved?",
-        "under review for long time",
-        "kyc verified but no approval",
-    ],
-    "disbursal": [
-        "money not credited",
-        "loan approved but not received",
-        "when will money come to bank?",
-        "disbursement pending",
-        "amount deducted but not credited",
-    ],
-    "emi_payment_reflecting": [
-        "paid emi but not updated",
-        "payment failed",
-        "money cut from bank but showing due",
-        "how to pay manually?",
-        "paytm not working",
-        "upi link for payment",
-        "already paid",
-    ],
-    "foreclosure_partpayment": [
-        "i want to close my loan",
-        "foreclosure charges",
-        "prepayment option",
-        "close account permanently",
-        "noc letter request",
-        "pay full amount now",
-    ],
-    "charges_fees_penalty": [
-        "why extra charges?",
-        "processing fee is too high",
-        "penalty charges explanation",
-        "hidden charges",
-        "why insurance fee deducted?",
-        "bounce charges refund",
-    ],
-    "nach_autodebit_bounce": [
-        "stop auto debit",
-        "nach failed",
-        "change bank for auto debit",
-        "bounce charge why?",
-        "cancel enach",
-        "disable autopay",
-    ],
-    "kyc_verification": [
-        "kyc rejected",
-        "video kyc not working",
-        "pan card upload error",
-        "aadhaar verification failed",
-        "selfie not uploading",
-        "documents required",
-    ],
-    "otp_login_app_tech": [
-        "otp not received",
-        "cannot login",
-        "app crashing",
-        "invalid pin",
-        "change mobile number",
-        "login error",
-        "forgot password",
-    ],
-    "statement_receipt": [
-        "send loan statement",
-        "need payment receipt",
-        "repayment schedule",
-        "send noc to email",
-        "download statement",
-    ],
-    "collections_harassment": [
-        "stop calling me",
-        "agent is abusive",
-        "harassment complaint",
-        "calling my parents",
-        "recovery agent threat",
-        "do not call contact list",
-    ],
-    "fraud_security": [
-        "this is fraud",
-        "unauthorized transaction",
-        "someone took loan in my name",
-        "fake profile",
-        "report scam",
-        "account hacked",
-    ],
-    "customer_support": [
-        "call me",
-        "customer care number",
-        "talk to human",
-        "chat with agent",
-        "support team email",
-        "raise a ticket",
-    ],
-}
diff --git a/backend/src/agent_service/features/question_category.py b/backend/src/agent_service/features/question_category.py
deleted file mode 100644
index e17efe4..0000000
--- a/backend/src/agent_service/features/question_category.py
+++ /dev/null
@@ -1,171 +0,0 @@
-from __future__ import annotations
-
-import re
-from dataclasses import dataclass
-from typing import Optional
-
-BUSINESS_CATEGORIES: tuple[str, ...] = (
-    "loan_products_and_eligibility",
-    "application_status_and_approval",
-    "theft_claim_and_non_seizure",
-    "disbursal_and_bank_credit",
-    "profile_kyc_and_access",
-    "credit_report_and_bureau",
-    "foreclosure_and_closure",
-    "emi_payments_and_charges",
-    "collections_and_recovery",
-    "fraud_and_security",
-    "customer_support_channels",
-    "other",
-)
-
-ROUTER_REASON_TO_CATEGORY: dict[str, str] = {
-    "lead_intent_new_loan": "loan_products_and_eligibility",
-    "eligibility_offer": "loan_products_and_eligibility",
-    "loan_terms_rates": "loan_products_and_eligibility",
-    "application_status_approval": "application_status_and_approval",
-    "disbursal": "disbursal_and_bank_credit",
-    "kyc_verification": "profile_kyc_and_access",
-    "otp_login_app_tech": "profile_kyc_and_access",
-    "emi_payment_reflecting": "emi_payments_and_charges",
-    "nach_autodebit_bounce": "emi_payments_and_charges",
-    "charges_fees_penalty": "emi_payments_and_charges",
-    "statement_receipt": "emi_payments_and_charges",
-    "foreclosure_partpayment": "foreclosure_and_closure",
-    "collections_harassment": "collections_and_recovery",
-    "fraud_security": "fraud_and_security",
-    "customer_support": "customer_support_channels",
-    "unknown": "other",
-}
-
-# Ordered from most specific/high-signal to broader buckets.
-KEYWORD_CATEGORY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
-    (
-        "theft_claim_and_non_seizure",
-        re.compile(
-            r"\b(stolen|theft|theft/loss|insurance\s+claim|non[-\s]?repossession|non[-\s]?seizure)\b",
-            re.I,
-        ),
-    ),
-    (
-        "fraud_and_security",
-        re.compile(
-            r"\b(fraud|scam|unauthorized|hack(?:ed|ing)?|loan\s+in\s+my\s+name|security\s+issue)\b",
-            re.I,
-        ),
-    ),
-    (
-        "collections_and_recovery",
-        re.compile(
-            r"\b(collections?|recovery\s+agent|harass|stop\s+calls?|calling\s+me|calling\s+relatives?)\b",
-            re.I,
-        ),
-    ),
-    (
-        "credit_report_and_bureau",
-        re.compile(
-            r"\b(credit\s+report|credit\s+score|bureau|cibil|dpd|write[-\s]?off|settled\s+remark)\b",
-            re.I,
-        ),
-    ),
-    (
-        "foreclosure_and_closure",
-        re.compile(
-            r"\b(foreclos|prepay|part\s*payment|close\s+my\s+loan|closure\s+amount|noc)\b",
-            re.I,
-        ),
-    ),
-    (
-        "disbursal_and_bank_credit",
-        re.compile(
-            r"\b(disburs|disbursement|approved\s+but\s+not\s+received|not\s+credited|money\s+not\s+received)\b",
-            re.I,
-        ),
-    ),
-    (
-        "profile_kyc_and_access",
-        re.compile(
-            r"\b(kyc|otp|login|address\s+update|email\s+id|mobile\s+number|profile\s+update|contact\s+details)\b",
-            re.I,
-        ),
-    ),
-    (
-        "emi_payments_and_charges",
-        re.compile(
-            r"\b(emi|payment\s+not\s+reflect|bounce\s+charge|nach|auto\s*debit|charges?|penalt|refund|due\s+date)\b",
-            re.I,
-        ),
-    ),
-    (
-        "application_status_and_approval",
-        re.compile(
-            r"\b(application\s+status|status\s+check|approved|approval|rejected|pending\s+application)\b",
-            re.I,
-        ),
-    ),
-    (
-        "loan_products_and_eligibility",
-        re.compile(
-            r"\b(apply\s+for\s+(a\s+)?(loan|personal\s+loan|home\s+loan|business\s+loan|vehicle\s+loan)|eligib|loan\s+products?)\b",
-            re.I,
-        ),
-    ),
-    (
-        "customer_support_channels",
-        re.compile(
-            r"\b(callback|call\s+me|customer\s+care|toll[-\s]?free|whatsapp|support\s+number|help\s+desk)\b",
-            re.I,
-        ),
-    ),
-)
-
-
-@dataclass(slots=True)
-class QuestionCategoryResult:
-    category: str
-    confidence: float
-    source: str
-
-
-def map_router_reason_to_category(router_reason: Optional[str]) -> Optional[str]:
-    if not router_reason:
-        return None
-    normalized = router_reason.strip().lower()
-    return ROUTER_REASON_TO_CATEGORY.get(normalized)
-
-
-def classify_question_category(
-    question: Optional[str],
-    router_reason: Optional[str] = None,
-) -> QuestionCategoryResult:
-    text = (question or "").strip()
-
-    if text:
-        for category, pattern in KEYWORD_CATEGORY_RULES:
-            if pattern.search(text):
-                return QuestionCategoryResult(
-                    category=category,
-                    confidence=0.9,
-                    source="keyword",
-                )
-
-    mapped_router = map_router_reason_to_category(router_reason)
-    if mapped_router and mapped_router != "other":
-        return QuestionCategoryResult(
-            category=mapped_router,
-            confidence=0.75,
-            source="router_reason",
-        )
-
-    if mapped_router == "other":
-        return QuestionCategoryResult(
-            category="other",
-            confidence=0.35,
-            source="router_reason",
-        )
-
-    return QuestionCategoryResult(
-        category="other",
-        confidence=0.0,
-        source="fallback",
-    )
```

### 5B: features/knowledge_base/ package (NEW)
```diff
```

### 5B: Old features/ files DELETED (moved to knowledge_base/)
```diff
diff --git a/backend/src/agent_service/features/faq_classifier.py b/backend/src/agent_service/features/faq_classifier.py
deleted file mode 100644
index 0ee160c..0000000
--- a/backend/src/agent_service/features/faq_classifier.py
+++ /dev/null
@@ -1,141 +0,0 @@
-"""LLM-based FAQ categorization using Groq API."""
-
-from __future__ import annotations
-
-import json
-import logging
-import os
-from typing import Any
-
-from src.agent_service.core.config import GROQ_API_KEYS, GROQ_BASE_URL
-from src.agent_service.core.http_client import get_http_client
-from src.agent_service.core.prompts import prompt_manager
-
-log = logging.getLogger(__name__)
-
-FAQ_CLASSIFIER_MODEL = os.getenv("FAQ_CLASSIFIER_MODEL", "openai/gpt-oss-120b").strip()
-BATCH_SIZE = int(os.getenv("FAQ_CLASSIFIER_BATCH_SIZE", "30"))
-
-
-async def classify_faqs(
-    items: list[dict[str, Any]],
-    category_labels: list[str],
-) -> list[dict[str, Any]]:
-    """Classify a list of FAQ items into categories using Groq LLM.
-
-    Populates the 'category' field on each item.  Items that already have
-    a category are left unchanged.  If classification fails, items are
-    returned unchanged (empty category defaults to 'technical' downstream).
-    """
-    if not items or not category_labels or not GROQ_API_KEYS:
-        return items
-
-    # Split items needing classification
-    needs_classification: list[tuple[int, dict[str, Any]]] = [
-        (i, item) for i, item in enumerate(items) if not (item.get("category") or "").strip()
-    ]
-    if not needs_classification:
-        return items
-
-    indices, to_classify_tuple = zip(*needs_classification, strict=True)
-    to_classify: list[dict[str, Any]] = list(to_classify_tuple)
-    batches = [to_classify[i : i + BATCH_SIZE] for i in range(0, len(to_classify), BATCH_SIZE)]
-
-    all_categories: list[str] = []
-    for batch in batches:
-        categories = await _classify_batch(batch, category_labels)
-        all_categories.extend(categories)
-
-    # Apply classifications back — immutable: build new list with new dicts
-    result = list(items)
-    for idx, category in zip(indices, all_categories, strict=True):
-        if category:
-            result[idx] = {**result[idx], "category": category}
-
-    return result
-
-
-async def _classify_batch(
-    batch: list[dict[str, Any]],
-    category_labels: list[str],
-) -> list[str]:
-    """Classify a single batch of FAQs via Groq API."""
-    try:
-        faqs_payload = [
-            {
-                "index": i,
-                "question": (item.get("question") or "")[:500],
-                "answer_preview": (item.get("answer") or "")[:200],
-            }
-            for i, item in enumerate(batch)
-        ]
-
-        system_content = prompt_manager.get_template("faq_classifier", "system_prompt")
-
-        messages = [
-            {
-                "role": "system",
-                "content": system_content,
-            },
-            {
-                "role": "user",
-                "content": json.dumps(
-                    {
-                        "categories": category_labels,
-                        "faqs": faqs_payload,
-                    },
-                    ensure_ascii=False,
-                ),
-            },
-        ]
-
-        payload: dict[str, Any] = {
-            "model": FAQ_CLASSIFIER_MODEL,
-            "messages": messages,
-            "temperature": 0,
-            "response_format": {"type": "json_object"},
-        }
-
-        headers = {
-            "Authorization": f"Bearer {GROQ_API_KEYS[0]}",
-            "Content-Type": "application/json",
-        }
-
-        client = await get_http_client()
-        response = await client.post(
-            f"{GROQ_BASE_URL.rstrip('/')}/openai/v1/chat/completions",
-            json=payload,
-            headers=headers,
-            timeout=30.0,
-        )
-        response.raise_for_status()
-
-        body = response.json()
-        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
-        if not content:
-            log.warning("FAQ classifier: empty response from Groq")
-            return [""] * len(batch)
-
-        parsed = json.loads(content)
-        classifications = parsed.get("classifications", [])
-        if not isinstance(classifications, list):
-            log.warning("FAQ classifier: response missing 'classifications' array")
-            return [""] * len(batch)
-
-        # Build a set of valid category labels (lowered) for validation
-        valid_labels = {c.lower() for c in category_labels}
-
-        # Map index -> category
-        by_index: dict[int, str] = {}
-        for entry in classifications:
-            if isinstance(entry, dict):
-                idx = entry.get("index")
-                cat = str(entry.get("category", "")).strip().lower()
-                if isinstance(idx, int) and cat in valid_labels:
-                    by_index[idx] = cat
-
-        return [by_index.get(i, "") for i in range(len(batch))]
-
-    except Exception:
-        log.warning("FAQ classifier batch failed", exc_info=True)
-        return [""] * len(batch)
diff --git a/backend/src/agent_service/features/faq_pdf_parser.py b/backend/src/agent_service/features/faq_pdf_parser.py
deleted file mode 100644
index ddab824..0000000
--- a/backend/src/agent_service/features/faq_pdf_parser.py
+++ /dev/null
@@ -1,69 +0,0 @@
-from __future__ import annotations
-
-import io
-import re
-from typing import Any
-
-import pdfplumber
-
-_QA_PATTERN = re.compile(
-    r"Question:\s*(.*?)\s*Answer:\s*(.*?)(?=\nQuestion:|\Z)",
-    re.IGNORECASE | re.DOTALL,
-)
-
-
-def _clean_text(value: str) -> str:
-    return re.sub(r"\s+", " ", (value or "")).strip()
-
-
-def parse_pdf_faqs(pdf_bytes: bytes) -> list[dict[str, str]]:
-    if not pdf_bytes:
-        return []
-
-    pages: list[str] = []
-    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
-        for page in pdf.pages:
-            text = page.extract_text(x_tolerance=1)
-            if text:
-                pages.append(text)
-
-    full_text = "\n".join(pages)
-    pairs: list[dict[str, str]] = []
-
-    for match in _QA_PATTERN.finditer(full_text):
-        question = _clean_text(match.group(1))
-        answer = _clean_text(match.group(2))
-        if not question or not answer:
-            continue
-        pairs.append({"question": question, "answer": answer})
-
-    return pairs
-
-
-def coerce_json_items(payload: Any) -> list[dict[str, Any]]:
-    if not isinstance(payload, list):
-        return []
-    rows: list[dict[str, Any]] = []
-    for item in payload:
-        if not isinstance(item, dict):
-            continue
-        q = _clean_text(str(item.get("question") or ""))
-        a = _clean_text(str(item.get("answer") or ""))
-        if not q or not a:
-            continue
-        tags: list[str] = []
-        raw_tags = item.get("tags")
-        if isinstance(raw_tags, str):
-            tags = [_clean_text(tag) for tag in raw_tags.split(",") if _clean_text(tag)]
-        elif isinstance(raw_tags, list):
-            tags = [_clean_text(str(tag)) for tag in raw_tags if _clean_text(str(tag))]
-
-        rows.append(
-            {
-                "question": q,
-                "answer": a,
-                "category": _clean_text(str(item.get("category") or "")),
-                "tags": tags,
-            }
-        )
-    return rows
diff --git a/backend/src/agent_service/features/kb_milvus_store.py b/backend/src/agent_service/features/kb_milvus_store.py
deleted file mode 100644
index f8b3344..0000000
--- a/backend/src/agent_service/features/kb_milvus_store.py
+++ /dev/null
@@ -1,96 +0,0 @@
-from __future__ import annotations
-
-import logging
-from typing import Any
-
-from langchain_core.documents import Document
-
-from src.agent_service.features.knowledge_base_repo import (
-    VECTOR_STATUS_FAILED,
-    VECTOR_STATUS_SYNCED,
-    VECTOR_STATUS_SYNCING,
-    KnowledgeBaseRepo,
-    normalize_question,
-)
-from src.common.milvus_mgr import milvus_mgr
-
-log = logging.getLogger("kb_milvus_store")
-
-_repo = KnowledgeBaseRepo()
-
-
-class KBMilvusStore:
-    """Thin async wrapper around ``milvus_mgr.kb_faqs`` for FAQ vector ops.
-
-    All public methods are fully async — no executor wrappers needed because
-    langchain-milvus implements native async via ``aadd_documents``,
-    ``asimilarity_search_with_score``, and ``adelete``.
-    """
-
-    async def sync_faq(self, pool: Any, item: dict[str, Any]) -> None:
-        """Upsert a single FAQ embedding into Milvus and update vector_status in PostgreSQL."""
-        question_key: str = str(
-            item.get("question_key") or normalize_question(str(item.get("question") or ""))
-        )
-        if not question_key:
-            return
-
-        await _repo.set_vector_status_for_question_keys(
-            pool, [question_key], status=VECTOR_STATUS_SYNCING, error=None
-        )
-        try:
-            doc = Document(
-                page_content=(f"Question: {item['question']}\nAnswer: {item['answer']}"),
-                metadata={
-                    "question_key": question_key,
-                    "question": item.get("question", ""),
-                    "answer": item.get("answer", ""),
-                    "category": item.get("category", ""),
-                },
-            )
-            await milvus_mgr.kb_faqs.aadd_documents([doc], ids=[question_key])  # type: ignore[union-attr]
-            await _repo.set_vector_status_for_question_keys(
-                pool, [question_key], status=VECTOR_STATUS_SYNCED, error=None
-            )
-        except Exception as exc:
-            log.error("Milvus sync_faq failed for key=%s: %s", question_key, exc)
-            await _repo.set_vector_status_for_question_keys(
-                pool, [question_key], status=VECTOR_STATUS_FAILED, error=str(exc)[:1000]
-            )
-            raise
-
-    async def sync_all(self, pool: Any, items: list[dict[str, Any]]) -> None:
-        """Full resync — clear collection then batch-upsert all FAQs."""
-        await self.clear()
-        for item in items:
-            if item.get("question") and item.get("answer"):
-                try:
-                    await self.sync_faq(pool, item)
-                except Exception:
-                    # Individual failures are already logged and status-tracked by sync_faq; continue bulk sync
-                    continue
-
-    async def semantic_search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
-        """Return top-k FAQ matches by cosine similarity (score 0–1, higher = better)."""
-        results = await milvus_mgr.kb_faqs.asimilarity_search_with_score(  # type: ignore[union-attr]
-            query, k=limit
-        )
-        return [
-            {
-                "question": doc.metadata.get("question", ""),
-                "answer": doc.metadata.get("answer", ""),
-                "score": float(score),
-            }
-            for doc, score in results
-        ]
-
-    async def clear(self) -> None:
-        """Delete all documents from the kb_faqs Milvus collection."""
-        try:
-            # adelete with expr="" deletes everything (Milvus boolean expr on metadata field)
-            await milvus_mgr.kb_faqs.adelete(expr="question_key != ''")  # type: ignore[union-attr]
-        except Exception as exc:
-            log.warning("Milvus clear (kb_faqs) failed: %s", exc)
-
-
-kb_milvus_store = KBMilvusStore()
diff --git a/backend/src/agent_service/features/knowledge_base_repo.py b/backend/src/agent_service/features/knowledge_base_repo.py
deleted file mode 100644
index c1c05a4..0000000
--- a/backend/src/agent_service/features/knowledge_base_repo.py
+++ /dev/null
@@ -1,673 +0,0 @@
-from __future__ import annotations
-
-import asyncio
-import hashlib
-import re
-import uuid
-from typing import Any, Iterable
-
-_table_ready = False
-_table_lock = asyncio.Lock()
-DEFAULT_CATEGORY_ID = "technical"
-VECTOR_STATUS_PENDING = "pending"
-VECTOR_STATUS_SYNCING = "syncing"
-VECTOR_STATUS_SYNCED = "synced"
-VECTOR_STATUS_FAILED = "failed"
-_VECTOR_STATUS_VALUES = {
-    VECTOR_STATUS_PENDING,
-    VECTOR_STATUS_SYNCING,
-    VECTOR_STATUS_SYNCED,
-    VECTOR_STATUS_FAILED,
-}
-_DEFAULT_CATEGORIES: tuple[tuple[str, str, str], ...] = (
-    ("billing", "billing", "Billing"),
-    ("account", "account", "Account"),
-    ("data", "data", "Data"),
-    ("technical", "technical", "Technical"),
-    ("sales", "sales", "Sales"),
-)
-
-
-def normalize_question(value: str) -> str:
-    return re.sub(r"\s+", " ", (value or "").strip().lower())
-
-
-def content_hash(question: str, answer: str) -> str:
-    payload = f"{normalize_question(question)}::{(answer or '').strip()}"
-    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
-
-
-def _normalize_category(value: str | None) -> str:
-    if not value:
-        return ""
-    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
-    return normalized
-
-
-def _normalize_tags(value: Any) -> list[str]:
-    if value is None:
-        return []
-    if isinstance(value, str):
-        source = value.split(",")
-    elif isinstance(value, list):
-        source = value
-    else:
-        return []
-
-    tags: list[str] = []
-    seen = set()
-    for tag in source:
-        text = re.sub(r"\s+", " ", str(tag or "")).strip().lower()
-        if not text or text in seen:
-            continue
-        seen.add(text)
-        tags.append(text)
-    return tags
-
-
-def _build_category_lookup(rows: list[dict[str, Any]]) -> dict[str, str]:
-    lookup: dict[str, str] = {}
-    for row in rows:
-        category_id = str(row["id"])
-        candidates = {
-            category_id,
-            _normalize_category(str(row["slug"])),
-            _normalize_category(str(row["label"])),
-            str(row["slug"]).strip().lower(),
-            str(row["label"]).strip().lower(),
-        }
-        for candidate in candidates:
-            if candidate:
-                lookup[candidate] = category_id
-    return lookup
-
-
-def _resolve_category_id_from_lookup(
-    category: str | None,
-    category_lookup: dict[str, str],
-    category_labels: list[str],
-) -> str:
-    if not category or not category.strip():
-        return DEFAULT_CATEGORY_ID
-
-    raw = category.strip()
-    key = _normalize_category(raw)
-    if key in category_lookup:
-        return category_lookup[key]
-
-    lower = raw.lower()
-    if lower in category_lookup:
-        return category_lookup[lower]
-
-    available = ", ".join(category_labels)
-    raise ValueError(f"Unknown category '{raw}'. Allowed categories: {available}")
-
-
-class KnowledgeBaseRepo:
-    async def ensure_table(self, pool: Any) -> None:
-        global _table_ready
-        if _table_ready:
-            return
-
-        async with _table_lock:
-            if _table_ready:
-                return
-
-            await pool.execute("""
-                CREATE TABLE IF NOT EXISTS public.faq_categories (
-                    category_id text PRIMARY KEY,
-                    slug text NOT NULL UNIQUE,
-                    label text NOT NULL UNIQUE,
-                    is_active boolean NOT NULL DEFAULT true,
-                    created_at timestamptz NOT NULL DEFAULT now(),
-                    updated_at timestamptz NOT NULL DEFAULT now()
-                )
-                """)
-            await pool.executemany(
-                """
-                INSERT INTO public.faq_categories (category_id, slug, label, is_active, created_at, updated_at)
-                VALUES ($1, $2, $3, true, now(), now())
-                ON CONFLICT (category_id)
-                DO UPDATE
-                SET slug = EXCLUDED.slug,
-                    label = EXCLUDED.label,
-                    is_active = true,
-                    updated_at = now()
-                """,
-                _DEFAULT_CATEGORIES,
-            )
-
-            await pool.execute("""
-                CREATE TABLE IF NOT EXISTS public.nbfc_faqs (
-                    id bigserial PRIMARY KEY,
-                    faq_id text,
-                    question_key text NOT NULL UNIQUE,
-                    question text NOT NULL,
-                    answer text NOT NULL,
-                    category_id text,
-                    tags text[] DEFAULT '{}',
-                    vector_status text,
-                    vector_error text,
-                    vector_updated_at timestamptz,
-                    source text NOT NULL DEFAULT 'manual',
-                    source_ref text,
-                    content_hash text NOT NULL,
-                    created_at timestamptz NOT NULL DEFAULT now(),
-                    updated_at timestamptz NOT NULL DEFAULT now()
-                )
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ADD COLUMN IF NOT EXISTS faq_id text
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ADD COLUMN IF NOT EXISTS category_id text
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ADD COLUMN IF NOT EXISTS tags text[] DEFAULT '{}'
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ADD COLUMN IF NOT EXISTS vector_status text
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ADD COLUMN IF NOT EXISTS vector_error text
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ADD COLUMN IF NOT EXISTS vector_updated_at timestamptz
-                """)
-
-            rows_missing_ids = await pool.fetch("""
-                SELECT id
-                FROM public.nbfc_faqs
-                WHERE faq_id IS NULL OR faq_id = ''
-                """)
-            if rows_missing_ids:
-                await pool.executemany(
-                    """
-                    UPDATE public.nbfc_faqs
-                    SET faq_id = $1
-                    WHERE id = $2
-                    """,
-                    [(str(uuid.uuid4()), row["id"]) for row in rows_missing_ids],
-                )
-
-            await pool.execute(
-                """
-                UPDATE public.nbfc_faqs
-                SET category_id = $1
-                WHERE category_id IS NULL OR category_id = ''
-                """,
-                DEFAULT_CATEGORY_ID,
-            )
-            await pool.execute("""
-                UPDATE public.nbfc_faqs
-                SET tags = '{}'::text[]
-                WHERE tags IS NULL
-                """)
-            await pool.execute(
-                """
-                UPDATE public.nbfc_faqs
-                SET vector_status = $1
-                WHERE vector_status IS NULL OR vector_status = ''
-                """,
-                VECTOR_STATUS_PENDING,
-            )
-
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ALTER COLUMN faq_id SET NOT NULL
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ALTER COLUMN category_id SET DEFAULT 'technical'
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ALTER COLUMN category_id SET NOT NULL
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ALTER COLUMN tags SET DEFAULT '{}'::text[]
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ALTER COLUMN tags SET NOT NULL
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ALTER COLUMN vector_status SET DEFAULT 'pending'
-                """)
-            await pool.execute("""
-                ALTER TABLE public.nbfc_faqs
-                ALTER COLUMN vector_status SET NOT NULL
-                """)
-
-            await pool.execute("""
-                DO $$
-                BEGIN
-                    IF NOT EXISTS (
-                        SELECT 1
-                        FROM pg_constraint
-                        WHERE conname = 'nbfc_faqs_category_fk'
-                    ) THEN
-                        ALTER TABLE public.nbfc_faqs
-                        ADD CONSTRAINT nbfc_faqs_category_fk
-                        FOREIGN KEY (category_id)
-                        REFERENCES public.faq_categories(category_id);
-                    END IF;
-                END $$;
-                """)
-            await pool.execute("""
-                DO $$
-                BEGIN
-                    IF NOT EXISTS (
-                        SELECT 1
-                        FROM pg_constraint
-                        WHERE conname = 'nbfc_faqs_vector_status_check'
-                    ) THEN
-                        ALTER TABLE public.nbfc_faqs
-                        ADD CONSTRAINT nbfc_faqs_vector_status_check
-                        CHECK (vector_status IN ('pending', 'syncing', 'synced', 'failed'));
-                    END IF;
-                END $$;
-                """)
-
-            await pool.execute("""
-                CREATE UNIQUE INDEX IF NOT EXISTS idx_nbfc_faqs_faq_id
-                ON public.nbfc_faqs (faq_id)
-                """)
-            await pool.execute("""
-                CREATE INDEX IF NOT EXISTS idx_nbfc_faqs_updated_at
-                ON public.nbfc_faqs (updated_at DESC)
-                """)
-            await pool.execute("""
-                CREATE INDEX IF NOT EXISTS idx_nbfc_faqs_question
-                ON public.nbfc_faqs (question)
-                """)
-            await pool.execute("""
-                CREATE INDEX IF NOT EXISTS idx_nbfc_faqs_category
-                ON public.nbfc_faqs (category_id)
-                """)
-
-            _table_ready = True
-
-    async def list_faqs(self, pool: Any, limit: int, skip: int) -> list[dict[str, Any]]:
-        await self.ensure_table(pool)
-        rows = await pool.fetch(
-            """
-            SELECT
-                f.faq_id,
-                f.question,
-                f.answer,
-                f.created_at,
-                f.updated_at,
-                COALESCE(c.label, 'Technical') AS category,
-                f.tags,
-                f.vector_status,
-                f.vector_error,
-                f.vector_updated_at
-            FROM public.nbfc_faqs f
-            LEFT JOIN public.faq_categories c ON c.category_id = f.category_id
-            ORDER BY updated_at DESC
-            OFFSET $1
-            LIMIT $2
-            """,
-            skip,
-            limit,
-        )
-        return [
-            {
-                "id": row["faq_id"],
-                "question": row["question"],
-                "answer": row["answer"],
-                "category": row["category"] or "Technical",
-                "tags": list(row["tags"] or []),
-                "vector_status": row["vector_status"] or VECTOR_STATUS_PENDING,
-                "vectorized": (row["vector_status"] or VECTOR_STATUS_PENDING)
-                == VECTOR_STATUS_SYNCED,
-                "vector_error": row["vector_error"],
-                "vector_updated_at": (
-                    row["vector_updated_at"].isoformat() if row["vector_updated_at"] else None
-                ),
-                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
-                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
-            }
-            for row in rows
-        ]
-
-    async def list_categories(self, pool: Any) -> list[dict[str, Any]]:
-        await self.ensure_table(pool)
-        rows = await pool.fetch("""
-            SELECT category_id, slug, label, is_active
-            FROM public.faq_categories
-            WHERE is_active = true
-            ORDER BY label ASC
-            """)
-        return [
-            {
-                "id": row["category_id"],
-                "slug": row["slug"],
-                "label": row["label"],
-                "is_active": row["is_active"],
-            }
-            for row in rows
-        ]
-
-    async def resolve_category_id(self, pool: Any, category: str | None) -> str:
-        await self.ensure_table(pool)
-        categories = await self.list_categories(pool)
-        return _resolve_category_id_from_lookup(
-            category,
-            _build_category_lookup(categories),
-            [str(row["label"]) for row in categories],
-        )
-
-    async def upsert_many(
-        self,
-        pool: Any,
-        items: Iterable[dict[str, Any]],
-        *,
-        source: str,
-        source_ref: str | None = None,
-    ) -> int:
-        await self.ensure_table(pool)
-        categories = await self.list_categories(pool)
-        category_lookup = _build_category_lookup(categories)
-        category_labels = [str(row["label"]) for row in categories]
-        rows = []
-        for item in items:
-            question = (item.get("question") or "").strip()
-            answer = (item.get("answer") or "").strip()
-            if not question or not answer:
-                continue
-            category_id = _resolve_category_id_from_lookup(
-                str(item.get("category") or ""),
-                category_lookup,
-                category_labels,
-            )
-            tags = _normalize_tags(item.get("tags"))
-            rows.append(
-                {
-                    "faq_id": str(item.get("id") or "").strip() or str(uuid.uuid4()),
-                    "question_key": normalize_question(question),
-                    "question": question,
-                    "answer": answer,
-                    "category_id": category_id,
-                    "tags": tags,
-                    "source": source,
-                    "source_ref": source_ref,
-                    "content_hash": content_hash(question, answer),
-                }
-            )
-
-        if not rows:
-            return 0
-
-        await pool.executemany(
-            """
-            INSERT INTO public.nbfc_faqs (
-                faq_id,
-                question_key,
-                question,
-                answer,
-                category_id,
-                tags,
-                vector_status,
-                vector_error,
-                vector_updated_at,
-                source,
-                source_ref,
-                content_hash,
-                created_at,
-                updated_at
-            )
-            VALUES ($1, $2, $3, $4, $5, $6, $7, NULL, NULL, $8, $9, $10, now(), now())
-            ON CONFLICT (question_key)
-            DO UPDATE
-              SET question = EXCLUDED.question,
-                  answer = EXCLUDED.answer,
-                  category_id = EXCLUDED.category_id,
-                  tags = EXCLUDED.tags,
-                  vector_status = EXCLUDED.vector_status,
-                  vector_error = NULL,
-                  vector_updated_at = NULL,
-                  source = EXCLUDED.source,
-                  source_ref = EXCLUDED.source_ref,
-                  content_hash = EXCLUDED.content_hash,
-                  updated_at = now()
-            """,
-            [
-                (
-                    row["faq_id"],
-                    row["question_key"],
-                    row["question"],
-                    row["answer"],
-                    row["category_id"],
-                    row["tags"],
-                    VECTOR_STATUS_PENDING,
-                    row["source"],
-                    row["source_ref"],
-                    row["content_hash"],
-                )
-                for row in rows
-            ],
-        )
-        return len(rows)
-
-    async def update_one(
-        self,
-        pool: Any,
-        *,
-        faq_id: str | None,
-        original_question: str | None,
-        new_question: str | None,
-        new_answer: str | None,
-        new_category: str | None,
-        new_tags: list[str] | None,
-    ) -> bool:
-        await self.ensure_table(pool)
-        identifier_id = (faq_id or "").strip()
-        original_key = normalize_question(original_question or "")
-        row = None
-        if identifier_id:
-            row = await pool.fetchrow(
-                """
-                SELECT faq_id, question, answer, category_id, tags
-                FROM public.nbfc_faqs
-                WHERE faq_id = $1
-                """,
-                identifier_id,
-            )
-        if row is None and original_key:
-            row = await pool.fetchrow(
-                """
-                SELECT faq_id, question, answer, category_id, tags
-                FROM public.nbfc_faqs
-                WHERE question_key = $1
-                """,
-                original_key,
-            )
-        if row is None:
-            return False
-
-        final_question = (new_question or row["question"] or "").strip()
-        final_answer = (new_answer or row["answer"] or "").strip()
-        if not final_question or not final_answer:
-            return False
-        final_category = await self.resolve_category_id(pool, new_category or row["category_id"])
-        final_tags = _normalize_tags(new_tags if new_tags is not None else row["tags"])
-        target_key = normalize_question(final_question)
-
-        await pool.execute(
-            """
-            UPDATE public.nbfc_faqs
-            SET question_key = $1,
-                question = $2,
-                answer = $3,
-                category_id = $4,
-                tags = $5,
-                source = 'manual_edit',
-                source_ref = NULL,
-                content_hash = $6,
-                vector_status = $7,
-                vector_error = NULL,
-                vector_updated_at = NULL,
-                updated_at = now()
-            WHERE faq_id = $8
-            """,
-            target_key,
-            final_question,
-            final_answer,
-            final_category,
-            final_tags,
-            content_hash(final_question, final_answer),
-            VECTOR_STATUS_PENDING,
-            row["faq_id"],
-        )
-        return True
-
-    async def delete_one(
-        self,
-        pool: Any,
-        *,
-        faq_id: str | None = None,
-        question: str | None = None,
-    ) -> int:
-        await self.ensure_table(pool)
-        target_id = (faq_id or "").strip()
-        if target_id:
-            result = await pool.execute(
-                """
-                DELETE FROM public.nbfc_faqs
-                WHERE faq_id = $1
-                """,
-                target_id,
-            )
-        else:
-            result = await pool.execute(
-                """
-                DELETE FROM public.nbfc_faqs
-                WHERE question_key = $1
-                """,
-                normalize_question(question or ""),
-            )
-        # asyncpg returns: DELETE <n>
-        return int(str(result).split()[-1])
-
-    async def delete_all(self, pool: Any) -> int:
-        await self.ensure_table(pool)
-        result = await pool.execute("DELETE FROM public.nbfc_faqs")
-        return int(str(result).split()[-1])
-
-    async def search_local(self, pool: Any, query: str, limit: int = 5) -> list[dict[str, Any]]:
-        await self.ensure_table(pool)
-        q = (query or "").strip()
-        if not q:
-            return []
-
-        # Full-text search with ts_rank for real relevance scores.
-        # ts_rank_cd(..., 32) uses rank/(rank+1) normalization → scores bounded in (0, 1).
-        rows = await pool.fetch(
-            """
-            SELECT
-                question,
-                answer,
-                ts_rank_cd(
-                    to_tsvector('english', question || ' ' || answer),
-                    plainto_tsquery('english', $1),
-                    32
-                ) AS score
-            FROM public.nbfc_faqs
-            WHERE to_tsvector('english', question || ' ' || answer)
-                    @@ plainto_tsquery('english', $1)
-            ORDER BY score DESC
-            LIMIT $2
-            """,
-            q,
-            limit,
-        )
-
-        if rows:
-            return [
-                {
-                    "question": row["question"],
-                    "answer": row["answer"],
-                    "score": float(row["score"]),
-                }
-                for row in rows
-            ]
-
-        # Fallback: ILIKE substring match when FTS yields nothing (e.g. very short
-        # queries, stop-words only). Score is a low constant to signal low confidence.
-        ilike_rows = await pool.fetch(
-            """
-            SELECT question, answer
-            FROM public.nbfc_faqs
-            WHERE question ILIKE ('%' || $1 || '%')
-               OR answer ILIKE ('%' || $1 || '%')
-            ORDER BY updated_at DESC
-            LIMIT $2
-            """,
-            q,
-            limit,
-        )
-        return [
-            {
-                "question": row["question"],
-                "answer": row["answer"],
-                "score": 0.1,
-            }
-            for row in ilike_rows
-        ]
-
-    async def dump_all(self, pool: Any) -> list[dict[str, str]]:
-        await self.ensure_table(pool)
-        rows = await pool.fetch("""
-            SELECT question_key, question, answer
-            FROM public.nbfc_faqs
-            ORDER BY updated_at DESC
-            """)
-        return [
-            {
-                "question_key": row["question_key"],
-                "question": row["question"],
-                "answer": row["answer"],
-            }
-            for row in rows
-        ]
-
-    async def set_vector_status_for_question_keys(
-        self,
-        pool: Any,
-        question_keys: list[str],
-        *,
-        status: str,
-        error: str | None = None,
-    ) -> None:
-        await self.ensure_table(pool)
-        if not question_keys:
-            return
-        if status not in _VECTOR_STATUS_VALUES:
-            raise ValueError(f"Unsupported vector status: {status}")
-
-        await pool.execute(
-            """
-            UPDATE public.nbfc_faqs
-            SET vector_status = $1,
-                vector_error = $2,
-                vector_updated_at = CASE
-                    WHEN $3 THEN now()
-                    ELSE NULL
-                END
-            WHERE question_key = ANY($4::text[])
-            """,
-            status,
-            error,
-            status in {VECTOR_STATUS_SYNCED, VECTOR_STATUS_FAILED},
-            question_keys,
-        )
diff --git a/backend/src/agent_service/features/knowledge_base_service.py b/backend/src/agent_service/features/knowledge_base_service.py
deleted file mode 100644
index 1e7dc26..0000000
--- a/backend/src/agent_service/features/knowledge_base_service.py
+++ /dev/null
@@ -1,170 +0,0 @@
-from __future__ import annotations
-
-import logging
-from typing import Any, Iterable
-
-from src.agent_service.features.faq_classifier import classify_faqs
-from src.agent_service.features.faq_pdf_parser import coerce_json_items, parse_pdf_faqs
-from src.agent_service.features.kb_milvus_store import kb_milvus_store
-from src.agent_service.features.knowledge_base_repo import KnowledgeBaseRepo
-
-log = logging.getLogger("knowledge_base_service")
-
-
-class KnowledgeBaseService:
-    def __init__(self) -> None:
-        self.repo = KnowledgeBaseRepo()
-
-    async def list_faqs(self, pool: Any, limit: int, skip: int) -> list[dict[str, Any]]:
-        return await self.repo.list_faqs(pool, limit=limit, skip=skip)
-
-    async def list_categories(self, pool: Any) -> list[dict[str, Any]]:
-        return await self.repo.list_categories(pool)
-
-    async def upsert_items(
-        self,
-        pool: Any,
-        items: Iterable[dict[str, Any]],
-        *,
-        source: str,
-        source_ref: str | None = None,
-        sync_milvus: bool = True,
-    ) -> int:
-        rows = list(items)
-        count = await self.repo.upsert_many(
-            pool,
-            rows,
-            source=source,
-            source_ref=source_ref,
-        )
-        if sync_milvus and count > 0:
-            all_rows = await self.repo.dump_all(pool)
-            await self._sync_to_milvus(pool, all_rows)
-        return count
-
-    async def update_faq(
-        self,
-        pool: Any,
-        *,
-        faq_id: str | None,
-        original_question: str | None,
-        new_question: str | None,
-        new_answer: str | None,
-        new_category: str | None,
-        new_tags: list[str] | None,
-    ) -> bool:
-        updated = await self.repo.update_one(
-            pool,
-            faq_id=faq_id,
-            original_question=original_question,
-            new_question=new_question,
-            new_answer=new_answer,
-            new_category=new_category,
-            new_tags=new_tags,
-        )
-        if updated:
-            all_rows = await self.repo.dump_all(pool)
-            await self._sync_to_milvus(pool, all_rows)
-        return updated
-
-    async def delete_faq(
-        self,
-        pool: Any,
-        *,
-        faq_id: str | None = None,
-        question: str | None = None,
-    ) -> int:
-        deleted = await self.repo.delete_one(pool, faq_id=faq_id, question=question)
-        if deleted > 0:
-            all_rows = await self.repo.dump_all(pool)
-            await self._sync_to_milvus(pool, all_rows)
-        return deleted
-
-    async def clear_all(self, pool: Any) -> int:
-        deleted = await self.repo.delete_all(pool)
-        await kb_milvus_store.clear()
-        return deleted
-
-    async def semantic_search(
-        self, pool: Any, *, query: str, limit: int = 5
-    ) -> list[dict[str, Any]]:
-        query_text = (query or "").strip()
-        if not query_text:
-            return []
-
-        try:
-            rows = await kb_milvus_store.semantic_search(query_text, limit=limit)
-            if rows:
-                return rows
-        except Exception as exc:  # noqa: BLE001
-            log.warning("Milvus semantic search failed, using local fallback: %s", exc)
-
-        return await self.repo.search_local(pool, query_text, limit=limit)
-
-    async def semantic_delete(self, pool: Any, *, query: str, threshold: float = 0.9) -> int:
-        query_text = (query or "").strip().lower()
-        if not query_text:
-            return 0
-
-        try:
-            results = await kb_milvus_store.semantic_search(query_text, limit=100)
-        except Exception as exc:  # noqa: BLE001
-            log.warning("Milvus semantic delete search failed: %s", exc)
-            raise RuntimeError(f"Milvus semantic delete search failed: {exc}") from exc
-
-        to_delete = [r for r in results if r["score"] >= threshold]
-
-        if not to_delete:
-            return 0
-
-        deleted = 0
-        for item in to_delete:
-            deleted += await self.repo.delete_one(pool, question=item["question"])
-
-        all_rows = await self.repo.dump_all(pool)
-        await self._sync_to_milvus(pool, all_rows)
-        return deleted
-
-    async def ingest_json_payload(self, pool: Any, payload: Any) -> int:
-        items = coerce_json_items(payload)
-        items = await self._auto_classify(pool, items)
-        return await self.upsert_items(pool, items, source="json_batch")
-
-    async def ingest_pdf_bytes(self, pool: Any, pdf_bytes: bytes, filename: str) -> int:
-        items = parse_pdf_faqs(pdf_bytes)
-        items = await self._auto_classify(pool, items)
-        return await self.upsert_items(
-            pool,
-            items,
-            source="pdf_upload",
-            source_ref=filename,
-        )
-
-    async def _auto_classify(self, pool: Any, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
-        """Best-effort LLM classification for items missing a category.
-
-        Never blocks or fails the ingest pipeline — returns items unchanged
-        if anything goes wrong.
-        """
-        try:
-            categories = await self.repo.list_categories(pool)
-            labels = [str(c.get("slug") or c.get("label", "")).strip() for c in categories]
-            labels = [lb for lb in labels if lb]
-            if not labels:
-                return items
-            return await classify_faqs(items, labels)
-        except Exception:  # noqa: BLE001
-            log.warning(
-                "Auto-classify failed; items ingested without classification", exc_info=True
-            )
-            return items
-
-    async def _sync_to_milvus(self, pool: Any, items: list[dict[str, Any]]) -> None:
-        """Full resync of all FAQ embeddings to Milvus kb_faqs collection."""
-        try:
-            await kb_milvus_store.sync_all(pool, items)
-        except Exception as exc:  # noqa: BLE001
-            log.warning("Milvus sync failed: %s", exc)
-
-
-knowledge_base_service = KnowledgeBaseService()
```

### 5A-5F: Import updates + DedupToolNode + test updates
```diff
diff --git a/backend/src/agent_service/api/admin.py b/backend/src/agent_service/api/admin.py
index 5b1275f..0c0ac2e 100644
--- a/backend/src/agent_service/api/admin.py
+++ b/backend/src/agent_service/api/admin.py
@@ -8,7 +8,7 @@ from sse_starlette.sse import EventSourceResponse
 
 from src.agent_service.api.admin_auth import require_admin_key
 from src.agent_service.core.config import KB_FAQ_BATCH_MAX_ITEMS, KB_FAQ_PDF_MAX_BYTES
-from src.agent_service.features.knowledge_base_service import knowledge_base_service
+from src.agent_service.features.knowledge_base.service import knowledge_base_service
 
 log = logging.getLogger("admin_api")
 router = APIRouter(dependencies=[Depends(require_admin_key)])
diff --git a/backend/src/agent_service/api/endpoints/agent_query.py b/backend/src/agent_service/api/endpoints/agent_query.py
index 931f7b3..48831bb 100644
--- a/backend/src/agent_service/api/endpoints/agent_query.py
+++ b/backend/src/agent_service/api/endpoints/agent_query.py
@@ -13,7 +13,7 @@ from src.agent_service.core.recursive_rag_graph import (
 from src.agent_service.core.resource_resolver import resource_resolver
 from src.agent_service.core.schemas import AgentRequest
 from src.agent_service.core.session_utils import session_utils
-from src.agent_service.features.nbfc_router import nbfc_router_service
+from src.agent_service.features.routing.nbfc_router import nbfc_router_service
 
 log = logging.getLogger(__name__)
 router = APIRouter(prefix="/agent", tags=["agent-query"])
diff --git a/backend/src/agent_service/api/endpoints/agent_stream.py b/backend/src/agent_service/api/endpoints/agent_stream.py
index b32e8c5..6471e4e 100644
--- a/backend/src/agent_service/api/endpoints/agent_stream.py
+++ b/backend/src/agent_service/api/endpoints/agent_stream.py
@@ -32,7 +32,7 @@ from src.agent_service.core.session_cost import get_session_cost_tracker
 from src.agent_service.core.session_utils import session_utils
 from src.agent_service.core.streaming_utils import StreamingState, sse_formatter, streaming_utils
 from src.agent_service.eval_store.shadow_queue import trace_queue
-from src.agent_service.features.nbfc_router import nbfc_router_service
+from src.agent_service.features.routing.nbfc_router import nbfc_router_service
 from src.agent_service.features.runtime_trace_store import persist_runtime_trace
 from src.agent_service.features.shadow_eval import ShadowEvalCollector, maybe_shadow_eval_commit
 from src.agent_service.security.inline_guard import evaluate_prompt_safety_decision
diff --git a/backend/src/agent_service/api/endpoints/router_endpoints.py b/backend/src/agent_service/api/endpoints/router_endpoints.py
index 6949a70..666bb53 100644
--- a/backend/src/agent_service/api/endpoints/router_endpoints.py
+++ b/backend/src/agent_service/api/endpoints/router_endpoints.py
@@ -6,7 +6,7 @@ from fastapi import APIRouter, HTTPException
 
 from src.agent_service.core.schemas import RouterClassifyRequest
 from src.agent_service.core.session_utils import valid_session_id
-from src.agent_service.features.nbfc_router import nbfc_router_service
+from src.agent_service.features.routing.nbfc_router import nbfc_router_service
 from src.agent_service.tools.mcp_manager import mcp_manager
 
 log = logging.getLogger(__name__)
diff --git a/backend/src/agent_service/core/recursive_rag_graph.py b/backend/src/agent_service/core/recursive_rag_graph.py
index 0f8cc60..8f3c152 100644
--- a/backend/src/agent_service/core/recursive_rag_graph.py
+++ b/backend/src/agent_service/core/recursive_rag_graph.py
@@ -1,4 +1,4 @@
-"""Manual LangGraph Recursive RAG workflow using message-based state."""
+"""LangGraph Recursive RAG workflow using message-based state."""
 
 from __future__ import annotations
 
@@ -41,70 +41,38 @@ def _safe_tool_output(value: Any) -> str:
     return str(value)
 
 
-def build_recursive_rag_graph(
-    *,
-    model: Any,
-    tools: list[Any],
-    system_prompt: str,
-    checkpointer: Any,
-):
-    """
-    Build strict recursive RAG graph with manual StateGraph construction.
+class DedupToolNode:
+    """Graph node that executes tool calls with same-turn deduplication.
 
-    State is message-based; retrieval context flows only through message objects.
+    Encapsulates tool lookup, execution-policy-driven deduplication, and safe
+    output formatting into a single callable that plugs into a LangGraph
+    StateGraph as ``builder.add_node("run_tools", DedupToolNode(tools))``.
     """
 
-    tools_by_name = {getattr(tool, "name", ""): tool for tool in tools}
-    llm = model.bind_tools(tools) if tools else model
-
-    async def llm_step(state: RecursiveRAGState) -> dict[str, Any]:
-        messages = state.get("messages", [])
-        model_messages = [SystemMessage(content=system_prompt), *messages]
-
-        ai_message = await llm.ainvoke(model_messages)
-        if not isinstance(ai_message, AIMessage):
-            ai_message = AIMessage(content=str(ai_message))
-
-        return {"messages": [ai_message]}
+    def __init__(self, tools: list[Any]) -> None:
+        self._tools_by_name = {getattr(tool, "name", ""): tool for tool in tools}
 
-    async def run_tools(state: RecursiveRAGState) -> dict[str, Any]:
+    async def __call__(self, state: RecursiveRAGState) -> dict[str, Any]:
         messages = state.get("messages", [])
-        if not messages:
-            return {
-                "iteration": state.get("iteration", 0),
-                "tool_execution_cache": dict(state.get("tool_execution_cache", {}) or {}),
-            }
+        cache = dict(state.get("tool_execution_cache", {}) or {})
+        iteration = state.get("iteration", 0)
 
-        last_message = messages[-1]
-        if not isinstance(last_message, AIMessage):
-            return {
-                "iteration": state.get("iteration", 0),
-                "tool_execution_cache": dict(state.get("tool_execution_cache", {}) or {}),
-            }
+        if not messages or not isinstance(messages[-1], AIMessage):
+            return {"iteration": iteration, "tool_execution_cache": cache}
 
-        tool_calls = getattr(last_message, "tool_calls", []) or []
+        tool_calls = getattr(messages[-1], "tool_calls", []) or []
         if not tool_calls:
-            return {
-                "iteration": state.get("iteration", 0),
-                "tool_execution_cache": dict(state.get("tool_execution_cache", {}) or {}),
-            }
+            return {"iteration": iteration, "tool_execution_cache": cache}
 
         tool_messages: list[ToolMessage] = []
-        tool_execution_cache = dict(state.get("tool_execution_cache", {}) or {})
         for tool_call in tool_calls:
             tool_name = tool_call.get("name", "")
             tool_args = tool_call.get("args", {}) or {}
             if not isinstance(tool_args, dict):
                 tool_args = {"input": tool_args}
             tool_call_id = tool_call.get("id") or tool_name or "tool-call"
-            policy = get_tool_execution_policy(tool_name)
-            dedupe_key = (
-                build_same_turn_dedupe_key(tool_name, tool_args)
-                if policy.same_turn_dedupe
-                else None
-            )
 
-            tool = tools_by_name.get(tool_name)
+            tool = self._tools_by_name.get(tool_name)
             if tool is None:
                 tool_messages.append(
                     ToolMessage(
@@ -115,22 +83,10 @@ def build_recursive_rag_graph(
                 )
                 continue
 
-            if dedupe_key and dedupe_key in tool_execution_cache:
-                content = tool_execution_cache[dedupe_key]
-                log.info(
-                    "Suppressing duplicate side-effect tool call within run tool=%s dedupe_key=%s",
-                    tool_name,
-                    dedupe_key,
-                )
-            else:
-                try:
-                    result = await tool.ainvoke(tool_args)
-                    content = _safe_tool_output(result)
-                except Exception as exc:
-                    log.warning("Tool invocation failed for %s: %r", tool_name, exc)
-                    content = f"Tool '{tool_name}' failed: {exc}"
-                if dedupe_key:
-                    tool_execution_cache[dedupe_key] = content
+            content = self._execute_with_dedupe(tool_name, tool_args, tool_call_id, tool, cache)
+            if content is None:
+                # Not cached — must await actual execution
+                content = await self._invoke_tool(tool_name, tool_args, tool, cache)
 
             tool_messages.append(
                 ToolMessage(content=content, tool_call_id=tool_call_id, name=tool_name)
@@ -138,10 +94,81 @@ def build_recursive_rag_graph(
 
         return {
             "messages": tool_messages,
-            "iteration": state.get("iteration", 0) + 1,
-            "tool_execution_cache": tool_execution_cache,
+            "iteration": iteration + 1,
+            "tool_execution_cache": cache,
         }
 
+    def _execute_with_dedupe(
+        self,
+        tool_name: str,
+        tool_args: dict,
+        tool_call_id: str,
+        tool: Any,
+        cache: dict[str, str],
+    ) -> str | None:
+        """Return cached result if this is a duplicate side-effect call, else None."""
+        policy = get_tool_execution_policy(tool_name)
+        if not policy.same_turn_dedupe:
+            return None
+
+        dedupe_key = build_same_turn_dedupe_key(tool_name, tool_args)
+        if dedupe_key and dedupe_key in cache:
+            log.info(
+                "Suppressing duplicate side-effect tool call within run tool=%s dedupe_key=%s",
+                tool_name,
+                dedupe_key,
+            )
+            return cache[dedupe_key]
+        return None
+
+    async def _invoke_tool(
+        self,
+        tool_name: str,
+        tool_args: dict,
+        tool: Any,
+        cache: dict[str, str],
+    ) -> str:
+        """Invoke tool, cache result if policy requires dedup, return formatted output."""
+        policy = get_tool_execution_policy(tool_name)
+        dedupe_key = (
+            build_same_turn_dedupe_key(tool_name, tool_args)
+            if policy.same_turn_dedupe
+            else None
+        )
+
+        try:
+            result = await tool.ainvoke(tool_args)
+            content = _safe_tool_output(result)
+        except Exception as exc:
+            log.warning("Tool invocation failed for %s: %r", tool_name, exc)
+            content = f"Tool '{tool_name}' failed: {exc}"
+
+        if dedupe_key:
+            cache[dedupe_key] = content
+        return content
+
+
+def build_recursive_rag_graph(
+    *,
+    model: Any,
+    tools: list[Any],
+    system_prompt: str,
+    checkpointer: Any,
+):
+    """Build recursive RAG graph with DedupToolNode for tool execution."""
+
+    llm = model.bind_tools(tools) if tools else model
+
+    async def llm_step(state: RecursiveRAGState) -> dict[str, Any]:
+        messages = state.get("messages", [])
+        model_messages = [SystemMessage(content=system_prompt), *messages]
+
+        ai_message = await llm.ainvoke(model_messages)
+        if not isinstance(ai_message, AIMessage):
+            ai_message = AIMessage(content=str(ai_message))
+
+        return {"messages": [ai_message]}
+
     def route_after_llm(state: RecursiveRAGState) -> Literal["run_tools", "__end__"]:
         messages = state.get("messages", [])
         if not messages:
@@ -164,7 +191,7 @@ def build_recursive_rag_graph(
 
     builder = StateGraph(RecursiveRAGState)
     builder.add_node("llm_step", llm_step)
-    builder.add_node("run_tools", run_tools)
+    builder.add_node("run_tools", DedupToolNode(tools))
 
     builder.add_edge(START, "llm_step")
     builder.add_conditional_edges("llm_step", route_after_llm)
diff --git a/backend/src/agent_service/features/runtime_trace_store.py b/backend/src/agent_service/features/runtime_trace_store.py
index e4d7651..7766aeb 100644
--- a/backend/src/agent_service/features/runtime_trace_store.py
+++ b/backend/src/agent_service/features/runtime_trace_store.py
@@ -12,7 +12,7 @@ from src.agent_service.eval_store.pg_store import (
     EvalSchemaUnavailableError,
     get_shared_pool,
 )
-from src.agent_service.features.question_category import classify_question_category
+from src.agent_service.features.routing.question_category import classify_question_category
 
 log = logging.getLogger("runtime_trace_store")
 
diff --git a/backend/src/agent_service/tools/mcp_manager.py b/backend/src/agent_service/tools/mcp_manager.py
index bc37f6a..cbb27b1 100644
--- a/backend/src/agent_service/tools/mcp_manager.py
+++ b/backend/src/agent_service/tools/mcp_manager.py
@@ -193,7 +193,10 @@ class MCPManager:
         return tools
 
     def _build_kb_tool(self) -> StructuredTool:
-        from src.agent_service.features.kb_milvus_store import kb_milvus_store
+        from src.agent_service.core.prompts import prompt_manager
+        from src.agent_service.features.knowledge_base.milvus_store import kb_milvus_store
+
+        kb_description = prompt_manager.get_template("tools", "kb_search")
 
         class KBQueryInput(BaseModel):
             query: str = Field(
@@ -208,7 +211,7 @@ class MCPManager:
             func=None,
             coroutine=mock_fintech_knowledge_base,
             name="mock_fintech_knowledge_base",
-            description="Search the fintech FAQ knowledge base by semantic similarity.",
+            description=kb_description,
             args_schema=KBQueryInput,
         )
 
diff --git a/backend/tests/test_bugfix_validations.py b/backend/tests/test_bugfix_validations.py
index eaac9ec..076a42c 100644
--- a/backend/tests/test_bugfix_validations.py
+++ b/backend/tests/test_bugfix_validations.py
@@ -11,9 +11,9 @@ import pytest
 
 from src.agent_service.api import eval_read
 from src.agent_service.eval_store.pg_store import EvalPgStore
-from src.agent_service.features import knowledge_base_service as kb_service_module
 from src.agent_service.features import runtime_trace_store
-from src.agent_service.features.knowledge_base_service import KnowledgeBaseService
+from src.agent_service.features.knowledge_base import service as kb_service_module
+from src.agent_service.features.knowledge_base.service import KnowledgeBaseService
 from src.agent_service.features.shadow_eval import ShadowEvalCollector
 
 
diff --git a/backend/tests/test_faq_classifier.py b/backend/tests/test_faq_classifier.py
index 3d4e918..8ae8ee9 100644
--- a/backend/tests/test_faq_classifier.py
+++ b/backend/tests/test_faq_classifier.py
@@ -8,7 +8,7 @@ from unittest.mock import AsyncMock, MagicMock
 
 import pytest
 
-from src.agent_service.features import faq_classifier
+from src.agent_service.features.knowledge_base import faq_classifier
 
 CATEGORY_LABELS = ["billing", "account", "data", "technical", "sales"]
 
diff --git a/backend/tests/test_question_category.py b/backend/tests/test_question_category.py
index ab74bad..0f73a8c 100644
--- a/backend/tests/test_question_category.py
+++ b/backend/tests/test_question_category.py
@@ -1,4 +1,4 @@
-from src.agent_service.features.question_category import classify_question_category
+from src.agent_service.features.routing.question_category import classify_question_category
 
 
 def test_question_category_keyword_override_for_theft():
diff --git a/backend/tests/test_router_answerability.py b/backend/tests/test_router_answerability.py
index 19c235a..20d7a74 100644
--- a/backend/tests/test_router_answerability.py
+++ b/backend/tests/test_router_answerability.py
@@ -1,11 +1,11 @@
 import numpy as np
 import pytest
 
-from src.agent_service.features.answerability import (
+from src.agent_service.features.routing.answerability import (
     QueryAnswerabilityClassifier,
     _answerability_decision,
 )
-from src.agent_service.features.nbfc_router import NBFCClassifierService
+from src.agent_service.features.routing.nbfc_router import NBFCClassifierService
 
 
 class _Tool:
```

---

<a id="fe-phase-1"></a>
## Frontend Phase 1: Purge 23 Unused shadcn/ui Components

### DELETED: 23 component files + barrel export cleanup
```diff
diff --git a/Chatbot UI and Admin Console/src/components/ui/accordion.tsx b/Chatbot UI and Admin Console/src/components/ui/accordion.tsx
deleted file mode 100644
index 3e36d71..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/accordion.tsx	
+++ /dev/null
@@ -1,39 +0,0 @@
-import * as React from "react"
-import * as AccordionPrimitive from "@radix-ui/react-accordion"
-import { ChevronDown } from "lucide-react"
-import { cn } from "./utils"
-
-const Accordion = AccordionPrimitive.Root
-
-const AccordionItem = React.forwardRef<
-  React.ElementRef<typeof AccordionPrimitive.Item>,
-  React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Item>
->(({ className, ...props }, ref) => (
-  <AccordionPrimitive.Item ref={ref} className={cn("border-b", className)} {...props} />
-))
-AccordionItem.displayName = "AccordionItem"
-
-const AccordionTrigger = React.forwardRef<
-  React.ElementRef<typeof AccordionPrimitive.Trigger>,
-  React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Trigger>
->(({ className, children, ...props }, ref) => (
-  <AccordionPrimitive.Header className="flex">
-    <AccordionPrimitive.Trigger ref={ref} className={cn("flex flex-1 items-center justify-between py-4 font-medium transition-all hover:underline [&[data-state=open]>svg]:rotate-180", className)} {...props}>
-      {children}
-      <ChevronDown className="h-4 w-4 shrink-0 transition-transform duration-200" />
-    </AccordionPrimitive.Trigger>
-  </AccordionPrimitive.Header>
-))
-AccordionTrigger.displayName = AccordionPrimitive.Trigger.displayName
-
-const AccordionContent = React.forwardRef<
-  React.ElementRef<typeof AccordionPrimitive.Content>,
-  React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Content>
->(({ className, children, ...props }, ref) => (
-  <AccordionPrimitive.Content ref={ref} className="overflow-hidden text-sm transition-all data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down" {...props}>
-    <div className={cn("pb-4 pt-0", className)}>{children}</div>
-  </AccordionPrimitive.Content>
-))
-AccordionContent.displayName = AccordionPrimitive.Content.displayName
-
-export { Accordion, AccordionItem, AccordionTrigger, AccordionContent }
diff --git a/Chatbot UI and Admin Console/src/components/ui/aspect-ratio.tsx b/Chatbot UI and Admin Console/src/components/ui/aspect-ratio.tsx
deleted file mode 100644
index 251434b..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/aspect-ratio.tsx	
+++ /dev/null
@@ -1,3 +0,0 @@
-import * as AspectRatioPrimitive from "@radix-ui/react-aspect-ratio"
-const AspectRatio = AspectRatioPrimitive.Root
-export { AspectRatio }
diff --git a/Chatbot UI and Admin Console/src/components/ui/avatar.tsx b/Chatbot UI and Admin Console/src/components/ui/avatar.tsx
deleted file mode 100644
index dcc1b74..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/avatar.tsx	
+++ /dev/null
@@ -1,29 +0,0 @@
-import * as React from "react"
-import * as AvatarPrimitive from "@radix-ui/react-avatar"
-import { cn } from "./utils"
-
-const Avatar = React.forwardRef<
-  React.ElementRef<typeof AvatarPrimitive.Root>,
-  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Root>
->(({ className, ...props }, ref) => (
-  <AvatarPrimitive.Root ref={ref} className={cn("relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full", className)} {...props} />
-))
-Avatar.displayName = AvatarPrimitive.Root.displayName
-
-const AvatarImage = React.forwardRef<
-  React.ElementRef<typeof AvatarPrimitive.Image>,
-  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Image>
->(({ className, ...props }, ref) => (
-  <AvatarPrimitive.Image ref={ref} className={cn("aspect-square h-full w-full", className)} {...props} />
-))
-AvatarImage.displayName = AvatarPrimitive.Image.displayName
-
-const AvatarFallback = React.forwardRef<
-  React.ElementRef<typeof AvatarPrimitive.Fallback>,
-  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Fallback>
->(({ className, ...props }, ref) => (
-  <AvatarPrimitive.Fallback ref={ref} className={cn("flex h-full w-full items-center justify-center rounded-full bg-muted", className)} {...props} />
-))
-AvatarFallback.displayName = AvatarPrimitive.Fallback.displayName
-
-export { Avatar, AvatarImage, AvatarFallback }
diff --git a/Chatbot UI and Admin Console/src/components/ui/badge.tsx b/Chatbot UI and Admin Console/src/components/ui/badge.tsx
deleted file mode 100644
index f263b60..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/badge.tsx	
+++ /dev/null
@@ -1,32 +0,0 @@
-import * as React from "react"
-import { cva, type VariantProps } from "class-variance-authority"
-import { cn } from "./utils"
-
-const badgeVariants = cva(
-  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
-  {
-    variants: {
-      variant: {
-        default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
-        secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
-        destructive: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
-        outline: "text-foreground",
-      },
-    },
-    defaultVariants: {
-      variant: "default",
-    },
-  }
-)
-
-export interface BadgeProps
-  extends React.HTMLAttributes<HTMLDivElement>,
-    VariantProps<typeof badgeVariants> {}
-
-function Badge({ className, variant, ...props }: BadgeProps) {
-  return (
-    <div className={cn(badgeVariants({ variant }), className)} {...props} />
-  )
-}
-
-export { Badge, badgeVariants }
diff --git a/Chatbot UI and Admin Console/src/components/ui/breadcrumb.tsx b/Chatbot UI and Admin Console/src/components/ui/breadcrumb.tsx
deleted file mode 100644
index 57c40e8..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/breadcrumb.tsx	
+++ /dev/null
@@ -1,19 +0,0 @@
-import * as React from "react"
-import { Slot } from "@radix-ui/react-slot"
-import { ChevronRight, MoreHorizontal } from "lucide-react"
-import { cn } from "./utils"
-const Breadcrumb = React.forwardRef<HTMLElement, React.ComponentPropsWithoutRef<"nav"> & { separator?: React.ReactNode }>(({ ...props }, ref) => <nav ref={ref} aria-label="breadcrumb" {...props} />)
-Breadcrumb.displayName = "Breadcrumb"
-const BreadcrumbList = React.forwardRef<HTMLOListElement, React.ComponentPropsWithoutRef<"ol">>(({ className, ...props }, ref) => (<ol ref={ref} className={cn("flex flex-wrap items-center gap-1.5 break-words text-sm text-muted-foreground sm:gap-2.5", className)} {...props} />))
-BreadcrumbList.displayName = "BreadcrumbList"
-const BreadcrumbItem = React.forwardRef<HTMLLIElement, React.ComponentPropsWithoutRef<"li">>(({ className, ...props }, ref) => (<li ref={ref} className={cn("inline-flex items-center gap-1.5", className)} {...props} />))
-BreadcrumbItem.displayName = "BreadcrumbItem"
-const BreadcrumbLink = React.forwardRef<HTMLAnchorElement, React.ComponentPropsWithoutRef<"a"> & { asChild?: boolean }>(({ asChild, className, ...props }, ref) => { const Comp = asChild ? Slot : "a"; return (<Comp ref={ref} className={cn("transition-colors hover:text-foreground", className)} {...props} />) })
-BreadcrumbLink.displayName = "BreadcrumbLink"
-const BreadcrumbPage = React.forwardRef<HTMLSpanElement, React.ComponentPropsWithoutRef<"span">>(({ className, ...props }, ref) => (<span ref={ref} role="link" aria-disabled="true" aria-current="page" className={cn("font-normal text-foreground", className)} {...props} />))
-BreadcrumbPage.displayName = "BreadcrumbPage"
-const BreadcrumbSeparator = ({ children, className, ...props }: React.ComponentProps<"li">) => (<li role="presentation" aria-hidden="true" className={cn("[&>svg]:h-3.5 [&>svg]:w-3.5", className)} {...props}>{children ?? <ChevronRight />}</li>)
-BreadcrumbSeparator.displayName = "BreadcrumbSeparator"
-const BreadcrumbEllipsis = ({ className, ...props }: React.ComponentProps<"span">) => (<span role="presentation" aria-hidden="true" className={cn("flex h-9 w-9 items-center justify-center", className)} {...props}><MoreHorizontal className="h-4 w-4" /><span className="sr-only">More</span></span>)
-BreadcrumbEllipsis.displayName = "BreadcrumbEllipsis"
-export { Breadcrumb, BreadcrumbList, BreadcrumbItem, BreadcrumbLink, BreadcrumbPage, BreadcrumbSeparator, BreadcrumbEllipsis }
diff --git a/Chatbot UI and Admin Console/src/components/ui/calendar.tsx b/Chatbot UI and Admin Console/src/components/ui/calendar.tsx
deleted file mode 100644
index 9b17d96..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/calendar.tsx	
+++ /dev/null
@@ -1,63 +0,0 @@
-import * as React from 'react'
-import { ChevronLeft, ChevronRight } from 'lucide-react'
-import { DayPicker, type DayPickerProps } from 'react-day-picker'
-import { cn } from './utils'
-import { buttonVariants } from './button'
-
-export type CalendarProps = DayPickerProps
-
-function Calendar({ className, classNames, showOutsideDays = true, ...props }: CalendarProps) {
-  return (
-    <DayPicker
-      showOutsideDays={showOutsideDays}
-      className={cn('p-3', className)}
-      classNames={{
-        months: 'flex flex-col sm:flex-row gap-2',
-        month: 'flex flex-col gap-4',
-        month_caption: 'flex justify-center pt-1 relative items-center w-full',
-        caption_label: 'text-sm font-medium',
-        nav: 'flex items-center gap-1',
-        button_previous: cn(
-          buttonVariants({ variant: 'outline' }),
-          'absolute left-1 top-0 h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100',
-        ),
-        button_next: cn(
-          buttonVariants({ variant: 'outline' }),
-          'absolute right-1 top-0 h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100',
-        ),
-        month_grid: 'w-full border-collapse space-x-1',
-        weekdays: 'flex',
-        weekday: 'text-muted-foreground rounded-md w-8 font-normal text-[0.8rem]',
-        week: 'flex w-full mt-2',
-        day: 'relative p-0 text-center text-sm focus-within:relative focus-within:z-20 [&:has([aria-selected])]:bg-accent [&:has([aria-selected].day-outside)]:bg-accent/50 [&:has([aria-selected].day-range-end)]:rounded-r-md first:[&:has([aria-selected])]:rounded-l-md last:[&:has([aria-selected])]:rounded-r-md',
-        day_button: cn(
-          buttonVariants({ variant: 'ghost' }),
-          'h-8 w-8 p-0 font-normal aria-selected:opacity-100',
-        ),
-        range_start: 'day-range-start',
-        range_end: 'day-range-end',
-        selected:
-          'bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground',
-        today: 'bg-accent text-accent-foreground',
-        outside:
-          'day-outside text-muted-foreground opacity-50 aria-selected:bg-accent/50 aria-selected:text-muted-foreground aria-selected:opacity-30',
-        disabled: 'text-muted-foreground opacity-50',
-        range_middle: 'aria-selected:bg-accent aria-selected:text-accent-foreground',
-        hidden: 'invisible',
-        ...classNames,
-      }}
-      components={{
-        Chevron: ({ orientation }) =>
-          orientation === 'left' ? (
-            <ChevronLeft className="h-4 w-4" />
-          ) : (
-            <ChevronRight className="h-4 w-4" />
-          ),
-      }}
-      {...props}
-    />
-  )
-}
-
-Calendar.displayName = 'Calendar'
-export { Calendar }
diff --git a/Chatbot UI and Admin Console/src/components/ui/carousel.tsx b/Chatbot UI and Admin Console/src/components/ui/carousel.tsx
deleted file mode 100644
index 428f888..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/carousel.tsx	
+++ /dev/null
@@ -1,31 +0,0 @@
-import * as React from "react"
-import useEmblaCarousel, { type UseEmblaCarouselType } from "embla-carousel-react"
-import { ArrowLeft, ArrowRight } from "lucide-react"
-import { cn } from "./utils"
-import { Button } from "./button"
-type CarouselApi = UseEmblaCarouselType[1]
-type UseCarouselParameters = Parameters<typeof useEmblaCarousel>
-type CarouselOptions = UseCarouselParameters[0]
-type CarouselPlugin = UseCarouselParameters[1]
-type CarouselProps = { opts?: CarouselOptions; plugins?: CarouselPlugin; orientation?: "horizontal" | "vertical"; setApi?: (api: CarouselApi) => void }
-type CarouselContextProps = { carouselRef: ReturnType<typeof useEmblaCarousel>[0]; api: ReturnType<typeof useEmblaCarousel>[1]; scrollPrev: () => void; scrollNext: () => void; canScrollPrev: boolean; canScrollNext: boolean } & CarouselProps
-const CarouselContext = React.createContext<CarouselContextProps | null>(null)
-function useCarousel() { const ctx = React.useContext(CarouselContext); if (!ctx) throw new Error("useCarousel must be used within <Carousel />"); return ctx }
-const Carousel = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & CarouselProps>(({ orientation = "horizontal", opts, setApi, plugins, className, children, ...props }, ref) => {
-  const [carouselRef, api] = useEmblaCarousel({ ...opts, axis: orientation === "horizontal" ? "x" : "y" }, plugins)
-  const [canScrollPrev, setCanScrollPrev] = React.useState(false)
-  const [canScrollNext, setCanScrollNext] = React.useState(false)
-  const onSelect = React.useCallback((api: CarouselApi) => { if (!api) return; setCanScrollPrev(api.canScrollPrev()); setCanScrollNext(api.canScrollNext()) }, [])
-  React.useEffect(() => { if (!api) return; setApi?.(api); onSelect(api); api.on("reInit", onSelect); api.on("select", onSelect); return () => { api?.off("select", onSelect) } }, [api, setApi, onSelect])
-  return (<CarouselContext.Provider value={{ carouselRef, api, opts, orientation, scrollPrev: () => api?.scrollPrev(), scrollNext: () => api?.scrollNext(), canScrollPrev, canScrollNext }}><div ref={ref} onKeyDownCapture={(e) => { if (e.key === "ArrowLeft") api?.scrollPrev(); if (e.key === "ArrowRight") api?.scrollNext() }} className={cn("relative", className)} role="region" aria-roledescription="carousel" {...props}>{children}</div></CarouselContext.Provider>)
-})
-Carousel.displayName = "Carousel"
-const CarouselContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => { const { carouselRef, orientation } = useCarousel(); return (<div ref={carouselRef} className="overflow-hidden"><div ref={ref} className={cn("flex", orientation === "horizontal" ? "-ml-4" : "-mt-4 flex-col", className)} {...props} /></div>) })
-CarouselContent.displayName = "CarouselContent"
-const CarouselItem = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => { const { orientation } = useCarousel(); return (<div ref={ref} role="group" aria-roledescription="slide" className={cn("min-w-0 shrink-0 grow-0 basis-full", orientation === "horizontal" ? "pl-4" : "pt-4", className)} {...props} />) })
-CarouselItem.displayName = "CarouselItem"
-const CarouselPrevious = React.forwardRef<HTMLButtonElement, React.ComponentProps<typeof Button>>(({ className, variant = "outline", size = "icon", ...props }, ref) => { const { orientation, scrollPrev, canScrollPrev } = useCarousel(); return (<Button ref={ref} variant={variant} size={size} className={cn("absolute h-8 w-8 rounded-full", orientation === "horizontal" ? "-left-12 top-1/2 -translate-y-1/2" : "-top-12 left-1/2 -translate-x-1/2 rotate-90", className)} disabled={!canScrollPrev} onClick={scrollPrev} {...props}><ArrowLeft className="h-4 w-4" /><span className="sr-only">Previous slide</span></Button>) })
-CarouselPrevious.displayName = "CarouselPrevious"
-const CarouselNext = React.forwardRef<HTMLButtonElement, React.ComponentProps<typeof Button>>(({ className, variant = "outline", size = "icon", ...props }, ref) => { const { orientation, scrollNext, canScrollNext } = useCarousel(); return (<Button ref={ref} variant={variant} size={size} className={cn("absolute h-8 w-8 rounded-full", orientation === "horizontal" ? "-right-12 top-1/2 -translate-y-1/2" : "-bottom-12 left-1/2 -translate-x-1/2 rotate-90", className)} disabled={!canScrollNext} onClick={scrollNext} {...props}><ArrowRight className="h-4 w-4" /><span className="sr-only">Next slide</span></Button>) })
-CarouselNext.displayName = "CarouselNext"
-export { type CarouselApi, Carousel, CarouselContent, CarouselItem, CarouselPrevious, CarouselNext }
diff --git a/Chatbot UI and Admin Console/src/components/ui/chart.tsx b/Chatbot UI and Admin Console/src/components/ui/chart.tsx
deleted file mode 100644
index b996f2b..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/chart.tsx	
+++ /dev/null
@@ -1,11 +0,0 @@
-import { ResponsiveContainer } from "recharts"
-import { cn } from "./utils"
-interface ChartContainerProps extends React.HTMLAttributes<HTMLDivElement> { config?: Record<string, { label?: string; color?: string }>; children: React.ReactElement }
-function ChartContainer({ className, children, config, ...props }: ChartContainerProps) {
-  return (
-    <div className={cn("flex aspect-video justify-center text-xs", className)} style={config ? Object.fromEntries(Object.entries(config).map(([k, v]) => [`--color-${k}`, v.color ?? "hsl(var(--chart-1))"])) : undefined} {...props}>
-      <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
-    </div>
-  )
-}
-export { ChartContainer }
diff --git a/Chatbot UI and Admin Console/src/components/ui/checkbox.tsx b/Chatbot UI and Admin Console/src/components/ui/checkbox.tsx
deleted file mode 100644
index 9e48e09..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/checkbox.tsx	
+++ /dev/null
@@ -1,18 +0,0 @@
-import * as React from "react"
-import * as CheckboxPrimitive from "@radix-ui/react-checkbox"
-import { Check } from "lucide-react"
-import { cn } from "./utils"
-
-const Checkbox = React.forwardRef<
-  React.ElementRef<typeof CheckboxPrimitive.Root>,
-  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
->(({ className, ...props }, ref) => (
-  <CheckboxPrimitive.Root ref={ref} className={cn("peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground", className)} {...props}>
-    <CheckboxPrimitive.Indicator className={cn("flex items-center justify-center text-current")}>
-      <Check className="h-4 w-4" />
-    </CheckboxPrimitive.Indicator>
-  </CheckboxPrimitive.Root>
-))
-Checkbox.displayName = CheckboxPrimitive.Root.displayName
-
-export { Checkbox }
diff --git a/Chatbot UI and Admin Console/src/components/ui/context-menu.tsx b/Chatbot UI and Admin Console/src/components/ui/context-menu.tsx
deleted file mode 100644
index 50dffa8..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/context-menu.tsx	
+++ /dev/null
@@ -1,13 +0,0 @@
-import * as React from "react"
-import * as ContextMenuPrimitive from "@radix-ui/react-context-menu"
-import { cn } from "./utils"
-export const ContextMenu = ContextMenuPrimitive.Root
-export const ContextMenuTrigger = ContextMenuPrimitive.Trigger
-export const ContextMenuContent = React.forwardRef<React.ElementRef<typeof ContextMenuPrimitive.Content>, React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Content>>(({ className, ...props }, ref) => (<ContextMenuPrimitive.Portal><ContextMenuPrimitive.Content ref={ref} className={cn("z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md", className)} {...props} /></ContextMenuPrimitive.Portal>))
-ContextMenuContent.displayName = ContextMenuPrimitive.Content.displayName
-export const ContextMenuItem = React.forwardRef<React.ElementRef<typeof ContextMenuPrimitive.Item>, React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Item>>(({ className, ...props }, ref) => (<ContextMenuPrimitive.Item ref={ref} className={cn("relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-accent data-[disabled]:opacity-50", className)} {...props} />))
-ContextMenuItem.displayName = ContextMenuPrimitive.Item.displayName
-export const ContextMenuSeparator = React.forwardRef<React.ElementRef<typeof ContextMenuPrimitive.Separator>, React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Separator>>(({ className, ...props }, ref) => (<ContextMenuPrimitive.Separator ref={ref} className={cn("-mx-1 my-1 h-px bg-border", className)} {...props} />))
-ContextMenuSeparator.displayName = ContextMenuPrimitive.Separator.displayName
-export const ContextMenuLabel = React.forwardRef<React.ElementRef<typeof ContextMenuPrimitive.Label>, React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Label>>(({ className, ...props }, ref) => (<ContextMenuPrimitive.Label ref={ref} className={cn("px-2 py-1.5 text-sm font-semibold", className)} {...props} />))
-ContextMenuLabel.displayName = ContextMenuPrimitive.Label.displayName
diff --git a/Chatbot UI and Admin Console/src/components/ui/drawer.tsx b/Chatbot UI and Admin Console/src/components/ui/drawer.tsx
deleted file mode 100644
index 24f281a..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/drawer.tsx	
+++ /dev/null
@@ -1,21 +0,0 @@
-import * as React from "react"
-import { Drawer as DrawerPrimitive } from "vaul"
-import { cn } from "./utils"
-const Drawer = ({ shouldScaleBackground = true, ...props }: React.ComponentProps<typeof DrawerPrimitive.Root>) => (<DrawerPrimitive.Root shouldScaleBackground={shouldScaleBackground} {...props} />)
-Drawer.displayName = "Drawer"
-const DrawerTrigger = DrawerPrimitive.Trigger
-const DrawerPortal = DrawerPrimitive.Portal
-const DrawerClose = DrawerPrimitive.Close
-const DrawerOverlay = React.forwardRef<React.ElementRef<typeof DrawerPrimitive.Overlay>, React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Overlay>>(({ className, ...props }, ref) => (<DrawerPrimitive.Overlay ref={ref} className={cn("fixed inset-0 z-50 bg-black/80", className)} {...props} />))
-DrawerOverlay.displayName = DrawerPrimitive.Overlay.displayName
-const DrawerContent = React.forwardRef<React.ElementRef<typeof DrawerPrimitive.Content>, React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Content>>(({ className, children, ...props }, ref) => (<DrawerPortal><DrawerOverlay /><DrawerPrimitive.Content ref={ref} className={cn("fixed inset-x-0 bottom-0 z-50 mt-24 flex h-auto flex-col rounded-t-[10px] border bg-background", className)} {...props}><div className="mx-auto mt-4 h-2 w-[100px] rounded-full bg-muted" />{children}</DrawerPrimitive.Content></DrawerPortal>))
-DrawerContent.displayName = "DrawerContent"
-const DrawerHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (<div className={cn("grid gap-1.5 p-4 text-center sm:text-left", className)} {...props} />)
-DrawerHeader.displayName = "DrawerHeader"
-const DrawerFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (<div className={cn("mt-auto flex flex-col gap-2 p-4", className)} {...props} />)
-DrawerFooter.displayName = "DrawerFooter"
-const DrawerTitle = React.forwardRef<React.ElementRef<typeof DrawerPrimitive.Title>, React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Title>>(({ className, ...props }, ref) => (<DrawerPrimitive.Title ref={ref} className={cn("text-lg font-semibold leading-none tracking-tight", className)} {...props} />))
-DrawerTitle.displayName = DrawerPrimitive.Title.displayName
-const DrawerDescription = React.forwardRef<React.ElementRef<typeof DrawerPrimitive.Description>, React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Description>>(({ className, ...props }, ref) => (<DrawerPrimitive.Description ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />))
-DrawerDescription.displayName = DrawerPrimitive.Description.displayName
-export { Drawer, DrawerPortal, DrawerOverlay, DrawerTrigger, DrawerClose, DrawerContent, DrawerHeader, DrawerFooter, DrawerTitle, DrawerDescription }
diff --git a/Chatbot UI and Admin Console/src/components/ui/dropdown-menu.tsx b/Chatbot UI and Admin Console/src/components/ui/dropdown-menu.tsx
deleted file mode 100644
index 62e78f7..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/dropdown-menu.tsx	
+++ /dev/null
@@ -1,97 +0,0 @@
-import * as React from "react"
-import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu"
-import { Check, ChevronRight, Circle } from "lucide-react"
-import { cn } from "./utils"
-
-const DropdownMenu = DropdownMenuPrimitive.Root
-const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger
-const DropdownMenuGroup = DropdownMenuPrimitive.Group
-const DropdownMenuPortal = DropdownMenuPrimitive.Portal
-const DropdownMenuSub = DropdownMenuPrimitive.Sub
-const DropdownMenuRadioGroup = DropdownMenuPrimitive.RadioGroup
-
-const DropdownMenuSubTrigger = React.forwardRef<
-  React.ElementRef<typeof DropdownMenuPrimitive.SubTrigger>,
-  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.SubTrigger> & { inset?: boolean }
->(({ className, inset, children, ...props }, ref) => (
-  <DropdownMenuPrimitive.SubTrigger ref={ref} className={cn("flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-accent data-[state=open]:bg-accent", inset && "pl-8", className)} {...props}>
-    {children}
-    <ChevronRight className="ml-auto h-4 w-4" />
-  </DropdownMenuPrimitive.SubTrigger>
-))
-DropdownMenuSubTrigger.displayName = DropdownMenuPrimitive.SubTrigger.displayName
-
-const DropdownMenuSubContent = React.forwardRef<
-  React.ElementRef<typeof DropdownMenuPrimitive.SubContent>,
-  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.SubContent>
->(({ className, ...props }, ref) => (
-  <DropdownMenuPrimitive.SubContent ref={ref} className={cn("z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2", className)} {...props} />
-))
-DropdownMenuSubContent.displayName = DropdownMenuPrimitive.SubContent.displayName
-
-const DropdownMenuContent = React.forwardRef<
-  React.ElementRef<typeof DropdownMenuPrimitive.Content>,
-  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
->(({ className, sideOffset = 4, ...props }, ref) => (
-  <DropdownMenuPrimitive.Portal>
-    <DropdownMenuPrimitive.Content ref={ref} sideOffset={sideOffset} className={cn("z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2", className)} {...props} />
-  </DropdownMenuPrimitive.Portal>
-))
-DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName
-
-const DropdownMenuItem = React.forwardRef<
-  React.ElementRef<typeof DropdownMenuPrimitive.Item>,
-  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> & { inset?: boolean }
->(({ className, inset, ...props }, ref) => (
-  <DropdownMenuPrimitive.Item ref={ref} className={cn("relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50", inset && "pl-8", className)} {...props} />
-))
-DropdownMenuItem.displayName = DropdownMenuPrimitive.Item.displayName
-
-const DropdownMenuCheckboxItem = React.forwardRef<
-  React.ElementRef<typeof DropdownMenuPrimitive.CheckboxItem>,
-  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.CheckboxItem>
->(({ className, children, checked, ...props }, ref) => (
-  <DropdownMenuPrimitive.CheckboxItem ref={ref} className={cn("relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50", className)} checked={checked} {...props}>
-    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
-      <DropdownMenuPrimitive.ItemIndicator><Check className="h-4 w-4" /></DropdownMenuPrimitive.ItemIndicator>
-    </span>
-    {children}
-  </DropdownMenuPrimitive.CheckboxItem>
-))
-DropdownMenuCheckboxItem.displayName = DropdownMenuPrimitive.CheckboxItem.displayName
-
-const DropdownMenuRadioItem = React.forwardRef<
-  React.ElementRef<typeof DropdownMenuPrimitive.RadioItem>,
-  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.RadioItem>
->(({ className, children, ...props }, ref) => (
-  <DropdownMenuPrimitive.RadioItem ref={ref} className={cn("relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50", className)} {...props}>
-    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
-      <DropdownMenuPrimitive.ItemIndicator><Circle className="h-2 w-2 fill-current" /></DropdownMenuPrimitive.ItemIndicator>
-    </span>
-    {children}
-  </DropdownMenuPrimitive.RadioItem>
-))
-DropdownMenuRadioItem.displayName = DropdownMenuPrimitive.RadioItem.displayName
-
-const DropdownMenuLabel = React.forwardRef<
-  React.ElementRef<typeof DropdownMenuPrimitive.Label>,
-  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Label> & { inset?: boolean }
->(({ className, inset, ...props }, ref) => (
-  <DropdownMenuPrimitive.Label ref={ref} className={cn("px-2 py-1.5 text-sm font-semibold", inset && "pl-8", className)} {...props} />
-))
-DropdownMenuLabel.displayName = DropdownMenuPrimitive.Label.displayName
-
-const DropdownMenuSeparator = React.forwardRef<
-  React.ElementRef<typeof DropdownMenuPrimitive.Separator>,
-  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>
->(({ className, ...props }, ref) => (
-  <DropdownMenuPrimitive.Separator ref={ref} className={cn("-mx-1 my-1 h-px bg-muted", className)} {...props} />
-))
-DropdownMenuSeparator.displayName = DropdownMenuPrimitive.Separator.displayName
-
-const DropdownMenuShortcut = ({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) => (
-  <span className={cn("ml-auto text-xs tracking-widest opacity-60", className)} {...props} />
-)
-DropdownMenuShortcut.displayName = "DropdownMenuShortcut"
-
-export { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuCheckboxItem, DropdownMenuRadioItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuShortcut, DropdownMenuGroup, DropdownMenuPortal, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger, DropdownMenuRadioGroup }
diff --git a/Chatbot UI and Admin Console/src/components/ui/form.tsx b/Chatbot UI and Admin Console/src/components/ui/form.tsx
deleted file mode 100644
index 6b5bf0b..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/form.tsx	
+++ /dev/null
@@ -1,60 +0,0 @@
-import * as React from "react"
-import * as LabelPrimitive from "@radix-ui/react-label"
-import { Slot } from "@radix-ui/react-slot"
-import { Controller, ControllerProps, FieldPath, FieldValues, FormProvider, useFormContext } from "react-hook-form"
-import { cn } from "./utils"
-import { Label } from "./label"
-
-const Form = FormProvider
-
-type FormFieldContextValue<TFieldValues extends FieldValues = FieldValues, TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>> = { name: TName }
-const FormFieldContext = React.createContext<FormFieldContextValue>({} as FormFieldContextValue)
-
-const FormField = <TFieldValues extends FieldValues = FieldValues, TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>>({ ...props }: ControllerProps<TFieldValues, TName>) => (<FormFieldContext.Provider value={{ name: props.name }}><Controller {...props} /></FormFieldContext.Provider>)
-
-const useFormField = () => {
-  const fieldContext = React.useContext(FormFieldContext)
-  const itemContext = React.useContext(FormItemContext)
-  const { getFieldState, formState } = useFormContext()
-  const fieldState = getFieldState(fieldContext.name, formState)
-  if (!fieldContext) throw new Error("useFormField should be used within <FormField>")
-  const { id } = itemContext
-  return { id, name: fieldContext.name, formItemId: `${id}-form-item`, formDescriptionId: `${id}-form-item-description`, formMessageId: `${id}-form-item-message`, ...fieldState }
-}
-
-type FormItemContextValue = { id: string }
-const FormItemContext = React.createContext<FormItemContextValue>({} as FormItemContextValue)
-
-const FormItem = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => {
-  const id = React.useId()
-  return (<FormItemContext.Provider value={{ id }}><div ref={ref} className={cn("space-y-2", className)} {...props} /></FormItemContext.Provider>)
-})
-FormItem.displayName = "FormItem"
-
-const FormLabel = React.forwardRef<React.ElementRef<typeof LabelPrimitive.Root>, React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>>(({ className, ...props }, ref) => {
-  const { error, formItemId } = useFormField()
-  return (<Label ref={ref} className={cn(error && "text-destructive", className)} htmlFor={formItemId} {...props} />)
-})
-FormLabel.displayName = "FormLabel"
-
-const FormControl = React.forwardRef<React.ElementRef<typeof Slot>, React.ComponentPropsWithoutRef<typeof Slot>>(({ ...props }, ref) => {
-  const { error, formItemId, formDescriptionId, formMessageId } = useFormField()
-  return (<Slot ref={ref} id={formItemId} aria-describedby={!error ? formDescriptionId : `${formDescriptionId} ${formMessageId}`} aria-invalid={!!error} {...props} />)
-})
-FormControl.displayName = "FormControl"
-
-const FormDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(({ className, ...props }, ref) => {
-  const { formDescriptionId } = useFormField()
-  return (<p ref={ref} id={formDescriptionId} className={cn("text-sm text-muted-foreground", className)} {...props} />)
-})
-FormDescription.displayName = "FormDescription"
-
-const FormMessage = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(({ className, children, ...props }, ref) => {
-  const { error, formMessageId } = useFormField()
-  const body = error ? String(error?.message) : children
-  if (!body) return null
-  return (<p ref={ref} id={formMessageId} className={cn("text-sm font-medium text-destructive", className)} {...props}>{body}</p>)
-})
-FormMessage.displayName = "FormMessage"
-
-export { useFormField, Form, FormItem, FormLabel, FormControl, FormDescription, FormMessage, FormField }
diff --git a/Chatbot UI and Admin Console/src/components/ui/index.ts b/Chatbot UI and Admin Console/src/components/ui/index.ts
index 1ac9678..b6bd5cd 100644
--- a/Chatbot UI and Admin Console/src/components/ui/index.ts	
+++ b/Chatbot UI and Admin Console/src/components/ui/index.ts	
@@ -1,51 +1,28 @@
-export * from './accordion'
 export * from './alert'
 export * from './alert-dialog'
-export * from './aspect-ratio'
-export * from './avatar'
-export * from './badge'
-export * from './breadcrumb'
 export * from './button'
-export * from './calendar'
-export * from './collapsible-panel'
 export * from './card'
-export * from './carousel'
-export * from './chart'
-export * from './checkbox'
 export * from './collapsible'
+export * from './collapsible-panel'
 export * from './command'
-export * from './context-menu'
 export * from './dialog'
-export * from './drawer'
-export * from './dropdown-menu'
-export * from './form'
 export * from './hover-card'
 export * from './input'
 export * from './input-otp'
 export * from './label'
-export * from './menubar'
 export * from './mobile-header'
-export * from './navigation-menu'
-export * from './pagination'
 export * from './popover'
 export * from './progress'
 export * from './radio-group'
-export * from './resizable'
 export * from './responsive-grid'
 export * from './responsive-table'
 export * from './scroll-area'
 export * from './select'
-export * from './separator'
 export * from './sheet'
 export * from './skeleton'
 export * from './slider'
 export * from './sonner'
 export * from './split-pane'
-export * from './switch'
-export * from './table'
 export * from './tabs'
 export * from './textarea'
-export * from './toggle'
-export * from './toggle-group'
-export * from './tooltip'
 export { cn } from './utils'
diff --git a/Chatbot UI and Admin Console/src/components/ui/menubar.tsx b/Chatbot UI and Admin Console/src/components/ui/menubar.tsx
deleted file mode 100644
index 610d2d9..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/menubar.tsx	
+++ /dev/null
@@ -1,19 +0,0 @@
-import * as React from "react"
-import * as MenubarPrimitive from "@radix-ui/react-menubar"
-import { cn } from "./utils"
-export const MenubarMenu = MenubarPrimitive.Menu
-export const MenubarGroup = MenubarPrimitive.Group
-export const MenubarPortal = MenubarPrimitive.Portal
-export const MenubarSub = MenubarPrimitive.Sub
-export const MenubarRadioGroup = MenubarPrimitive.RadioGroup
-export const Menubar = React.forwardRef<React.ElementRef<typeof MenubarPrimitive.Root>, React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Root>>(({ className, ...props }, ref) => (<MenubarPrimitive.Root ref={ref} className={cn("flex h-10 items-center space-x-1 rounded-md border bg-background p-1", className)} {...props} />))
-Menubar.displayName = MenubarPrimitive.Root.displayName
-export const MenubarTrigger = React.forwardRef<React.ElementRef<typeof MenubarPrimitive.Trigger>, React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Trigger>>(({ className, ...props }, ref) => (<MenubarPrimitive.Trigger ref={ref} className={cn("flex cursor-default select-none items-center rounded-sm px-3 py-1.5 text-sm font-medium outline-none focus:bg-accent focus:text-accent-foreground data-[state=open]:bg-accent data-[state=open]:text-accent-foreground", className)} {...props} />))
-MenubarTrigger.displayName = MenubarPrimitive.Trigger.displayName
-export const MenubarContent = React.forwardRef<React.ElementRef<typeof MenubarPrimitive.Content>, React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Content>>(({ className, align = "start", alignOffset = -4, sideOffset = 8, ...props }, ref) => (<MenubarPrimitive.Portal><MenubarPrimitive.Content ref={ref} align={align} alignOffset={alignOffset} sideOffset={sideOffset} className={cn("z-50 min-w-[12rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md", className)} {...props} /></MenubarPrimitive.Portal>))
-MenubarContent.displayName = MenubarPrimitive.Content.displayName
-export const MenubarItem = React.forwardRef<React.ElementRef<typeof MenubarPrimitive.Item>, React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Item>>(({ className, ...props }, ref) => (<MenubarPrimitive.Item ref={ref} className={cn("relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-accent", className)} {...props} />))
-MenubarItem.displayName = MenubarPrimitive.Item.displayName
-export const MenubarSeparator = React.forwardRef<React.ElementRef<typeof MenubarPrimitive.Separator>, React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Separator>>(({ className, ...props }, ref) => (<MenubarPrimitive.Separator ref={ref} className={cn("-mx-1 my-1 h-px bg-muted", className)} {...props} />))
-MenubarSeparator.displayName = MenubarPrimitive.Separator.displayName
-export const MenubarShortcut = ({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) => (<span className={cn("ml-auto text-xs tracking-widest text-muted-foreground", className)} {...props} />)
diff --git a/Chatbot UI and Admin Console/src/components/ui/navigation-menu.tsx b/Chatbot UI and Admin Console/src/components/ui/navigation-menu.tsx
deleted file mode 100644
index d49f5f1..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/navigation-menu.tsx	
+++ /dev/null
@@ -1,18 +0,0 @@
-import * as React from "react"
-import * as NavigationMenuPrimitive from "@radix-ui/react-navigation-menu"
-import { cn } from "./utils"
-const NavigationMenu = React.forwardRef<React.ElementRef<typeof NavigationMenuPrimitive.Root>, React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Root>>(({ className, children, ...props }, ref) => (<NavigationMenuPrimitive.Root ref={ref} className={cn("relative z-10 flex max-w-max flex-1 items-center justify-center", className)} {...props}>{children}</NavigationMenuPrimitive.Root>))
-NavigationMenu.displayName = NavigationMenuPrimitive.Root.displayName
-const NavigationMenuList = React.forwardRef<React.ElementRef<typeof NavigationMenuPrimitive.List>, React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.List>>(({ className, ...props }, ref) => (<NavigationMenuPrimitive.List ref={ref} className={cn("group flex flex-1 list-none items-center justify-center space-x-1", className)} {...props} />))
-NavigationMenuList.displayName = NavigationMenuPrimitive.List.displayName
-const NavigationMenuItem = NavigationMenuPrimitive.Item
-const NavigationMenuTrigger = React.forwardRef<React.ElementRef<typeof NavigationMenuPrimitive.Trigger>, React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Trigger>>(({ className, children, ...props }, ref) => (<NavigationMenuPrimitive.Trigger ref={ref} className={cn("group inline-flex h-10 w-max items-center justify-center rounded-md bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground focus:outline-none disabled:pointer-events-none disabled:opacity-50 data-[active]:bg-accent/50 data-[state=open]:bg-accent/50", className)} {...props}>{children}</NavigationMenuPrimitive.Trigger>))
-NavigationMenuTrigger.displayName = NavigationMenuPrimitive.Trigger.displayName
-const NavigationMenuContent = React.forwardRef<React.ElementRef<typeof NavigationMenuPrimitive.Content>, React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Content>>(({ className, ...props }, ref) => (<NavigationMenuPrimitive.Content ref={ref} className={cn("left-0 top-0 w-full data-[motion^=from-]:animate-in data-[motion^=to-]:animate-out data-[motion^=from-]:fade-in data-[motion^=to-]:fade-out data-[motion=from-end]:slide-in-from-right-52 data-[motion=from-start]:slide-in-from-left-52 data-[motion=to-end]:slide-out-to-right-52 data-[motion=to-start]:slide-out-to-left-52 md:absolute md:w-auto", className)} {...props} />))
-NavigationMenuContent.displayName = NavigationMenuPrimitive.Content.displayName
-const NavigationMenuLink = NavigationMenuPrimitive.Link
-const NavigationMenuViewport = React.forwardRef<React.ElementRef<typeof NavigationMenuPrimitive.Viewport>, React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Viewport>>(({ className, ...props }, ref) => (<div className={cn("absolute left-0 top-full flex justify-center")}><NavigationMenuPrimitive.Viewport className={cn("origin-top-center relative mt-1.5 h-[var(--radix-navigation-menu-viewport-height)] w-full overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-90 md:w-[var(--radix-navigation-menu-viewport-width)]", className)} ref={ref} {...props} /></div>))
-NavigationMenuViewport.displayName = NavigationMenuPrimitive.Viewport.displayName
-const NavigationMenuIndicator = React.forwardRef<React.ElementRef<typeof NavigationMenuPrimitive.Indicator>, React.ComponentPropsWithoutRef<typeof NavigationMenuPrimitive.Indicator>>(({ className, ...props }, ref) => (<NavigationMenuPrimitive.Indicator ref={ref} className={cn("top-full z-[1] flex h-1.5 items-end justify-center overflow-hidden data-[state=visible]:animate-in data-[state=hidden]:animate-out data-[state=hidden]:fade-out data-[state=visible]:fade-in", className)} {...props}><div className="relative top-[60%] h-2 w-2 rotate-45 rounded-tl-sm bg-border shadow-md" /></NavigationMenuPrimitive.Indicator>))
-NavigationMenuIndicator.displayName = NavigationMenuPrimitive.Indicator.displayName
-export { NavigationMenu, NavigationMenuList, NavigationMenuItem, NavigationMenuContent, NavigationMenuTrigger, NavigationMenuLink, NavigationMenuViewport, NavigationMenuIndicator }
diff --git a/Chatbot UI and Admin Console/src/components/ui/pagination.tsx b/Chatbot UI and Admin Console/src/components/ui/pagination.tsx
deleted file mode 100644
index dd2f32d..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/pagination.tsx	
+++ /dev/null
@@ -1,21 +0,0 @@
-import * as React from "react"
-import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react"
-import { cn } from "./utils"
-import { buttonVariants } from "./button"
-import { type ButtonProps } from "./button"
-const Pagination = ({ className, ...props }: React.ComponentProps<"nav">) => (<nav role="navigation" aria-label="pagination" className={cn("mx-auto flex w-full justify-center", className)} {...props} />)
-Pagination.displayName = "Pagination"
-const PaginationContent = React.forwardRef<HTMLUListElement, React.ComponentProps<"ul">>(({ className, ...props }, ref) => (<ul ref={ref} className={cn("flex flex-row items-center gap-1", className)} {...props} />))
-PaginationContent.displayName = "PaginationContent"
-const PaginationItem = React.forwardRef<HTMLLIElement, React.ComponentProps<"li">>(({ className, ...props }, ref) => (<li ref={ref} className={cn("", className)} {...props} />))
-PaginationItem.displayName = "PaginationItem"
-type PaginationLinkProps = { isActive?: boolean } & Pick<ButtonProps, "size"> & React.ComponentProps<"a">
-const PaginationLink = ({ className, isActive, size = "icon", ...props }: PaginationLinkProps) => (<a aria-current={isActive ? "page" : undefined} className={cn(buttonVariants({ variant: isActive ? "outline" : "ghost", size }), className)} {...props} />)
-PaginationLink.displayName = "PaginationLink"
-const PaginationPrevious = ({ className, ...props }: React.ComponentProps<typeof PaginationLink>) => (<PaginationLink aria-label="Go to previous page" size="default" className={cn("gap-1 pl-2.5", className)} {...props}><ChevronLeft className="h-4 w-4" /><span>Previous</span></PaginationLink>)
-PaginationPrevious.displayName = "PaginationPrevious"
-const PaginationNext = ({ className, ...props }: React.ComponentProps<typeof PaginationLink>) => (<PaginationLink aria-label="Go to next page" size="default" className={cn("gap-1 pr-2.5", className)} {...props}><span>Next</span><ChevronRight className="h-4 w-4" /></PaginationLink>)
-PaginationNext.displayName = "PaginationNext"
-const PaginationEllipsis = ({ className, ...props }: React.ComponentProps<"span">) => (<span aria-hidden className={cn("flex h-9 w-9 items-center justify-center", className)} {...props}><MoreHorizontal className="h-4 w-4" /><span className="sr-only">More pages</span></span>)
-PaginationEllipsis.displayName = "PaginationEllipsis"
-export { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious }
diff --git a/Chatbot UI and Admin Console/src/components/ui/resizable.tsx b/Chatbot UI and Admin Console/src/components/ui/resizable.tsx
deleted file mode 100644
index 0054758..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/resizable.tsx	
+++ /dev/null
@@ -1,34 +0,0 @@
-import { GripVertical } from 'lucide-react'
-import { Group, Panel, Separator, type GroupProps, type SeparatorProps } from 'react-resizable-panels'
-import { cn } from './utils'
-
-const ResizablePanelGroup = ({ className, ...props }: GroupProps) => (
-  <Group
-    className={cn('flex h-full w-full data-[panel-group-direction=vertical]:flex-col', className)}
-    {...props}
-  />
-)
-
-const ResizablePanel = Panel
-
-const ResizableHandle = ({
-  withHandle,
-  className,
-  ...props
-}: SeparatorProps & { withHandle?: boolean }) => (
-  <Separator
-    className={cn(
-      'relative flex w-px items-center justify-center bg-border after:absolute after:inset-y-0 after:left-1/2 after:w-1 after:-translate-x-1/2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-1 data-[panel-group-direction=vertical]:h-px data-[panel-group-direction=vertical]:w-full data-[panel-group-direction=vertical]:after:left-0 data-[panel-group-direction=vertical]:after:h-1 data-[panel-group-direction=vertical]:after:w-full data-[panel-group-direction=vertical]:after:-translate-y-1/2 data-[panel-group-direction=vertical]:after:translate-x-0 [&[data-panel-group-direction=vertical]>div]:rotate-90',
-      className,
-    )}
-    {...props}
-  >
-    {withHandle && (
-      <div className="z-10 flex h-4 w-3 items-center justify-center rounded-sm border bg-border">
-        <GripVertical className="h-2.5 w-2.5" />
-      </div>
-    )}
-  </Separator>
-)
-
-export { ResizablePanelGroup, ResizablePanel, ResizableHandle }
diff --git a/Chatbot UI and Admin Console/src/components/ui/separator.tsx b/Chatbot UI and Admin Console/src/components/ui/separator.tsx
deleted file mode 100644
index 6ad9cc1..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/separator.tsx	
+++ /dev/null
@@ -1,25 +0,0 @@
-import * as React from "react"
-import * as SeparatorPrimitive from "@radix-ui/react-separator"
-import { cn } from "./utils"
-
-const Separator = React.forwardRef<
-  React.ElementRef<typeof SeparatorPrimitive.Root>,
-  React.ComponentPropsWithoutRef<typeof SeparatorPrimitive.Root>
->(
-  ({ className, orientation = "horizontal", decorative = true, ...props }, ref) => (
-    <SeparatorPrimitive.Root
-      ref={ref}
-      decorative={decorative}
-      orientation={orientation}
-      className={cn(
-        "shrink-0 bg-border",
-        orientation === "horizontal" ? "h-[1px] w-full" : "h-full w-[1px]",
-        className
-      )}
-      {...props}
-    />
-  )
-)
-Separator.displayName = SeparatorPrimitive.Root.displayName
-
-export { Separator }
diff --git a/Chatbot UI and Admin Console/src/components/ui/switch.tsx b/Chatbot UI and Admin Console/src/components/ui/switch.tsx
deleted file mode 100644
index c66105a..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/switch.tsx	
+++ /dev/null
@@ -1,15 +0,0 @@
-import * as React from "react"
-import * as SwitchPrimitives from "@radix-ui/react-switch"
-import { cn } from "./utils"
-
-const Switch = React.forwardRef<
-  React.ElementRef<typeof SwitchPrimitives.Root>,
-  React.ComponentPropsWithoutRef<typeof SwitchPrimitives.Root>
->(({ className, ...props }, ref) => (
-  <SwitchPrimitives.Root className={cn("peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=unchecked]:bg-input", className)} {...props} ref={ref}>
-    <SwitchPrimitives.Thumb className={cn("pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0")} />
-  </SwitchPrimitives.Root>
-))
-Switch.displayName = SwitchPrimitives.Root.displayName
-
-export { Switch }
diff --git a/Chatbot UI and Admin Console/src/components/ui/table.tsx b/Chatbot UI and Admin Console/src/components/ui/table.tsx
deleted file mode 100644
index 6a8f953..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/table.tsx	
+++ /dev/null
@@ -1,62 +0,0 @@
-import * as React from "react"
-import { cn } from "./utils"
-
-const Table = React.forwardRef<HTMLTableElement, React.HTMLAttributes<HTMLTableElement>>(
-  ({ className, ...props }, ref) => (
-    <div className="relative w-full overflow-auto">
-      <table ref={ref} className={cn("w-full caption-bottom text-sm", className)} {...props} />
-    </div>
-  )
-)
-Table.displayName = "Table"
-
-const TableHeader = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
-  ({ className, ...props }, ref) => (
-    <thead ref={ref} className={cn("[&_tr]:border-b", className)} {...props} />
-  )
-)
-TableHeader.displayName = "TableHeader"
-
-const TableBody = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
-  ({ className, ...props }, ref) => (
-    <tbody ref={ref} className={cn("[&_tr:last-child]:border-0", className)} {...props} />
-  )
-)
-TableBody.displayName = "TableBody"
-
-const TableFooter = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
-  ({ className, ...props }, ref) => (
-    <tfoot ref={ref} className={cn("border-t bg-muted/50 font-medium [&>tr]:last:border-b-0", className)} {...props} />
-  )
-)
-TableFooter.displayName = "TableFooter"
-
-const TableRow = React.forwardRef<HTMLTableRowElement, React.HTMLAttributes<HTMLTableRowElement>>(
-  ({ className, ...props }, ref) => (
-    <tr ref={ref} className={cn("border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted", className)} {...props} />
-  )
-)
-TableRow.displayName = "TableRow"
-
-const TableHead = React.forwardRef<HTMLTableCellElement, React.ThHTMLAttributes<HTMLTableCellElement>>(
-  ({ className, ...props }, ref) => (
-    <th ref={ref} className={cn("h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0", className)} {...props} />
-  )
-)
-TableHead.displayName = "TableHead"
-
-const TableCell = React.forwardRef<HTMLTableCellElement, React.TdHTMLAttributes<HTMLTableCellElement>>(
-  ({ className, ...props }, ref) => (
-    <td ref={ref} className={cn("p-4 align-middle [&:has([role=checkbox])]:pr-0", className)} {...props} />
-  )
-)
-TableCell.displayName = "TableCell"
-
-const TableCaption = React.forwardRef<HTMLTableCaptionElement, React.HTMLAttributes<HTMLTableCaptionElement>>(
-  ({ className, ...props }, ref) => (
-    <caption ref={ref} className={cn("mt-4 text-sm text-muted-foreground", className)} {...props} />
-  )
-)
-TableCaption.displayName = "TableCaption"
-
-export { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption }
diff --git a/Chatbot UI and Admin Console/src/components/ui/toggle-group.tsx b/Chatbot UI and Admin Console/src/components/ui/toggle-group.tsx
deleted file mode 100644
index 71b965d..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/toggle-group.tsx	
+++ /dev/null
@@ -1,11 +0,0 @@
-import * as React from "react"
-import * as ToggleGroupPrimitive from "@radix-ui/react-toggle-group"
-import { type VariantProps } from "class-variance-authority"
-import { cn } from "./utils"
-import { toggleVariants } from "./toggle"
-const ToggleGroupContext = React.createContext<VariantProps<typeof toggleVariants>>({ size: "default", variant: "default" })
-const ToggleGroup = React.forwardRef<React.ElementRef<typeof ToggleGroupPrimitive.Root>, React.ComponentPropsWithoutRef<typeof ToggleGroupPrimitive.Root> & VariantProps<typeof toggleVariants>>(({ className, variant, size, children, ...props }, ref) => (<ToggleGroupPrimitive.Root ref={ref} className={cn("flex items-center justify-center gap-1", className)} {...props}><ToggleGroupContext.Provider value={{ variant, size }}>{children}</ToggleGroupContext.Provider></ToggleGroupPrimitive.Root>))
-ToggleGroup.displayName = ToggleGroupPrimitive.Root.displayName
-const ToggleGroupItem = React.forwardRef<React.ElementRef<typeof ToggleGroupPrimitive.Item>, React.ComponentPropsWithoutRef<typeof ToggleGroupPrimitive.Item> & VariantProps<typeof toggleVariants>>(({ className, children, variant, size, ...props }, ref) => { const context = React.useContext(ToggleGroupContext); return (<ToggleGroupPrimitive.Item ref={ref} className={cn(toggleVariants({ variant: context.variant || variant, size: context.size || size }), className)} {...props}>{children}</ToggleGroupPrimitive.Item>) })
-ToggleGroupItem.displayName = ToggleGroupPrimitive.Item.displayName
-export { ToggleGroup, ToggleGroupItem }
diff --git a/Chatbot UI and Admin Console/src/components/ui/toggle.tsx b/Chatbot UI and Admin Console/src/components/ui/toggle.tsx
deleted file mode 100644
index 8266c6d..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/toggle.tsx	
+++ /dev/null
@@ -1,8 +0,0 @@
-import * as React from "react"
-import * as TogglePrimitive from "@radix-ui/react-toggle"
-import { cva, type VariantProps } from "class-variance-authority"
-import { cn } from "./utils"
-const toggleVariants = cva("inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors hover:bg-muted hover:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=on]:bg-accent data-[state=on]:text-accent-foreground", { variants: { variant: { default: "bg-transparent", outline: "border border-input bg-transparent hover:bg-accent hover:text-accent-foreground" }, size: { default: "h-10 px-3", sm: "h-9 px-2.5", lg: "h-11 px-5" } }, defaultVariants: { variant: "default", size: "default" } })
-const Toggle = React.forwardRef<React.ElementRef<typeof TogglePrimitive.Root>, React.ComponentPropsWithoutRef<typeof TogglePrimitive.Root> & VariantProps<typeof toggleVariants>>(({ className, variant, size, ...props }, ref) => (<TogglePrimitive.Root ref={ref} className={cn(toggleVariants({ variant, size, className }))} {...props} />))
-Toggle.displayName = TogglePrimitive.Root.displayName
-export { Toggle, toggleVariants }
diff --git a/Chatbot UI and Admin Console/src/components/ui/tooltip.tsx b/Chatbot UI and Admin Console/src/components/ui/tooltip.tsx
deleted file mode 100644
index ab8aabb..0000000
--- a/Chatbot UI and Admin Console/src/components/ui/tooltip.tsx	
+++ /dev/null
@@ -1,17 +0,0 @@
-import * as React from "react"
-import * as TooltipPrimitive from "@radix-ui/react-tooltip"
-import { cn } from "./utils"
-
-const TooltipProvider = TooltipPrimitive.Provider
-const Tooltip = TooltipPrimitive.Root
-const TooltipTrigger = TooltipPrimitive.Trigger
-
-const TooltipContent = React.forwardRef<
-  React.ElementRef<typeof TooltipPrimitive.Content>,
-  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
->(({ className, sideOffset = 4, ...props }, ref) => (
-  <TooltipPrimitive.Content ref={ref} sideOffset={sideOffset} className={cn("z-50 overflow-hidden rounded-md border bg-popover px-3 py-1.5 text-sm text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2", className)} {...props} />
-))
-TooltipContent.displayName = TooltipPrimitive.Content.displayName
-
-export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
```

---

<a id="fe-phase-2"></a>
## Frontend Phase 2: KnowledgeBasePage Extraction (1,129 → 621 LOC)

### NEW: 6 extracted component files
```diff
```

### KnowledgeBasePage.tsx — Reduced to orchestrator
```diff
diff --git a/Chatbot UI and Admin Console/src/features/admin/knowledge-base/KnowledgeBasePage.tsx b/Chatbot UI and Admin Console/src/features/admin/knowledge-base/KnowledgeBasePage.tsx
index 96b98c9..4d85890 100644
--- a/Chatbot UI and Admin Console/src/features/admin/knowledge-base/KnowledgeBasePage.tsx	
+++ b/Chatbot UI and Admin Console/src/features/admin/knowledge-base/KnowledgeBasePage.tsx	
@@ -1,10 +1,6 @@
 import { useCallback, useMemo, useRef, useState } from 'react'
 import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
 import {
-  AlertCircle,
-  Check,
-  ChevronDown,
-  ChevronUp,
   Copy,
   Database,
   FileText,
@@ -14,7 +10,6 @@ import {
   Plus,
   Search,
   Sparkles,
-  Tag,
   Trash2,
   Upload,
   X,
@@ -22,7 +17,6 @@ import {
 import { toast } from 'sonner'
 
 import { clearAllFaqs, deleteFaq, ingestFaqBatch, ingestFaqPdf, updateFaq } from '@features/admin/api/admin'
-import { formatDateTime } from '@shared/lib/format'
 import { Alert, AlertDescription } from '@components/ui/alert'
 import { Skeleton } from '@components/ui/skeleton'
 import { MobileHeader } from '@components/ui/mobile-header'
@@ -39,511 +33,9 @@ import {
   faqListQueryOptions,
   faqSemanticSearchQueryOptions,
 } from '@features/admin/query/queryOptions'
-
-// ────────────────────────────────────────────────────────────────────────────
-// Types & Defaults
-// ────────────────────────────────────────────────────────────────────────────
-
-type SemanticMatch = {
-  question: string
-  answer: string
-  score: number
-}
-
-type EntryErrors = {
-  q?: string
-  a?: string
-}
-
-type FaqEntryDraft = {
-  question: string
-  answer: string
-  category: string
-  tags: string
-  errors: EntryErrors
-}
-
-const DEFAULT_CATEGORY = 'Technical'
-
-function getErrorMessage(error: unknown): string {
-  if (error instanceof Error && error.message.trim()) return error.message
-  if (typeof error === 'string' && error.trim()) return error
-  return 'Request failed'
-}
-
-function blankEntry(category = DEFAULT_CATEGORY): FaqEntryDraft {
-  return {
-    question: '',
-    answer: '',
-    category,
-    tags: '',
-    errors: {},
-  }
-}
-
-// ────────────────────────────────────────────────────────────────────────────
-// Sub-components
-// ────────────────────────────────────────────────────────────────────────────
-
-function StatusBadge({
-  vectorStatus,
-  vectorError,
-}: {
-  vectorStatus: KnowledgeBaseFaqRow['vectorStatus']
-  vectorError: KnowledgeBaseFaqRow['vectorError']
-}) {
-  if (vectorStatus === 'synced') {
-    return (
-      <span className="inline-flex items-center gap-1 rounded-full border border-teal-200 bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-700">
-        <span className="h-1.5 w-1.5 rounded-full bg-teal-500" />
-        Vectorized
-      </span>
-    )
-  }
-
-  if (vectorStatus === 'failed') {
-    const label = vectorError ? vectorError.slice(0, 60) : 'Vectorization failed'
-    return (
-      <span
-        className="inline-flex max-w-xs items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700"
-        title={vectorError ?? undefined}
-      >
-        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-rose-500" />
-        <span className="truncate">{label}{vectorError && vectorError.length > 60 ? '…' : ''}</span>
-      </span>
-    )
-  }
-
-  if (vectorStatus === 'syncing') {
-    return (
-      <span className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-700">
-        <Loader2 className="size-3 animate-spin" />
-        Syncing
-      </span>
-    )
-  }
-
-  return (
-    <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
-      <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
-      Pending
-    </span>
-  )
-}
-
-function CategoryBadge({ category }: { category: string }) {
-  const colors: Record<string, string> = {
-    Billing: 'bg-blue-50 text-blue-700 border-blue-200',
-    Account: 'bg-purple-50 text-purple-700 border-purple-200',
-    Data: 'bg-indigo-50 text-indigo-700 border-indigo-200',
-    Technical: 'bg-orange-50 text-orange-700 border-orange-200',
-    Sales: 'bg-green-50 text-green-700 border-green-200',
-  }
-
-  return (
-    <span
-      className={[
-        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs',
-        colors[category] ?? 'bg-gray-50 text-gray-700 border-gray-200',
-      ].join(' ')}
-    >
-      {category}
-    </span>
-  )
-}
-
-function FAQRow({
-  faq,
-  onEdit,
-  onDelete,
-}: {
-  faq: KnowledgeBaseFaqRow
-  onEdit: (row: KnowledgeBaseFaqRow) => void
-  onDelete: (row: KnowledgeBaseFaqRow) => void
-}) {
-  const [expanded, setExpanded] = useState(false)
-  const [menuOpen, setMenuOpen] = useState(false)
-
-  const toggleExpanded = () => setExpanded((prev) => !prev)
-
-  return (
-    <div className="mb-2 rounded-xl border border-gray-100 bg-white shadow-sm transition-shadow duration-200 hover:shadow-md">
-      <div
-        role="button"
-        tabIndex={0}
-        aria-expanded={expanded}
-        onClick={toggleExpanded}
-        onKeyDown={(event) => {
-          if (event.key === 'Enter' || event.key === ' ') {
-            event.preventDefault()
-            toggleExpanded()
-          }
-        }}
-        className="flex cursor-pointer items-start gap-4 px-3 sm:px-5 py-3 sm:py-4"
-      >
-        <button
-          type="button"
-          className="mt-0.5 shrink-0 text-gray-400 transition-colors hover:text-gray-600"
-          aria-label={expanded ? 'Collapse FAQ row' : 'Expand FAQ row'}
-          onClick={(event) => {
-            event.stopPropagation()
-            toggleExpanded()
-          }}
-        >
-          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
-        </button>
-
-        <div className="min-w-0 flex-1">
-          <p className="truncate text-sm font-medium text-gray-800">{faq.question}</p>
-          {!expanded && <p className="mt-0.5 truncate text-xs text-gray-400">{faq.answer}</p>}
-        </div>
-
-        <div
-          className="flex flex-col sm:flex-row shrink-0 items-end sm:items-center gap-1.5 sm:gap-2"
-          onClick={(event) => event.stopPropagation()}
-          onKeyDown={(event) => event.stopPropagation()}
-        >
-          <CategoryBadge category={faq.category} />
-          <StatusBadge vectorStatus={faq.vectorStatus} vectorError={faq.vectorError} />
-          <div className="relative">
-            <button
-              type="button"
-              onClick={() => setMenuOpen((prev) => !prev)}
-              aria-expanded={menuOpen}
-              aria-label="Open row actions"
-              className="rounded-lg p-1.5 text-gray-400 transition-all hover:bg-gray-100 hover:text-gray-700"
-            >
-              <MoreHorizontal size={16} />
-            </button>
-            {menuOpen && (
-              <>
-                <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} aria-hidden />
-                <div className="absolute right-0 top-8 z-20 w-36 overflow-hidden rounded-xl border border-gray-100 bg-white py-1 shadow-xl">
-                  <button
-                    type="button"
-                    onClick={() => {
-                      onEdit(faq)
-                      setMenuOpen(false)
-                    }}
-                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
-                  >
-                    <Pencil size={13} />
-                    Edit
-                  </button>
-                  <button
-                    type="button"
-                    onClick={async () => {
-                      await navigator.clipboard.writeText(`Q: ${faq.question}\nA: ${faq.answer}`)
-                      toast.success('Copied to clipboard')
-                      setMenuOpen(false)
-                    }}
-                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
-                  >
-                    <Copy size={13} />
-                    Copy
-                  </button>
-                  <div className="my-1 border-t border-gray-100" />
-                  <button
-                    type="button"
-                    onClick={() => {
-                      onDelete(faq)
-                      setMenuOpen(false)
-                    }}
-                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 transition-colors hover:bg-red-50"
-                  >
-                    <Trash2 size={13} />
-                    Delete
-                  </button>
-                </div>
-              </>
-            )}
-          </div>
-        </div>
-      </div>
-
-      {expanded && (
-        <div className="border-t border-gray-50 bg-gray-50/50 px-3 sm:px-5 py-3 sm:py-4">
-          <p className="mb-3 text-sm leading-relaxed text-gray-600">{faq.answer}</p>
-          <div className="flex flex-wrap items-center gap-2">
-            {faq.tags.map((tag) => (
-              <span key={tag} className="inline-flex items-center gap-1 rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
-                <Tag size={10} />
-                {tag}
-              </span>
-            ))}
-            <span className="ml-auto text-xs text-gray-400">
-              Added {faq.createdAt ? formatDateTime(faq.createdAt) : '—'}
-            </span>
-          </div>
-        </div>
-      )}
-    </div>
-  )
-}
-
-function EntryForm({
-  entry,
-  index,
-  total,
-  categories,
-  onChange,
-  onRemove,
-}: {
-  entry: FaqEntryDraft
-  index: number
-  total: number
-  categories: string[]
-  onChange: (idx: number, field: keyof FaqEntryDraft, value: string) => void
-  onRemove: (idx: number) => void
-}) {
-  return (
-    <div className="relative space-y-3 rounded-xl border border-gray-200 bg-gray-50/60 p-4">
-      {total > 1 && (
-        <div className="mb-1 flex items-center justify-between">
-          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">FAQ #{index + 1}</span>
-          <button
-            type="button"
-            onClick={() => onRemove(index)}
-            className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500"
-            aria-label="Remove this FAQ entry"
-          >
-            <X size={14} />
-          </button>
-        </div>
-      )}
-
-      <div>
-        <label className="mb-1.5 block text-xs font-medium text-gray-600">
-          Question <span className="text-red-500">*</span>
-        </label>
-        <input
-          value={entry.question}
-          onChange={(event) => onChange(index, 'question', event.target.value)}
-          placeholder="What does your customer need to know?"
-          className={`w-full rounded-lg border px-3 py-2.5 text-sm text-gray-800 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-teal-400 ${entry.errors.q ? 'border-red-300' : 'border-gray-200'} bg-white`}
-        />
-        {entry.errors.q && (
-          <p className="mt-1 flex items-center gap-1 text-xs text-red-500">
-            <AlertCircle size={11} /> {entry.errors.q}
-          </p>
-        )}
-      </div>
-
-      <div>
-        <label className="mb-1.5 block text-xs font-medium text-gray-600">
-          Answer <span className="text-red-500">*</span>
-        </label>
-        <textarea
-          value={entry.answer}
-          onChange={(event) => onChange(index, 'answer', event.target.value)}
-          placeholder="Provide a clear, concise answer."
-          rows={3}
-          className={`w-full resize-none rounded-lg border px-3 py-2.5 text-sm text-gray-800 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-teal-400 ${entry.errors.a ? 'border-red-300' : 'border-gray-200'} bg-white`}
-        />
-        {entry.errors.a && (
-          <p className="mt-1 flex items-center gap-1 text-xs text-red-500">
-            <AlertCircle size={11} /> {entry.errors.a}
-          </p>
-        )}
-      </div>
-
-      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
-        <div>
-          <label className="mb-1.5 block text-xs font-medium text-gray-600">Category</label>
-          <select
-            value={entry.category}
-            onChange={(event) => onChange(index, 'category', event.target.value)}
-            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-800 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-teal-400"
-          >
-            {categories.map((category) => (
-              <option key={category} value={category}>
-                {category}
-              </option>
-            ))}
-          </select>
-        </div>
-        <div>
-          <label className="mb-1.5 block text-xs font-medium text-gray-600">
-            Tags <span className="font-normal text-gray-400">(comma-separated)</span>
-          </label>
-          <input
-            value={entry.tags}
-            onChange={(event) => onChange(index, 'tags', event.target.value)}
-            placeholder="e.g. billing, refund"
-            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm text-gray-800 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-teal-400"
-          />
-        </div>
-      </div>
-    </div>
-  )
-}
-
-function AddEditModal({
-  initial,
-  categories,
-  saving,
-  onSave,
-  onClose,
-}: {
-  initial: KnowledgeBaseFaqRow | null
-  categories: string[]
-  saving: boolean
-  onSave: (entries: Array<{ question: string; answer: string; category: string; tags: string[] }>) => void
-  onClose: () => void
-}) {
-  const isEdit = Boolean(initial)
-
-  const [entries, setEntries] = useState<FaqEntryDraft[]>(() =>
-    initial
-      ? [
-          {
-            question: initial.question,
-            answer: initial.answer,
-            category: initial.category,
-            tags: initial.tags.join(', '),
-            errors: {},
-          },
-        ]
-      : [blankEntry(categories[0] || DEFAULT_CATEGORY)],
-  )
-
-  const handleChange = (idx: number, field: keyof FaqEntryDraft, value: string) => {
-    setEntries((prev) =>
-      prev.map((entry, index) =>
-        index === idx
-          ? {
-              ...entry,
-              [field]: value,
-              errors: {
-                ...entry.errors,
-                ...(field === 'question' ? { q: '' } : {}),
-                ...(field === 'answer' ? { a: '' } : {}),
-              },
-            }
-          : entry,
-      ),
-    )
-  }
-
-  const handleRemove = (idx: number) => {
-    setEntries((prev) => prev.filter((_, index) => index !== idx))
-  }
-
-  const handleAddAnother = () => {
-    setEntries((prev) => [...prev, blankEntry(categories[0] || DEFAULT_CATEGORY)])
-    setTimeout(() => {
-      const el = document.getElementById('modal-scroll-area')
-      if (el) el.scrollTop = el.scrollHeight
-    }, 50)
-  }
-
-  const handleSave = () => {
-    let hasError = false
-    const validated = entries.map((entry) => {
-      const errors: EntryErrors = {}
-      if (!entry.question.trim()) {
-        errors.q = 'Question is required'
-        hasError = true
-      }
-      if (!entry.answer.trim()) {
-        errors.a = 'Answer is required'
-        hasError = true
-      }
-      return { ...entry, errors }
-    })
-
-    if (hasError) {
-      setEntries(validated)
-      return
-    }
-
-    onSave(
-      entries.map((entry) => ({
-        question: entry.question.trim(),
-        answer: entry.answer.trim(),
-        category: entry.category,
-        tags: entry.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
-      })),
-    )
-  }
-
-  const readyCount = entries.filter((entry) => entry.question.trim() && entry.answer.trim()).length
-
-  return (
-    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
-      <div className="flex max-h-[90vh] w-full max-w-xl flex-col rounded-2xl border border-gray-100 bg-white shadow-2xl">
-        <div className="flex shrink-0 items-center justify-between border-b border-gray-100 px-6 py-4">
-          <div>
-            <h2 className="text-base font-semibold text-gray-900">{isEdit ? 'Edit FAQ' : 'Add FAQs'}</h2>
-            {!isEdit && entries.length > 1 && <p className="mt-0.5 text-xs text-gray-400">{entries.length} entries</p>}
-          </div>
-          <button
-            type="button"
-            onClick={onClose}
-            className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
-            aria-label="Close dialog"
-          >
-            <X size={18} />
-          </button>
-        </div>
-
-        <div id="modal-scroll-area" className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
-          {entries.map((entry, index) => (
-            <EntryForm
-              key={`${entry.question}:${index}`}
-              entry={entry}
-              index={index}
-              total={entries.length}
-              categories={categories}
-              onChange={handleChange}
-              onRemove={handleRemove}
-            />
-          ))}
-
-          {!isEdit && (
-            <button
-              type="button"
-              onClick={handleAddAnother}
-              className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-gray-200 py-3 text-sm text-gray-500 transition-all hover:border-teal-300 hover:bg-teal-50/30 hover:text-teal-600"
-            >
-              <Plus size={15} />
-              Add another FAQ
-            </button>
-          )}
-        </div>
-
-        <div className="flex shrink-0 items-center justify-between border-t border-gray-100 bg-gray-50/50 px-6 py-4">
-          {!isEdit && entries.length > 1 ? (
-            <p className="text-xs text-gray-400">
-              {readyCount} of {entries.length} ready to save
-            </p>
-          ) : (
-            <span />
-          )}
-          <div className="flex items-center gap-2">
-            <button
-              type="button"
-              onClick={onClose}
-              disabled={saving}
-              className="rounded-lg px-4 py-2 text-sm text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-50"
-            >
-              Cancel
-            </button>
-            <button
-              type="button"
-              onClick={handleSave}
-              disabled={saving}
-              className="flex items-center gap-1.5 rounded-xl bg-teal-500 px-5 py-2 text-sm text-white shadow-sm transition-colors hover:bg-teal-600 disabled:opacity-50"
-            >
-              {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
-              {isEdit ? 'Save changes' : entries.length > 1 ? `Add ${entries.length} FAQs` : 'Add FAQ'}
-            </button>
-          </div>
-        </div>
-      </div>
-    </div>
-  )
-}
+import { type SemanticMatch, DEFAULT_CATEGORY, getErrorMessage } from './components/kb-types'
+import { FAQRow } from './components/FaqRow'
+import { AddEditFaqModal } from './components/AddEditFaqModal'
 
 // ────────────────────────────────────────────────────────────────────────────
 // Main Component
@@ -1116,7 +608,7 @@ export function KnowledgeBasePage() {
 
       {/* Modal */}
       {modalOpen && (
-        <AddEditModal
+        <AddEditFaqModal
           initial={editTarget}
           categories={availableCategories}
           saving={modalSaving}
```

---

<a id="fe-phase-3"></a>
## Frontend Phase 3: GuardrailsPage Extraction (707 → 509 LOC)

### NEW: 6 extracted component files
```diff
```

### GuardrailsPage.tsx — Reduced to orchestrator
```diff
diff --git a/Chatbot UI and Admin Console/src/features/admin/guardrails/GuardrailsPage.tsx b/Chatbot UI and Admin Console/src/features/admin/guardrails/GuardrailsPage.tsx
index 68c856a..2d89b00 100644
--- a/Chatbot UI and Admin Console/src/features/admin/guardrails/GuardrailsPage.tsx	
+++ b/Chatbot UI and Admin Console/src/features/admin/guardrails/GuardrailsPage.tsx	
@@ -5,20 +5,15 @@ import {
   AlertTriangle,
   ArrowDown,
   ArrowUp,
-  BarChart2,
   Ban,
-  CheckCheck,
+  BarChart2,
   CheckCircle2,
   ChevronsUpDown,
-  ChevronDown,
   ChevronLeft,
   ChevronRight,
   Clock,
-  Layers,
   MessageSquare,
   ShieldAlert,
-  TrendingDown,
-  type LucideIcon,
 } from 'lucide-react'
 import {
   ResponsiveContainer,
@@ -28,13 +23,8 @@ import {
   YAxis,
   CartesianGrid,
   Tooltip,
-  type TooltipContentProps,
 } from 'recharts'
-import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'
-import {
-  type GuardrailEvent,
-  type GuardrailJudgeFailure,
-} from '@features/admin/api/admin'
+import type { GuardrailEvent } from '@features/admin/api/admin'
 import { buildConversationHref } from '@features/admin/lib/admin-links'
 import { formatDateTime } from '@shared/lib/format'
 import { Alert, AlertDescription } from '@components/ui/alert'
@@ -58,11 +48,14 @@ import {
   isBlockingDecision,
   mapGuardrailKpis,
   peakTrendValue,
-  riskLevelFromScore,
   uniqueDecisionOptions,
-  type GuardrailKpiCard,
-  type GuardrailRiskLevel,
 } from './viewmodel'
+import { TrendTooltip } from './components/TrendTooltip'
+import { RiskBadge } from './components/RiskBadge'
+import { DecisionBadge } from './components/DecisionBadge'
+import { KpiCard } from './components/KpiCard'
+import { FailureCard } from './components/FailureCard'
+import { SortHeader, SORT_FIELD_TO_KEY, type SortField, type SortDir } from './components/SortHeader'
 
 type TrendDatum = {
   bucket: string
@@ -70,200 +63,10 @@ type TrendDatum = {
   allowed: number
 }
 
-const KPI_ICON_BY_LABEL: Record<string, LucideIcon> = {
-  'Deny Rate': TrendingDown,
-  'Avg Risk': AlertTriangle,
-  'Queue Depth': Layers,
-  'Oldest Queue Age': Clock,
-  'Policy Adherence': CheckCircle2,
-  'Total Evaluations': BarChart2,
-}
-
-const KPI_TONE_CLASSES: Record<
-  GuardrailKpiCard['tone'],
-  { panel: string; border: string; iconBackground: string; iconShadow: string }
-> = {
-  rose: {
-    panel: 'from-rose-50 dark:from-rose-500/10',
-    border: 'border-rose-100 dark:border-rose-500/30',
-    iconBackground: 'bg-rose-500',
-    iconShadow: 'shadow-rose-200',
-  },
-  amber: {
-    panel: 'from-amber-50 dark:from-amber-500/10',
-    border: 'border-amber-100 dark:border-amber-500/30',
-    iconBackground: 'bg-amber-500',
-    iconShadow: 'shadow-amber-200',
-  },
-  violet: {
-    panel: 'from-violet-50 dark:from-violet-500/10',
-    border: 'border-violet-100 dark:border-violet-500/30',
-    iconBackground: 'bg-violet-500',
-    iconShadow: 'shadow-violet-200',
-  },
-  sky: {
-    panel: 'from-sky-50 dark:from-sky-500/10',
-    border: 'border-sky-100 dark:border-sky-500/30',
-    iconBackground: 'bg-sky-500',
-    iconShadow: 'shadow-sky-200',
-  },
-  emerald: {
-    panel: 'from-emerald-50 dark:from-emerald-500/10',
-    border: 'border-emerald-100 dark:border-emerald-500/30',
-    iconBackground: 'bg-emerald-500',
-    iconShadow: 'shadow-emerald-200',
-  },
-  indigo: {
-    panel: 'from-indigo-50 dark:from-indigo-500/10',
-    border: 'border-indigo-100 dark:border-indigo-500/30',
-    iconBackground: 'bg-indigo-500',
-    iconShadow: 'shadow-indigo-200',
-  },
-}
-
 function buildEventKey(event: GuardrailEvent, index: number): string {
   return `${event.trace_id || 'trace'}:${event.event_time}:${index}`
 }
 
-function TrendTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
-  if (!active || !payload?.length) return null
-
-  return (
-    <div className="rounded-xl border border-border bg-card p-3 shadow-lg">
-      <p className="mb-1 text-[11px] text-muted-foreground">{String(label || '')}</p>
-      {payload.map((entry, index) => (
-        <p key={`${String(entry.name)}-${index}`} style={{ color: entry.color || '#64748b' }} className="text-xs font-semibold">
-          {String(entry.name)}: {Number(entry.value ?? 0)}
-        </p>
-      ))}
-    </div>
-  )
-}
-
-function RiskBadge({ score }: { score: number }) {
-  const level = riskLevelFromScore(score)
-  const label = `${(score * 100).toFixed(0)}%`
-
-  if (level === 'critical') {
-    return (
-      <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-100 px-2.5 py-1 text-[11px] font-bold text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
-        <span className="inline-block size-1.5 rounded-full bg-red-500" /> Critical {label}
-      </span>
-    )
-  }
-
-  if (level === 'high') {
-    return (
-      <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-100 px-2.5 py-1 text-[11px] font-bold text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
-        <span className="inline-block size-1.5 rounded-full bg-amber-500" /> High {label}
-      </span>
-    )
-  }
-
-  if (level === 'medium') {
-    return (
-      <span className="inline-flex items-center gap-1 rounded-full border border-violet-200 bg-violet-100 px-2.5 py-1 text-[11px] font-bold text-violet-700 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300">
-        <span className="inline-block size-1.5 rounded-full bg-violet-500" /> Medium {label}
-      </span>
-    )
-  }
-
-  return (
-    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">
-      <span className="inline-block size-1.5 rounded-full bg-emerald-400" /> Low {label}
-    </span>
-  )
-}
-
-function DecisionBadge({ decision }: { decision: string }) {
-  if (isBlockingDecision(decision)) {
-    return (
-      <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500 px-2.5 py-1 text-[11px] font-bold text-white">
-        <Ban className="size-3" /> {decision}
-      </span>
-    )
-  }
-
-  return (
-    <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-500 px-2.5 py-1 text-[11px] font-bold text-white">
-      <CheckCheck className="size-3" /> {decision}
-    </span>
-  )
-}
-
-function KpiCard({ card }: { card: GuardrailKpiCard }) {
-  const Icon = KPI_ICON_BY_LABEL[card.label] || BarChart2
-  const tone = KPI_TONE_CLASSES[card.tone]
-
-  return (
-    <div className={`rounded-2xl border bg-gradient-to-br to-card p-4 shadow-sm ${tone.panel} ${tone.border}`}>
-      <div className={`mb-3 inline-flex rounded-lg p-2 shadow-md ${tone.iconBackground} ${tone.iconShadow}`}>
-        <Icon className="size-3.5 text-white" />
-      </div>
-      <p className="mb-1 text-[9px] font-bold uppercase leading-none tracking-[0.1em] text-muted-foreground">{card.label}</p>
-      <p className="text-[22px] font-extrabold leading-none text-foreground">{card.value}</p>
-    </div>
-  )
-}
-
-function FailureCard({ failure }: { failure: GuardrailJudgeFailure }) {
-  return (
-    <div className="rounded-xl border border-rose-100 bg-rose-50/40 p-4 dark:border-rose-500/30 dark:bg-rose-500/10">
-      <div className="mb-2 flex items-start justify-between gap-3">
-        <code className="break-all rounded border border-sky-100 bg-sky-50 px-2 py-0.5 text-[11px] text-sky-600 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
-          {failure.trace_id}
-        </code>
-        <span className="shrink-0 whitespace-nowrap rounded-full bg-rose-500 px-2.5 py-1 text-[10px] font-bold text-white">
-          Policy {(failure.policy_adherence * 100).toFixed(0)}%
-        </span>
-      </div>
-      <div className="flex items-start gap-2">
-        <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-amber-500" />
-        <p className="text-xs text-muted-foreground">{failure.summary || 'No summary provided.'}</p>
-      </div>
-    </div>
-  )
-}
-
-type SortField = 'time' | 'session' | 'risk' | 'decision' | 'path'
-type SortDir = 'asc' | 'desc'
-
-const SORT_FIELD_TO_KEY: Record<SortField, keyof GuardrailEvent> = {
-  time: 'event_time',
-  session: 'session_id',
-  risk: 'risk_score',
-  decision: 'risk_decision',
-  path: 'request_path',
-}
-
-function SortHeader({
-  label,
-  field,
-  active,
-  dir,
-  onSort,
-}: {
-  label: string
-  field: SortField
-  active: boolean
-  dir: SortDir
-  onSort: (field: SortField) => void
-}) {
-  return (
-    <th
-      className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-[0.1em] text-muted-foreground cursor-pointer select-none hover:text-foreground transition-colors"
-      onClick={() => onSort(field)}
-    >
-      <span className="inline-flex items-center gap-1">
-        {label}
-        {active
-          ? (dir === 'asc' ? <ArrowUp size={10} /> : <ArrowDown size={10} />)
-          : <ChevronsUpDown size={10} className="opacity-30" />}
-      </span>
-    </th>
-  )
-}
-
 export function GuardrailsPage() {
   const [tenantId, setTenantId] = useState('default')
   const [decisionFilter, setDecisionFilter] = useState('all')
```

---

<a id="fe-phase-4-5"></a>
## Frontend Phases 4-5: Data Extraction + API Typing

### NBFCLandingPage.tsx — Static data extracted to landing-data.ts
```diff
diff --git a/Chatbot UI and Admin Console/src/features/chat/pages/NBFCLandingPage.tsx b/Chatbot UI and Admin Console/src/features/chat/pages/NBFCLandingPage.tsx
index cae0eff..1e2a683 100644
--- a/Chatbot UI and Admin Console/src/features/chat/pages/NBFCLandingPage.tsx	
+++ b/Chatbot UI and Admin Console/src/features/chat/pages/NBFCLandingPage.tsx	
@@ -10,116 +10,13 @@ import {
 import { DISCLAIMER_ACCEPTED_EVENT, DISCLAIMER_ACCEPTED_KEY } from '@components/PrototypeDisclaimer'
 import { ChatWidget } from '../components/ChatWidget'
 import { RegisterDialog } from '../components/RegisterDialog'
-
-// ─── Loan product data ────────────────────────────────────────────────────────
-
-const LOAN_PRODUCTS = [
-  {
-    id: 'home',
-    icon: '🏠',
-    title: 'Home Loans',
-    subtitle: 'Build your dream home',
-    rate: '8.50%',
-    rateLabel: 'p.a. onwards',
-    features: ['Up to ₹5 Crore', 'Tenure up to 30 years', 'Quick approval in 48 hrs'],
-    accent: 'from-teal-500 to-cyan-600',
-    border: 'hover:border-teal-400',
-    badge: 'Most Popular',
-  },
-  {
-    id: 'business',
-    icon: '🏢',
-    title: 'Business Loans',
-    subtitle: 'Fuel your growth',
-    rate: '14.00%',
-    rateLabel: 'p.a. onwards',
-    features: ['Up to ₹2 Crore', 'No collateral required', 'Flexible repayment'],
-    accent: 'from-violet-500 to-purple-600',
-    border: 'hover:border-violet-400',
-    badge: null,
-  },
-  {
-    id: 'personal',
-    icon: '💼',
-    title: 'Personal Loans',
-    subtitle: 'Meet life\'s milestones',
-    rate: '12.50%',
-    rateLabel: 'p.a. onwards',
-    features: ['Up to ₹50 Lakh', 'Instant disbursal', 'Minimal documentation'],
-    accent: 'from-orange-500 to-amber-600',
-    border: 'hover:border-orange-400',
-    badge: null,
-  },
-  {
-    id: 'vehicle',
-    icon: '🚗',
-    title: 'Vehicle Loans',
-    subtitle: 'Drive your ambitions',
-    rate: '9.75%',
-    rateLabel: 'p.a. onwards',
-    features: ['New & used vehicles', 'Up to 95% LTV', 'Doorstep service'],
-    accent: 'from-sky-500 to-blue-600',
-    border: 'hover:border-sky-400',
-    badge: null,
-  },
-] as const
-
-const FEATURES = [
-  {
-    icon: '⚡',
-    title: 'Instant Eligibility Check',
-    desc: 'Get your loan eligibility in under 60 seconds with our AI-powered assessment engine.',
-  },
-  {
-    icon: '🔒',
-    title: 'Bank-Grade Security',
-    desc: '256-bit encryption and Non-RBI-compliant data handling keeps your information safe.',
-  },
-  {
-    icon: '📱',
-    title: '100% Digital Process',
-    desc: 'Apply, track, and manage your loan entirely online — no branch visits needed.',
-  },
-  {
-    icon: '🤝',
-    title: 'Dedicated Relationship Manager',
-    desc: 'Get a personal RM assigned to guide you through every step of your loan journey.',
-  },
-  {
-    icon: '💰',
-    title: 'Best-in-Class Rates',
-    desc: 'Competitive interest rates with transparent fee structures and no hidden charges.',
-  },
-  {
-    icon: '🤖',
-    title: 'AI-Powered Support',
-    desc: '24×7 intelligent chatbot answers all your queries in real-time with instant accuracy.',
-  },
-]
-
-const STATS = [
-  { value: '₹50,000 Cr+', label: 'Loans Disbursed' },
-  { value: '5 Lakh+', label: 'Happy Customers' },
-  { value: '48 hrs', label: 'Avg Approval Time' },
-  { value: '99.2%', label: 'Customer Satisfaction' },
-]
-
-const LANDING_SPOTLIGHT_STORAGE_KEY = 'mft_landing_spotlight_dismissed_v1'
-
-const LANDING_SPOTLIGHT_STEPS = [
-  {
-    targetId: 'landing-nav-ctas',
-    title: 'Start with the main actions',
-    description:
-      'This rail keeps the key flows close by: admin access, quick registration, and a direct route to apply.',
-  },
-  {
-    targetId: 'landing-chat-launcher',
-    title: 'Need help instantly?',
-    description:
-      'Open the assistant at any time to ask about rates, eligibility, repayment plans, or your application.',
-  },
-] as const
+import {
+  FEATURES,
+  LANDING_SPOTLIGHT_STEPS,
+  LANDING_SPOTLIGHT_STORAGE_KEY,
+  LOAN_PRODUCTS,
+  STATS,
+} from './landing-data'
 
 const CTA_GEOMETRY =
   'inline-flex min-h-12 items-center justify-center rounded-full px-6 text-sm font-semibold tracking-tight transition-all duration-200'
```

### health.ts — Promise<any> → typed interfaces
```diff
diff --git a/Chatbot UI and Admin Console/src/features/admin/api/health.ts b/Chatbot UI and Admin Console/src/features/admin/api/health.ts
index 63b91ef..65b1f3a 100644
--- a/Chatbot UI and Admin Console/src/features/admin/api/health.ts	
+++ b/Chatbot UI and Admin Console/src/features/admin/api/health.ts	
@@ -36,6 +36,24 @@ export interface SystemHealthResponse {
   timestamp: number
 }
 
+export interface RateLimitMetricsResponse {
+  enabled: boolean
+  message?: string
+  metrics?: Record<string, Record<string, number>>
+  timestamp?: number
+}
+
+export interface RateLimitConfigResponse {
+  enabled: boolean
+  algorithm: string
+  failure_mode: string
+  max_burst: number
+  per_ip_enabled: boolean
+  endpoints: Record<string, number>
+  tiers: Record<string, number>
+  per_ip: { enabled: boolean; limit: number }
+}
+
 // ── API ──────────────────────────────────────────────────────────────────────
 
 export async function fetchModels(): Promise<AgentModelCategory[]> {
@@ -49,12 +67,10 @@ export async function fetchSystemHealth(): Promise<SystemHealthResponse> {
   return requestJson({ method: 'GET', path: '/health/ready' })
 }
 
-// eslint-disable-next-line @typescript-eslint/no-explicit-any -- untyped backend response; type properly when API schema is available
-export async function fetchRateLimitMetrics(): Promise<any> {
+export async function fetchRateLimitMetrics(): Promise<RateLimitMetricsResponse> {
   return requestJson({ method: 'GET', path: '/rate-limit/metrics' })
 }
 
-// eslint-disable-next-line @typescript-eslint/no-explicit-any -- untyped backend response; type properly when API schema is available
-export async function fetchRateLimitConfig(): Promise<any> {
+export async function fetchRateLimitConfig(): Promise<RateLimitConfigResponse> {
   return requestJson({ method: 'GET', path: '/rate-limit/config' })
 }
```

---

<a id="server-hydration"></a>
## Server-Side Chat Hydration — localStorage → Checkpointer (Post-Audit Fix)

### sessions.py — NEW: GET /agent/sessions/{id}/messages endpoint
```diff
diff --git a/backend/src/agent_service/api/endpoints/sessions.py b/backend/src/agent_service/api/endpoints/sessions.py
index d56fab2..4c345ed 100644
--- a/backend/src/agent_service/api/endpoints/sessions.py
+++ b/backend/src/agent_service/api/endpoints/sessions.py
@@ -3,7 +3,7 @@
 import logging
 
 import uuid_utils  # Added dependency
-from fastapi import APIRouter, HTTPException, Query
+from fastapi import APIRouter, HTTPException, Query, Request
 
 from src.agent_service.core.config import DEFAULT_CHAT_MODEL, DEFAULT_CHAT_PROVIDER
 from src.agent_service.core.prompts import prompt_manager
@@ -63,6 +63,67 @@ async def list_active_sessions():
         raise HTTPException(status_code=500, detail=str(e)) from e
 
 
+@router.get("/sessions/{session_id}/messages")
+async def get_session_messages(
+    session_id: str,
+    request: Request,
+    limit: int = Query(default=120, ge=1, le=500),
+):
+    """Retrieve chat messages from the LangGraph checkpointer.
+
+    Returns messages in the frontend ChatMessage shape, hydrated from the
+    server-side checkpoint rather than client-side localStorage.
+    """
+    try:
+        sid = session_utils.validate_session_id(session_id)
+    except ValueError as e:
+        raise HTTPException(status_code=400, detail=str(e)) from e
+
+    checkpointer = getattr(request.app.state, "checkpointer", None)
+    if not checkpointer:
+        raise HTTPException(status_code=503, detail="Checkpointer unavailable")
+
+    config = {"configurable": {"thread_id": sid}}
+    checkpoint_tuple = await checkpointer.aget_tuple(config)
+
+    if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
+        return {"session_id": sid, "messages": []}
+
+    state = checkpoint_tuple.checkpoint.get("channel_values", {})
+    raw_messages = state.get("messages", [])
+
+    messages = []
+    for i, msg in enumerate(raw_messages[-limit:]):
+        msg_type = getattr(msg, "type", "")
+        if msg_type not in ("human", "ai"):
+            continue
+
+        kwargs = getattr(msg, "additional_kwargs", {}) or {}
+        resp_meta = getattr(msg, "response_metadata", {}) or {}
+
+        created = resp_meta.get("created")
+        timestamp = int(created * 1000) if created else 0
+
+        messages.append(
+            {
+                "id": kwargs.get("msg_id") or f"{sid}~{i}",
+                "role": "user" if msg_type == "human" else "assistant",
+                "content": getattr(msg, "content", ""),
+                "reasoning": str(kwargs.get("reasoning") or ""),
+                "timestamp": timestamp,
+                "status": "done",
+                "traceId": kwargs.get("trace_id"),
+                "provider": kwargs.get("provider") or resp_meta.get("model_provider"),
+                "model": kwargs.get("model") or resp_meta.get("model_name"),
+                "totalTokens": kwargs.get("total_tokens"),
+                "cost": kwargs.get("cost"),
+                "followUps": kwargs.get("follow_ups"),
+            }
+        )
+
+    return {"session_id": sid, "messages": messages}
+
+
 @router.get("/verify/{session_id}")
 async def verify_session(session_id: str):
     """Verify if a session exists."""
```

### test_session_messages.py — NEW: 3 endpoint tests
```diff
diff --git a/backend/tests/test_session_messages.py b/backend/tests/test_session_messages.py
new file mode 100644
index 0000000..3633db4
--- /dev/null
+++ b/backend/tests/test_session_messages.py
@@ -0,0 +1,126 @@
+"""Tests for GET /agent/sessions/{session_id}/messages endpoint."""
+
+from __future__ import annotations
+
+from types import SimpleNamespace
+from typing import Any, Optional
+
+import pytest
+from langchain_core.messages import AIMessage, HumanMessage
+
+import src.agent_service.api.endpoints.sessions as sessions_mod
+
+
+class _FakeCheckpointTuple:
+    def __init__(self, checkpoint: dict[str, Any]) -> None:
+        self.checkpoint = checkpoint
+        self.config = {"configurable": {"thread_id": "sess-1"}}
+
+
+class _FakeCheckpointer:
+    def __init__(self, checkpoint: Optional[dict[str, Any]] = None) -> None:
+        self._checkpoint = checkpoint
+
+    async def aget_tuple(self, config: dict) -> Optional[_FakeCheckpointTuple]:
+        if self._checkpoint is None:
+            return None
+        return _FakeCheckpointTuple(self._checkpoint)
+
+
+@pytest.mark.asyncio
+async def test_session_messages_returns_human_and_ai_messages():
+    """Endpoint transforms LangChain messages into frontend ChatMessage shape."""
+    ai_msg = AIMessage(
+        content="Your EMI is ₹12,500.",
+        additional_kwargs={
+            "trace_id": "trace-abc",
+            "provider": "groq",
+            "model": "openai/gpt-oss-120b",
+            "total_tokens": 350,
+        },
+        response_metadata={
+            "created": 1712345678.0,
+            "model_name": "openai/gpt-oss-120b",
+            "model_provider": "groq",
+        },
+    )
+    checkpoint = {
+        "channel_values": {
+            "messages": [
+                HumanMessage(content="What is my EMI?"),
+                ai_msg,
+            ],
+        },
+    }
+    checkpointer = _FakeCheckpointer(checkpoint)
+    fake_app = SimpleNamespace(state=SimpleNamespace(checkpointer=checkpointer))
+    request = SimpleNamespace(app=fake_app)
+
+    response = await sessions_mod.get_session_messages(
+        session_id="sess-1",
+        request=request,
+        limit=120,
+    )
+
+    assert response["session_id"] == "sess-1"
+    assert len(response["messages"]) == 2
+
+    user_msg = response["messages"][0]
+    assert user_msg["role"] == "user"
+    assert user_msg["content"] == "What is my EMI?"
+    assert user_msg["status"] == "done"
+
+    assistant_msg = response["messages"][1]
+    assert assistant_msg["role"] == "assistant"
+    assert assistant_msg["content"] == "Your EMI is ₹12,500."
+    assert assistant_msg["traceId"] == "trace-abc"
+    assert assistant_msg["provider"] == "groq"
+    assert assistant_msg["model"] == "openai/gpt-oss-120b"
+    assert assistant_msg["totalTokens"] == 350
+    assert assistant_msg["timestamp"] == 1712345678000
+
+
+@pytest.mark.asyncio
+async def test_session_messages_returns_empty_for_missing_checkpoint():
+    """Endpoint returns empty messages when checkpoint does not exist."""
+    checkpointer = _FakeCheckpointer(checkpoint=None)
+    fake_app = SimpleNamespace(state=SimpleNamespace(checkpointer=checkpointer))
+    request = SimpleNamespace(app=fake_app)
+
+    response = await sessions_mod.get_session_messages(
+        session_id="sess-unknown",
+        request=request,
+        limit=120,
+    )
+
+    assert response["session_id"] == "sess-unknown"
+    assert response["messages"] == []
+
+
+@pytest.mark.asyncio
+async def test_session_messages_skips_tool_messages():
+    """Tool messages are filtered out — frontend displays them inline via SSE."""
+    from langchain_core.messages import ToolMessage
+
+    checkpoint = {
+        "channel_values": {
+            "messages": [
+                HumanMessage(content="Show my loan details"),
+                ToolMessage(content="tool output", tool_call_id="tc-1"),
+                AIMessage(content="Here are your loan details."),
+            ],
+        },
+    }
+    checkpointer = _FakeCheckpointer(checkpoint)
+    fake_app = SimpleNamespace(state=SimpleNamespace(checkpointer=checkpointer))
+    request = SimpleNamespace(app=fake_app)
+
+    response = await sessions_mod.get_session_messages(
+        session_id="sess-2",
+        request=request,
+        limit=120,
+    )
+
+    assert len(response["messages"]) == 2
+    assert response["messages"][0]["role"] == "user"
+    assert response["messages"][1]["role"] == "assistant"
```

### sessions.ts — NEW: fetchSessionMessages API + ServerChatMessage type
```diff
diff --git a/Chatbot UI and Admin Console/src/shared/api/sessions.ts b/Chatbot UI and Admin Console/src/shared/api/sessions.ts
index f2c62c7..a713ffa 100644
--- a/Chatbot UI and Admin Console/src/shared/api/sessions.ts	
+++ b/Chatbot UI and Admin Console/src/shared/api/sessions.ts	
@@ -1,3 +1,4 @@
+import type { CostEvent } from '@shared/types/chat'
 import { requestJson } from './http'
 
 // ── Types ────────────────────────────────────────────────────────────────────
@@ -22,6 +23,32 @@ export async function fetchSessionConfig(sessionId: string): Promise<SessionConf
   })
 }
 
+export interface ServerChatMessage {
+  id: string
+  role: 'user' | 'assistant'
+  content: string
+  reasoning: string
+  timestamp: number
+  status: string
+  traceId?: string
+  provider?: string
+  model?: string
+  totalTokens?: number
+  cost?: CostEvent | null
+  followUps?: string[]
+}
+
+export async function fetchSessionMessages(
+  sessionId: string,
+  limit = 120,
+): Promise<ServerChatMessage[]> {
+  const res = await requestJson<{ messages: ServerChatMessage[] }>({
+    method: 'GET',
+    path: `/agent/sessions/${encodeURIComponent(sessionId)}/messages?limit=${limit}`,
+  })
+  return res.messages ?? []
+}
+
 export async function saveSessionConfig(payload: {
   session_id: string
   system_prompt?: string
```

### useChatStream.ts — Server hydration primary, localStorage fallback
```diff
diff --git a/Chatbot UI and Admin Console/src/features/chat/hooks/useChatStream.ts b/Chatbot UI and Admin Console/src/features/chat/hooks/useChatStream.ts
index 2276ba4..01843ce 100644
--- a/Chatbot UI and Admin Console/src/features/chat/hooks/useChatStream.ts	
+++ b/Chatbot UI and Admin Console/src/features/chat/hooks/useChatStream.ts	
@@ -1,5 +1,6 @@
 import { useCallback, useEffect, useRef, useState } from 'react'
 import { API_BASE_URL, requestJson } from '@shared/api/http'
+import { fetchSessionMessages } from '@shared/api/sessions'
 import { streamSse } from '@shared/api/sse'
 import { parseMaybeJson } from '@shared/lib/json'
 import type { ChatMessage, CostEvent, ToolCallEvent } from '@shared/types/chat'
@@ -116,18 +117,31 @@ export function useChatStream() {
     }
   }, [])
 
-  // Initialize session on mount
+  // Initialize session on mount — hydrate from server, localStorage fallback
   useEffect(() => {
     const existing = localStorage.getItem(SESSION_KEY)
     if (existing) {
       setSessionId(existing)
-      setMessages(safeParseMessages(localStorage.getItem(messageKey(existing))))
+      // Primary: fetch history from backend checkpointer
+      fetchSessionMessages(existing)
+        .then((serverMsgs) => {
+          if (serverMsgs.length > 0) {
+            setMessages(serverMsgs as ChatMessage[])
+          } else {
+            // Fallback: localStorage cache for sessions not yet in checkpointer
+            setMessages(safeParseMessages(localStorage.getItem(messageKey(existing))))
+          }
+        })
+        .catch(() => {
+          // Network error: use localStorage cache for offline/degraded mode
+          setMessages(safeParseMessages(localStorage.getItem(messageKey(existing))))
+        })
     } else {
       initNewSession()
     }
   }, [initNewSession])
 
-  // Persist messages whenever they change
+  // Write-through cache: persist to localStorage for fast reload / offline fallback
   useEffect(() => {
     if (!sessionId) return
     localStorage.setItem(messageKey(sessionId), JSON.stringify(messages.slice(-120)))
```

### useChatStream.test.ts — Mock for new API dependency
```diff
diff --git a/Chatbot UI and Admin Console/src/features/chat/hooks/useChatStream.test.ts b/Chatbot UI and Admin Console/src/features/chat/hooks/useChatStream.test.ts
index 4cfcfd5..92e08e2 100644
--- a/Chatbot UI and Admin Console/src/features/chat/hooks/useChatStream.test.ts	
+++ b/Chatbot UI and Admin Console/src/features/chat/hooks/useChatStream.test.ts	
@@ -2,9 +2,10 @@ import { act, renderHook } from '@testing-library/react'
 import { beforeEach, describe, expect, it, vi } from 'vitest'
 import { useChatStream } from './useChatStream'
 
-const { streamSseMock, requestJsonMock } = vi.hoisted(() => ({
+const { streamSseMock, requestJsonMock, fetchSessionMessagesMock } = vi.hoisted(() => ({
   streamSseMock: vi.fn(),
   requestJsonMock: vi.fn(),
+  fetchSessionMessagesMock: vi.fn(),
 }))
 
 type StreamOnEvent = (eventName: string, data: string, parsed?: unknown) => void
@@ -14,6 +15,10 @@ vi.mock('@shared/api/http', () => ({
   requestJson: requestJsonMock,
 }))
 
+vi.mock('@shared/api/sessions', () => ({
+  fetchSessionMessages: fetchSessionMessagesMock,
+}))
+
 vi.mock('@shared/api/sse', () => ({
   streamSse: streamSseMock,
 }))
@@ -22,6 +27,7 @@ describe('useChatStream stream-only contract', () => {
   beforeEach(() => {
     streamSseMock.mockReset()
     requestJsonMock.mockReset()
+    fetchSessionMessagesMock.mockReset()
     localStorage.clear()
 
     requestJsonMock.mockResolvedValue({
@@ -30,6 +36,9 @@ describe('useChatStream stream-only contract', () => {
       model_name: 'test-model',
       system_prompt: 'sys',
     })
+
+    // Default: server returns empty messages (new session)
+    fetchSessionMessagesMock.mockResolvedValue([])
   })
 
   async function initHook() {
```


---

<a id="final-fixes"></a>
## Final Audit Fixes — Redis Singleton + CRM Client + Error Parsing

### session_store.py — Removed misleading redis_uri parameter from get_redis()
```diff
diff --git a/backend/src/mcp_service/session_store.py b/backend/src/mcp_service/session_store.py
index dd8e087..b31acb1 100644
--- a/backend/src/mcp_service/session_store.py
+++ b/backend/src/mcp_service/session_store.py
@@ -33,8 +33,12 @@ def _redact_uri(uri: str) -> str:
     return uri
 
 
-async def get_redis(redis_uri: Optional[str] = None) -> AsyncRedis:
-    """Return (and lazily create) the module-level async Redis client."""
+async def get_redis() -> AsyncRedis:
+    """Return (and lazily create) the module-level async Redis client.
+
+    Uses the REDIS_URL from config. A single connection pool is shared
+    process-wide — no per-caller URI overrides to prevent pool contamination.
+    """
     global _pool, _client
 
     if _client is not None:
@@ -44,9 +48,8 @@ async def get_redis(redis_uri: Optional[str] = None) -> AsyncRedis:
         if _client is not None:
             return _client
 
-        uri = redis_uri or REDIS_URL
         _pool = ConnectionPool.from_url(
-            uri,
+            REDIS_URL,
             decode_responses=True,
             encoding="utf-8",
             max_connections=20,
@@ -54,7 +57,7 @@ async def get_redis(redis_uri: Optional[str] = None) -> AsyncRedis:
         )
         _client = AsyncRedis(connection_pool=_pool)
         await _client.ping()
-        log.info("Connected to Redis: %s", _redact_uri(uri))
+        log.info("Connected to Redis: %s", _redact_uri(REDIS_URL))
 
     return _client
 
@@ -90,11 +93,8 @@ def valid_session_id(session_id: object) -> str:
 class RedisSessionStore:
     """Async Redis session store used by MCP tool implementations."""
 
-    def __init__(self, redis_uri: Optional[str] = None) -> None:
-        self._redis_uri = redis_uri
-
     async def _redis(self) -> AsyncRedis:
-        return await get_redis(self._redis_uri)
+        return await get_redis()
 
     @staticmethod
     def _valid_session_id(session_id: object) -> Optional[str]:
```

### crm.ts — CrmGraphQLError class, timeout, retry
```diff
diff --git a/Chatbot UI and Admin Console/src/shared/api/crm.ts b/Chatbot UI and Admin Console/src/shared/api/crm.ts
index 3b2edb2..10c38f5 100644
--- a/Chatbot UI and Admin Console/src/shared/api/crm.ts	
+++ b/Chatbot UI and Admin Console/src/shared/api/crm.ts	
@@ -23,32 +23,70 @@ interface GraphQLResponse<T> {
   errors?: Array<{ message: string }>
 }
 
+class CrmGraphQLError extends Error {
+  constructor(
+    message: string,
+    public readonly status?: number,
+    public readonly graphqlErrors?: Array<{ message: string }>,
+  ) {
+    super(message)
+    this.name = 'CrmGraphQLError'
+  }
+}
+
+const CRM_TIMEOUT_MS = 15_000
+const CRM_MAX_RETRIES = 1
+
 async function crmGraphQL<T>(
   query: string,
   variables?: Record<string, unknown>,
 ): Promise<T> {
   const base = getCrmBase()
-  const res = await fetch(`${base}/graphql`, {
-    method: 'POST',
-    headers: { 'Content-Type': 'application/json' },
-    body: JSON.stringify({ query, variables }),
-  })
+  const url = `${base}/graphql`
 
-  const json: GraphQLResponse<T> = await res.json()
+  let lastError: Error | null = null
+  for (let attempt = 0; attempt <= CRM_MAX_RETRIES; attempt++) {
+    try {
+      const controller = new AbortController()
+      const timer = setTimeout(() => controller.abort(), CRM_TIMEOUT_MS)
 
-  if (json.errors && json.errors.length > 0) {
-    throw new Error(json.errors[0].message)
-  }
+      const res = await fetch(url, {
+        method: 'POST',
+        headers: { 'Content-Type': 'application/json' },
+        body: JSON.stringify({ query, variables }),
+        signal: controller.signal,
+      })
+      clearTimeout(timer)
 
-  if (!res.ok) {
-    throw new Error(`CRM request failed (${res.status})`)
-  }
+      const json: GraphQLResponse<T> = await res.json()
+
+      if (json.errors && json.errors.length > 0) {
+        throw new CrmGraphQLError(
+          json.errors[0].message,
+          res.status,
+          json.errors,
+        )
+      }
+
+      if (!res.ok) {
+        throw new CrmGraphQLError(`CRM request failed (${res.status})`, res.status)
+      }
 
-  if (!json.data) {
-    throw new Error('Empty response from CRM')
+      if (!json.data) {
+        throw new CrmGraphQLError('Empty response from CRM')
+      }
+
+      return json.data
+    } catch (err) {
+      lastError = err instanceof Error ? err : new Error(String(err))
+      if (attempt < CRM_MAX_RETRIES && !(err instanceof CrmGraphQLError)) {
+        continue // Retry on network/timeout errors only, not GraphQL errors
+      }
+      throw lastError
+    }
   }
 
-  return json.data
+  throw lastError ?? new Error('CRM request failed')
 }
 
 function normalizePhone(raw: string): string {
```

### http.ts — RFC 7807 Problem Details error parsing
```diff
diff --git a/Chatbot UI and Admin Console/src/shared/api/http.ts b/Chatbot UI and Admin Console/src/shared/api/http.ts
index 0dde66d..d978a23 100644
--- a/Chatbot UI and Admin Console/src/shared/api/http.ts	
+++ b/Chatbot UI and Admin Console/src/shared/api/http.ts	
@@ -53,30 +53,44 @@ async function parseBody(response: Response): Promise<unknown> {
   }
 }
 
+/**
+ * RFC 7807 Problem Details for HTTP APIs + FastAPI error shape support.
+ *
+ * Extraction priority:
+ * 1. RFC 7807 `title` / `detail` fields (standardised)
+ * 2. FastAPI `detail` string (default HTTPException shape)
+ * 3. Generic `message` / `error` fields (common REST conventions)
+ * 4. Fallback to status code
+ */
+interface ProblemDetails {
+  type?: string
+  title?: string
+  status?: number
+  detail?: string | { message?: string; detail?: string }
+  instance?: string
+  message?: string
+  error?: string
+}
+
 function resolveErrorMessage(parsed: unknown, status: number): string {
   if (typeof parsed === 'string' && parsed.trim()) return parsed
   if (typeof parsed !== 'object' || parsed === null) return `Request failed (${status})`
 
-  const payload = parsed as {
-    message?: string
-    detail?: string | { message?: string; detail?: string }
-  }
-  if (typeof payload.message === 'string' && payload.message.trim()) return payload.message.trim()
-  if (typeof payload.detail === 'string' && payload.detail.trim()) return payload.detail.trim()
-  if (payload.detail && typeof payload.detail === 'object') {
-    if (
-      typeof payload.detail.message === 'string' &&
-      payload.detail.message.trim()
-    ) {
-      return payload.detail.message.trim()
-    }
-    if (
-      typeof payload.detail.detail === 'string' &&
-      payload.detail.detail.trim()
-    ) {
-      return payload.detail.detail.trim()
-    }
+  const p = parsed as ProblemDetails
+
+  // RFC 7807: prefer `title` for short user-facing messages, `detail` for specifics
+  if (typeof p.title === 'string' && p.title.trim()) return p.title.trim()
+  if (typeof p.detail === 'string' && p.detail.trim()) return p.detail.trim()
+  // FastAPI nested detail object
+  if (p.detail && typeof p.detail === 'object') {
+    const nested = p.detail
+    if (typeof nested.message === 'string' && nested.message.trim()) return nested.message.trim()
+    if (typeof nested.detail === 'string' && nested.detail.trim()) return nested.detail.trim()
   }
+  // Common REST conventions
+  if (typeof p.message === 'string' && p.message.trim()) return p.message.trim()
+  if (typeof p.error === 'string' && p.error.trim()) return p.error.trim()
+
   return `Request failed (${status})`
 }
 
```
