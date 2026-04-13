# Final Audit Remediation — Code Diff

**Branch:** `fix/final-audit-remediation` (from `refactor/architectural-audit-remediation`)
**Date:** 2026-04-06
**Commits:** 5 (`99093c4`, `60c5060`, `f46787a`, `445e095`, `2f1c6bb`)
**Backend Tests:** 149/149 passing
**Frontend Tests:** 92/92 passing
**Total change:** 36 files changed (6,127 insertions, 524 deletions)

---

## Table of Contents

- [Redis Singleton + CRM Client + Error Parsing](#commit-1)
- [13 Validated Audit Findings — Security, Cleanup, Dedup](#commit-2)
- [.editorconfig](#commit-3)

---

<a id="commit-1"></a>
## Commit 1: Redis Singleton + CRM Client + Error Parsing (`99093c4`)

### session_store.py — Removed misleading redis_uri parameter
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

### crm.ts — CrmGraphQLError + timeout + retry
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

---

<a id="commit-2"></a>
## Commit 2: 13 Validated Audit Findings (`60c5060`)

### Security: admin_auth.py — Fail-closed when ADMIN_API_KEY unset
```diff
diff --git a/backend/src/agent_service/api/admin_auth.py b/backend/src/agent_service/api/admin_auth.py
index 0386b17..f0c2eb5 100644
--- a/backend/src/agent_service/api/admin_auth.py
+++ b/backend/src/agent_service/api/admin_auth.py
@@ -9,13 +9,16 @@ from src.agent_service.core.config import ADMIN_API_KEY
 
 def require_admin_key(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")) -> None:
     """
-    Validate X-Admin-Key when ADMIN_API_KEY is configured.
+    Validate X-Admin-Key header against the configured ADMIN_API_KEY.
 
-    If ADMIN_API_KEY is not set, the service remains backward-compatible and does not
-    enforce header validation.
+    Fail-closed: if ADMIN_API_KEY is not set, all admin endpoints are unavailable
+    (returns 503) rather than silently allowing unauthenticated access.
     """
     if not ADMIN_API_KEY:
-        return
+        raise HTTPException(
+            status_code=503,
+            detail="Admin API key not configured. Set ADMIN_API_KEY environment variable.",
+        )
 
     if not x_admin_key or x_admin_key.strip() != ADMIN_API_KEY:
         raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Key")
```

### Security: rate_limit_metrics.py — Auth on reset endpoint
```diff
diff --git a/backend/src/agent_service/api/endpoints/rate_limit_metrics.py b/backend/src/agent_service/api/endpoints/rate_limit_metrics.py
index 1db7353..99fad80 100644
--- a/backend/src/agent_service/api/endpoints/rate_limit_metrics.py
+++ b/backend/src/agent_service/api/endpoints/rate_limit_metrics.py
@@ -10,8 +10,9 @@ Provides:
 import logging
 from typing import Any, Dict
 
-from fastapi import APIRouter, HTTPException, Request, status
+from fastapi import APIRouter, Depends, HTTPException, Request, status
 
+from src.agent_service.api.admin_auth import require_admin_key
 from src.agent_service.core.config import RATE_LIMIT_ENABLED
 from src.agent_service.core.rate_limiter_manager import (
     enforce_rate_limit,
@@ -95,7 +96,11 @@ async def get_identifier_status(identifier: str, http_request: Request) -> Dict[
 
 
 @router.post("/reset/{identifier}")
-async def reset_identifier_limit(identifier: str, http_request: Request) -> Dict[str, Any]:
+async def reset_identifier_limit(
+    identifier: str,
+    http_request: Request,
+    _admin: None = Depends(require_admin_key),
+) -> Dict[str, Any]:
     """
     Reset rate limit for a specific identifier (ADMIN ONLY).
 
@@ -111,16 +116,12 @@ async def reset_identifier_limit(identifier: str, http_request: Request) -> Dict
     - VIP customer support
 
     **Security:**
-    - Should be protected by admin authentication middleware
+    - Protected by admin key authentication via X-Admin-Key header
     - Logs all reset operations for audit trail
     """
     if not RATE_LIMIT_ENABLED:
         return {"enabled": False, "message": "Rate limiting is globally disabled"}
 
-    # TODO: Add admin authentication check here
-    # if not is_admin(http_request):
-    #     raise HTTPException(status_code=403, detail="Admin access required")
-
     # Rate limit this endpoint (prevent reset abuse)
     manager = get_rate_limiter_manager()
     session_limiter = await manager.get_session_limiter()
```

### Security: eval_live.py — Auth on SSE endpoint
```diff
diff --git a/backend/src/agent_service/api/eval_live.py b/backend/src/agent_service/api/eval_live.py
index c3c7e60..4cf45d8 100644
--- a/backend/src/agent_service/api/eval_live.py
+++ b/backend/src/agent_service/api/eval_live.py
@@ -4,10 +4,11 @@ import json
 import logging
 from typing import Any, AsyncGenerator, Dict
 
-from fastapi import APIRouter, Query, Request
+from fastapi import APIRouter, Depends, Query, Request
 from redis.asyncio import Redis
 from sse_starlette.sse import EventSourceResponse
 
+from src.agent_service.api.admin_auth import require_admin_key
 from src.agent_service.core.config import REDIS_URL
 
 log = logging.getLogger("eval_live_api")
@@ -30,6 +31,7 @@ async def eval_live(
     cursor: str = Query(
         "$", description="Redis stream cursor. Use '$' for only-new. Use '0-0' to replay."
     ),
+    _admin: None = Depends(require_admin_key),
 ):
     """
     SSE live feed of new eval ingests.
```

### Security: sessions.py — Auth on admin session endpoints
```diff
diff --git a/backend/src/agent_service/api/endpoints/sessions.py b/backend/src/agent_service/api/endpoints/sessions.py
index 4c345ed..9b57c51 100644
--- a/backend/src/agent_service/api/endpoints/sessions.py
+++ b/backend/src/agent_service/api/endpoints/sessions.py
@@ -3,8 +3,9 @@
 import logging
 
 import uuid_utils  # Added dependency
-from fastapi import APIRouter, HTTPException, Query, Request
+from fastapi import APIRouter, Depends, HTTPException, Query, Request
 
+from src.agent_service.api.admin_auth import require_admin_key
 from src.agent_service.core.config import DEFAULT_CHAT_MODEL, DEFAULT_CHAT_PROVIDER
 from src.agent_service.core.prompts import prompt_manager
 from src.agent_service.core.resource_resolver import ResourceResolver
@@ -53,8 +54,8 @@ async def initialize_session():
 
 
 @router.get("/sessions")
-async def list_active_sessions():
-    """List all active sessions."""
+async def list_active_sessions(_admin: None = Depends(require_admin_key)):
+    """List all active sessions (admin only)."""
     try:
         sessions = await config_manager.list_sessions()
         return {"count": len(sessions), "sessions": sessions}
@@ -289,9 +290,9 @@ async def reset_session_cost(session_id: str):
 
 
 @router.get("/sessions/summary")
-async def get_all_sessions_cost_summary():
+async def get_all_sessions_cost_summary(_admin: None = Depends(require_admin_key)):
     """
-    Get cost summary across all active sessions.
+    Get cost summary across all active sessions (admin only).
 
     Returns:
         - active_sessions: Count of sessions with cost data
@@ -305,9 +306,9 @@ async def get_all_sessions_cost_summary():
 
 
 @router.delete("/sessions/cleanup")
-async def cleanup_corrupted_cost_keys():
+async def cleanup_corrupted_cost_keys(_admin: None = Depends(require_admin_key)):
     """
-    Admin endpoint: Clean up corrupted cost tracking keys.
+    Admin endpoint: Clean up corrupted cost tracking keys (admin only).
 
     This removes keys with wrong Redis types (from old implementations).
     """
```

### Backend: Deleted duplicate router/ directory
```diff
diff --git a/backend/scripts/generate_context_docs.py b/backend/scripts/generate_context_docs.py
index 3d49387..7652281 100755
--- a/backend/scripts/generate_context_docs.py
+++ b/backend/scripts/generate_context_docs.py
@@ -71,7 +71,7 @@ ROLE_HINTS: dict[str, str] = {
     "src/agent_service/faqs": "FAQ parsing artifacts and ingest support assets.",
     "src/agent_service/features": "Feature flags/prototypes and answerability/follow-up behavior modules.",
     "src/agent_service/llm": "Model catalog and provider client orchestration.",
-    "src/agent_service/router": "NBFC router taxonomy, schemas, service, and worker runtime.",
+    "src/agent_service/features/routing": "NBFC router taxonomy, schemas, service, and worker runtime.",
     "src/agent_service/security": "Security middleware, runtime checks, metrics, and TOR/GeoIP controls.",
     "src/agent_service/tools": "Graph/tool adapters for knowledge and MCP integration.",
     "src/common": "Shared logging and connection management primitives.",
diff --git a/backend/src/agent_service/router/prototypes_nbfc.py b/backend/src/agent_service/router/prototypes_nbfc.py
deleted file mode 100644
index 30a1118..0000000
--- a/backend/src/agent_service/router/prototypes_nbfc.py
+++ /dev/null
@@ -1,88 +0,0 @@
-SENTIMENT_PROTOTYPES = {
-    "positive": [
-        "Thanks! super smooth experience",
-        "mast hai yaar ❤️",
-        "great service",
-        "quick approval thank you",
-    ],
-    "neutral": [
-        "What is the interest rate?",
-        "How to check EMI schedule?",
-        "tenure for 24 months",
-        "what documents needed",
-    ],
-    "negative": [
-        "loan not approved since days",
-        "refund my penalty",
-        "OTP not coming",
-        "agent is harassing",
-        "unauthorized transaction fraud",
-        "paise kat gaye refund nahi aaya",
-        "bc refund",
-        "charged twice",
-    ],
-}
-
-REASON_PROTOTYPES = {
-    "application_status_approval": [
-        "loan not approved",
-        "application pending",
-        "approval delayed",
-        "status stuck",
-    ],
-    "disbursal": [
-        "approved but money not received",
-        "disbursal kab hoga",
-        "amount not credited",
-    ],
-    "emi_payment_reflecting": [
-        "EMI paid but not updated",
-        "payment not reflected",
-        "paid but app not showing",
-    ],
-    "otp_login_app_tech": [
-        "OTP not coming",
-        "login failing",
-        "app crashing",
-        "unable to login",
-    ],
-    "kyc_verification": [
-        "KYC stuck",
-        "PAN name mismatch",
-        "verification failed",
-        "aadhaar issue",
-    ],
-    "collections_harassment": [
-        "recovery agent harassing",
-        "stop calling me",
-        "too many calls",
-    ],
-    "fraud_security": [
-        "unauthorized transaction",
-        "fraud",
-        "scam",
-        "account hacked",
-    ],
-    "foreclosure_partpayment": [
-        "foreclose loan",
-        "preclosure charges",
-        "part payment charges",
-    ],
-    "charges_fees_penalty": [
-        "penalty charges",
-        "late fee",
-        "bounce charges",
-        "fees too high",
-    ],
-    "lead_intent_new_loan": [
-        "new loan",
-        "apply",
-        "eligibility",
-        "rate for 24 month plan",
-    ],
-    "customer_support": [
-        "contact customer care",
-        "helpline number",
-        "support email",
-    ],
-}
diff --git a/backend/src/agent_service/router/schemas.py b/backend/src/agent_service/router/schemas.py
deleted file mode 100644
index 465f6e6..0000000
--- a/backend/src/agent_service/router/schemas.py
+++ /dev/null
@@ -1,22 +0,0 @@
-from __future__ import annotations
-
-from typing import Any, Dict, Literal, Optional
-
-from pydantic import BaseModel, Field
-
-SentimentLabel = Literal["positive", "neutral", "negative"]
-RouterBackend = Literal["embeddings", "llm_glm_4.7", "hybrid"]
-
-
-class LabelScore(BaseModel):
-    label: str
-    score: float = Field(ge=0.0, le=1.0)
-    top: Optional[list[tuple[str, float]]] = None
-
-
-class RouterResult(BaseModel):
-    backend: RouterBackend
-    sentiment: LabelScore
-    reason: Optional[LabelScore] = None
-    override: Optional[str] = None
-    meta: Dict[str, Any] = Field(default_factory=dict)
diff --git a/backend/src/agent_service/router/service.py b/backend/src/agent_service/router/service.py
deleted file mode 100644
index dc497a4..0000000
--- a/backend/src/agent_service/router/service.py
+++ /dev/null
@@ -1,191 +0,0 @@
-from __future__ import annotations
-
-import re
-import time
-from typing import Any, Dict, List, Optional, Tuple
-
-from langchain_core.output_parsers import JsonOutputParser
-from langchain_core.prompts import ChatPromptTemplate
-
-from src.agent_service.core.prompts import prompt_manager
-from src.agent_service.llm.client import get_llm, get_owner_embeddings
-
-from .prototypes_nbfc import REASON_PROTOTYPES, SENTIMENT_PROTOTYPES
-from .schemas import LabelScore, RouterResult
-
-# Regex Patterns
-_PROFANITY = re.compile(r"\b(wtf|bc|mc|bkl|madarchod|behenchod)\b", re.I)
-_NEG_CUES = re.compile(
-    r"\b(refund|charged twice|not coming|failed|harass|fraud|unauthorized|penalty)\b", re.I
-)
-_POS_CUES = re.compile(r"\b(thanks|thank you|love|great|mast|awesome|super smooth)\b", re.I)
-
-
-def _cosine_top(
-    qv: List[float],
-    proto_vecs: Dict[str, List[List[float]]],
-    *,
-    topn: int = 3,
-) -> Tuple[str, float, List[Tuple[str, float]]]:
-    import math
-
-    def cos(a, b):
-        dot = sum(x * y for x, y in zip(a, b, strict=False))
-        na = math.sqrt(sum(x * x for x in a)) or 1e-9
-        nb = math.sqrt(sum(x * x for x in b)) or 1e-9
-        return dot / (na * nb)
-
-    scored: List[Tuple[str, float]] = []
-    for label, vecs in proto_vecs.items():
-        best = max((cos(qv, pv) for pv in vecs), default=-1.0)
-        scored.append((label, float(best)))
-
-    scored.sort(key=lambda x: x[1], reverse=True)
-    best_label, best_score = scored[0]
-    return best_label, best_score, scored[:topn]
-
-
-class RouterService:
-    def __init__(self):
-        # We perform lazy initialization of embeddings to allow for BYOK injection
-        # or graceful failure if no server-side key exists.
-        self._sent_proto_vecs: Optional[Dict[str, List[List[float]]]] = None
-        self._reason_proto_vecs: Optional[Dict[str, List[List[float]]]] = None
-
-    def _get_embedder(self):
-        return get_owner_embeddings(model="openai/text-embedding-3-small")
-
-    async def warm(self, api_key: Optional[str] = None):
-        if self._sent_proto_vecs is not None:
-            return
-
-        emb = self._get_embedder()
-
-        self._sent_proto_vecs = {}
-        for k, texts in SENTIMENT_PROTOTYPES.items():
-            self._sent_proto_vecs[k] = [await emb.aembed_query(t) for t in texts]
-
-        self._reason_proto_vecs = {}
-        for k, texts in REASON_PROTOTYPES.items():
-            self._reason_proto_vecs[k] = [await emb.aembed_query(t) for t in texts]
-
-    def _override_sentiment(self, text: str) -> Optional[Tuple[str, str]]:
-        t = text or ""
-        if _POS_CUES.search(t) and not _NEG_CUES.search(t):
-            return ("positive", "positive_cues")
-        if _PROFANITY.search(t) and not _POS_CUES.search(t):
-            return ("negative", "profanity")
-        if _NEG_CUES.search(t) and not _POS_CUES.search(t):
-            return ("negative", "negative_cues")
-        return None
-
-    async def classify_embeddings(
-        self,
-        text: str,
-        openrouter_api_key: Optional[str] = None,
-        *,
-        sent_threshold: float = 0.24,
-        reason_threshold: float = 0.32,
-    ) -> RouterResult:
-        await self.warm(openrouter_api_key)
-        assert self._sent_proto_vecs and self._reason_proto_vecs
-
-        emb = self._get_embedder()
-
-        t0 = time.perf_counter()
-        qv = await emb.aembed_query(text)
-
-        # Sentiment
-        s_label, s_score, s_top = _cosine_top(qv, self._sent_proto_vecs, topn=3)
-
-        override = None
-        ov = self._override_sentiment(text)
-        if ov:
-            s_label, override = ov[0], ov[1]
-            s_score = max(s_score, 0.60)
-
-        sentiment = LabelScore(label=s_label, score=float(s_score), top=s_top)
-
-        # Reason
-        reason = None
-        if s_label == "negative" or (s_label == "neutral" and s_score < 0.55):
-            r_label, r_score, r_top = _cosine_top(qv, self._reason_proto_vecs, topn=3)
-            if r_score >= reason_threshold:
-                reason = LabelScore(label=r_label, score=float(r_score), top=r_top)
-            else:
-                reason = LabelScore(label="unknown", score=float(r_score), top=r_top)
-
-        dt = (time.perf_counter() - t0) * 1000
-        return RouterResult(
-            backend="embeddings",
-            sentiment=sentiment,
-            reason=reason,
-            override=override,
-            meta={"latency_ms": round(dt, 2)},
-        )
-
-    async def classify_llm_glm47(
-        self, text: str, *, openrouter_api_key: Optional[str] = None
-    ) -> RouterResult:
-        llm = get_llm(
-            model_name="z-ai/glm-4.7",
-            openrouter_api_key=openrouter_api_key,
-        )
-
-        parser = JsonOutputParser()
-        classification_template = prompt_manager.get_template("router", "classification_prompt")
-        prompt = ChatPromptTemplate.from_messages(
-            [
-                ("system", "You are a strict classifier. Return ONLY JSON."),
-                ("human", classification_template),
-            ],
-            template_format="jinja2",
-        )
-        chain = prompt | llm | parser
-        out = await chain.ainvoke({"text": text})
-
-        sent = out.get("sentiment") or {}
-        rea = out.get("reason") or {}
-
-        return RouterResult(
-            backend="llm_glm_4.7",
-            sentiment=LabelScore(
-                label=str(sent.get("label", "unknown")), score=float(sent.get("score", 0.0))
-            ),
-            reason=LabelScore(
-                label=str(rea.get("label", "unknown")), score=float(rea.get("score", 0.0))
-            ),
-            meta={"rationale": out.get("rationale")},
-        )
-
-    async def classify(
-        self, text: str, openrouter_api_key: Optional[str] = None, mode: Optional[str] = None
-    ) -> RouterResult:
-        # Default behavior
-        return await self.classify_hybrid(text, openrouter_api_key=openrouter_api_key)
-
-    async def classify_hybrid(
-        self, text: str, *, openrouter_api_key: Optional[str] = None
-    ) -> RouterResult:
-        emb = await self.classify_embeddings(text, openrouter_api_key=openrouter_api_key)
-
-        s = emb.sentiment
-        need_llm = (s.score < 0.55) or (
-            s.label == "neutral" and (emb.reason and emb.reason.label == "unknown")
-        )
-
-        if not need_llm:
-            emb.backend = "hybrid"  # type: ignore
-            emb.meta["selected"] = "embeddings"
-            return emb
-
-        llm = await self.classify_llm_glm47(text, openrouter_api_key=openrouter_api_key)
-        llm.backend = "hybrid"  # type: ignore
-        llm.meta["selected"] = "llm_glm_4.7"
-        return llm
-
-    async def compare(self, text: str, openrouter_api_key: Optional[str] = None) -> Any:
-        # Debug tool to run both
-        e = await self.classify_embeddings(text, openrouter_api_key=openrouter_api_key)
-        llm_result = await self.classify_llm_glm47(text, openrouter_api_key=openrouter_api_key)
-        return {"embeddings": e, "llm": llm_result}
diff --git a/backend/src/agent_service/router/worker.py b/backend/src/agent_service/router/worker.py
deleted file mode 100644
index 1d740f3..0000000
--- a/backend/src/agent_service/router/worker.py
+++ /dev/null
@@ -1,98 +0,0 @@
-from __future__ import annotations
-
-import asyncio
-import logging
-
-import asyncpg
-from redis.asyncio import Redis
-
-from src.agent_service.core.config import POSTGRES_DSN, REDIS_URL
-from src.common.milvus_mgr import milvus_mgr
-
-from .service import RouterService
-
-log = logging.getLogger("router_worker")
-
-JOBS_STREAM = "router:jobs"
-GROUP = "router_group"
-CONSUMER = "router_1"
-
-_UPDATE_ROUTER_SQL = """
-UPDATE eval_traces SET
-    router_backend         = $1,
-    router_sentiment       = $2,
-    router_sentiment_score = $3,
-    router_reason          = $4,
-    router_reason_score    = $5,
-    router_override        = $6,
-    updated_at             = NOW()
-WHERE trace_id = $7
-"""
-
-
-async def ensure_group(r: Redis):
-    try:
-        await r.xgroup_create(JOBS_STREAM, GROUP, id="0-0", mkstream=True)
-    except Exception:
-        pass
-
-
-async def run_worker():
-    await milvus_mgr.aconnect()
-    log.info("Router worker: Milvus connected.")
-
-    pool: asyncpg.Pool | None = None
-    if POSTGRES_DSN:
-        pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=1, max_size=5, command_timeout=30)
-        log.info("Router worker: PostgreSQL pool connected.")
-    else:
-        log.warning("Router worker: POSTGRES_DSN not set; router result persistence disabled.")
-
-    r = Redis.from_url(REDIS_URL, decode_responses=True)
-    await ensure_group(r)
-
-    router = RouterService()
-
-    while True:
-        try:
-            resp = await r.xreadgroup(
-                groupname=GROUP,
-                consumername=CONSUMER,
-                streams={JOBS_STREAM: ">"},
-                count=25,
-                block=15000,
-            )
-            if not resp:
-                continue
-
-            for _stream, entries in resp:
-                for msg_id, fields in entries:
-                    try:
-                        trace_id = fields.get("trace_id")
-                        text = fields.get("text") or ""
-                        result = await router.classify_embeddings(text)
-
-                        if pool and trace_id:
-                            await pool.execute(
-                                _UPDATE_ROUTER_SQL,
-                                result.backend,
-                                result.sentiment.label,
-                                float(result.sentiment.score),
-                                (result.reason.label if result.reason else None),
-                                (float(result.reason.score) if result.reason else None),
-                                result.override,
-                                trace_id,
-                            )
-
-                        await r.xack(JOBS_STREAM, GROUP, msg_id)
-                    except Exception as e:
-                        log.error("job failed: %s", e)
-                        # don't ack -> will be pending; handle with XAUTOCLAIM later
-        except Exception as e:
-            log.error("worker loop error: %s", e)
-            await asyncio.sleep(1)
-
-
-if __name__ == "__main__":
-    logging.basicConfig(level=logging.INFO)
-    asyncio.run(run_worker())
```

### Frontend: Content fixes + dead files + stale comments
```diff
diff --git a/Chatbot UI and Admin Console/src/components/PrototypeDisclaimer.tsx b/Chatbot UI and Admin Console/src/components/PrototypeDisclaimer.tsx
index aa64a36..8a3c820 100644
--- a/Chatbot UI and Admin Console/src/components/PrototypeDisclaimer.tsx	
+++ b/Chatbot UI and Admin Console/src/components/PrototypeDisclaimer.tsx	
@@ -19,8 +19,9 @@ export function PrototypeDisclaimer() {
     const [open, setOpen] = useState(false)
 
     useEffect(() => {
-        // Open immediately on mount to ensure it shows every time (even on refresh)
-        setOpen(true)
+        if (!localStorage.getItem(DISCLAIMER_ACCEPTED_KEY)) {
+            setOpen(true)
+        }
     }, [])
 
     const handleAccept = () => {
diff --git a/Chatbot UI and Admin Console/src/features/admin/api/admin.ts b/Chatbot UI and Admin Console/src/features/admin/api/admin.ts
index bd50f8f..c013b27 100644
--- a/Chatbot UI and Admin Console/src/features/admin/api/admin.ts	
+++ b/Chatbot UI and Admin Console/src/features/admin/api/admin.ts	
@@ -1,6 +1,8 @@
-// ── Barrel re-export ─────────────────────────────────────────────────────────
-// All existing imports from '@features/admin/api/admin' continue to work.
-// New code should import from the domain module directly.
+/**
+ * @deprecated This barrel file is a backward-compatibility shim.
+ * New code should import from the domain module directly
+ * (e.g. `@features/admin/api/faqs`, `@features/admin/api/traces`, etc.).
+ */
 
 export * from './faqs'
 export * from './guardrails'
diff --git a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/GlobalTraceSheet.tsx b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/GlobalTraceSheet.tsx
index 118f1fd..856f8af 100644
--- a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/GlobalTraceSheet.tsx	
+++ b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/GlobalTraceSheet.tsx	
@@ -1,4 +1,3 @@
-// src/app/components/admin/trace/GlobalTraceSheet.tsx
 import { useEffect, useState } from 'react'
 import { Link, useSearchParams } from 'react-router'
 import { useQuery } from '@tanstack/react-query'
diff --git a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/JsonViewer.tsx b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/JsonViewer.tsx
index 6babd6f..874704e 100644
--- a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/JsonViewer.tsx	
+++ b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/JsonViewer.tsx	
@@ -1,4 +1,3 @@
-// src/app/components/admin/trace/JsonViewer.tsx
 import { useState } from 'react'
 import { ChevronRight } from 'lucide-react'
 
diff --git a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/TraceInspector.tsx b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/TraceInspector.tsx
index d16e631..dcaccaf 100644
--- a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/TraceInspector.tsx	
+++ b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/TraceInspector.tsx	
@@ -1,4 +1,3 @@
-// src/app/components/admin/trace/TraceInspector.tsx
 import { useState } from 'react'
 import type { ReactNode } from 'react'
 import {
diff --git a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/TraceTree.tsx b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/TraceTree.tsx
index 73c955f..603fa9d 100644
--- a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/TraceTree.tsx	
+++ b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/TraceTree.tsx	
@@ -1,4 +1,3 @@
-// src/app/components/admin/trace/TraceTree.tsx
 import { ArrowLeft, CheckCircle2, Eye, ChevronRight } from 'lucide-react'
 import { Skeleton } from '@components/ui/skeleton'
 import { getNodeIcon, getNodeChipClasses, getBarColor } from './nodeUtils'
diff --git a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/nodeUtils.tsx b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/nodeUtils.tsx
index d4a5bba..45ab4ae 100644
--- a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/nodeUtils.tsx	
+++ b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/nodeUtils.tsx	
@@ -1,4 +1,3 @@
-// src/app/components/admin/trace/nodeUtils.tsx
 import React from 'react'
 import { Brain, Link2, Bot, Code, Wrench, GitBranch } from 'lucide-react'
 import type { AggNodeType } from './types'
diff --git a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/parse.ts b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/parse.ts
index ff61368..f17695f 100644
--- a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/parse.ts	
+++ b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/parse.ts	
@@ -1,4 +1,3 @@
-// src/app/components/admin/trace/parse.ts
 import type { FlatNode, TraceDetail, TraceEvent } from './types'
 
 type SegmentKind = 'llm' | 'parser' | 'tool'
diff --git a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/types.ts b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/types.ts
index bf9cd8f..d40101d 100644
--- a/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/types.ts	
+++ b/Chatbot UI and Admin Console/src/features/admin/traces/trace-viewer/types.ts	
@@ -1,4 +1,3 @@
-// src/app/components/admin/trace/types.ts
 export type AggNodeType = 'trace' | 'chain' | 'llm' | 'parser' | 'tool'
 
 export type NodeStatus = 'success' | 'error' | 'pending'
diff --git a/Chatbot UI and Admin Console/src/features/chat/pages/landing-data.ts b/Chatbot UI and Admin Console/src/features/chat/pages/landing-data.ts
index 830814c..f29466c 100644
--- a/Chatbot UI and Admin Console/src/features/chat/pages/landing-data.ts	
+++ b/Chatbot UI and Admin Console/src/features/chat/pages/landing-data.ts	
@@ -60,7 +60,7 @@ export const FEATURES = [
   {
     icon: '🔒',
     title: 'Bank-Grade Security',
-    desc: '256-bit encryption and Non-RBI-compliant data handling keeps your information safe.',
+    desc: '256-bit encryption and RBI-compliant data handling keeps your information safe.',
   },
   {
     icon: '📱',
diff --git a/Chatbot UI and Admin Console/src/styles/fonts.css b/Chatbot UI and Admin Console/src/styles/fonts.css
deleted file mode 100644
index e69de29..0000000
diff --git a/Chatbot UI and Admin Console/src/styles/index.css b/Chatbot UI and Admin Console/src/styles/index.css
index c4ed6eb..58f4c52 100644
--- a/Chatbot UI and Admin Console/src/styles/index.css	
+++ b/Chatbot UI and Admin Console/src/styles/index.css	
@@ -1,4 +1,3 @@
-@import "./fonts.css";
 @import "./tailwind.css";
 @import "./theme.css";
 @import "./chat-widget.css";
```

### Frontend: Deleted unreferenced barrel files
```diff
diff --git a/Chatbot UI and Admin Console/src/components/index.ts b/Chatbot UI and Admin Console/src/components/index.ts
deleted file mode 100644
index dee1452..0000000
--- a/Chatbot UI and Admin Console/src/components/index.ts	
+++ /dev/null
@@ -1,3 +0,0 @@
-export { ImageWithFallback } from './ImageWithFallback'
-export { PrototypeDisclaimer } from './PrototypeDisclaimer'
-export { RouteErrorBoundary } from './RouteErrorBoundary'
diff --git a/Chatbot UI and Admin Console/src/shared/api/index.ts b/Chatbot UI and Admin Console/src/shared/api/index.ts
deleted file mode 100644
index ae08aa3..0000000
--- a/Chatbot UI and Admin Console/src/shared/api/index.ts	
+++ /dev/null
@@ -1,4 +0,0 @@
-export { API_BASE_URL, RUNTIME_CONFIG, ApiError, requestJson, withAdminHeaders } from './http'
-export { streamSse } from './sse'
-export { fetchSessionConfig, saveSessionConfig } from './sessions'
-export type { SessionConfig } from './sessions'
diff --git a/Chatbot UI and Admin Console/src/shared/hooks/index.ts b/Chatbot UI and Admin Console/src/shared/hooks/index.ts
deleted file mode 100644
index 33f4b6d..0000000
--- a/Chatbot UI and Admin Console/src/shared/hooks/index.ts	
+++ /dev/null
@@ -1 +0,0 @@
-export { useAvailableModels } from './useModels'
diff --git a/Chatbot UI and Admin Console/src/shared/lib/index.ts b/Chatbot UI and Admin Console/src/shared/lib/index.ts
deleted file mode 100644
index d902c24..0000000
--- a/Chatbot UI and Admin Console/src/shared/lib/index.ts	
+++ /dev/null
@@ -1,10 +0,0 @@
-export { formatCurrency, formatDateTime } from './format'
-export { copyToClipboard, tableElementToMarkdown } from './clipboard'
-export type { CopyPayloadKind, ClipboardCopyResult } from './clipboard'
-export { parseMaybeJson } from './json'
-export {
-  buildConversationHref,
-  buildTraceHref,
-  clearTraceIdSearchParams,
-  setTraceIdSearchParams,
-} from './navigation'
diff --git a/Chatbot UI and Admin Console/src/shared/types/index.ts b/Chatbot UI and Admin Console/src/shared/types/index.ts
deleted file mode 100644
index 90c0f03..0000000
--- a/Chatbot UI and Admin Console/src/shared/types/index.ts	
+++ /dev/null
@@ -1 +0,0 @@
-export type { ChatMessage, MessageRole, MessageStatus, ToolCallEvent, CostEvent } from './chat'
```

### Frontend: Deduplicated provider-key logic → shared/lib/provider-keys.ts
```diff
diff --git a/Chatbot UI and Admin Console/src/features/admin/pages/ModelConfig.tsx b/Chatbot UI and Admin Console/src/features/admin/pages/ModelConfig.tsx
index 40c480a..43e76cf 100644
--- a/Chatbot UI and Admin Console/src/features/admin/pages/ModelConfig.tsx	
+++ b/Chatbot UI and Admin Console/src/features/admin/pages/ModelConfig.tsx	
@@ -5,7 +5,6 @@ import {
   fetchSessionConfig,
   saveSessionConfig,
   type AgentModel,
-  type SessionConfig,
 } from '@features/admin/api/admin'
 import { useAvailableModels } from '../../../shared/hooks/useModels'
 import { useAdminContext } from '@features/admin/context/AdminContext'
@@ -20,17 +19,7 @@ import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@
 import { Cpu, Save, Search, Server, Sparkles } from 'lucide-react'
 import { KeyInput } from '@components/ui/key-input'
 import { MobileHeader } from '@components/ui/mobile-header'
-
-function providerRequiresSessionKey(provider: string) {
-  return provider === 'openrouter' || provider === 'nvidia'
-}
-
-function hasSavedProviderKey(provider: string, sessionCfg?: SessionConfig) {
-  if (provider === 'openrouter') return !!sessionCfg?.has_openrouter_key
-  if (provider === 'nvidia') return !!sessionCfg?.has_nvidia_key
-  if (provider === 'groq') return !!sessionCfg?.has_groq_key
-  return false
-}
+import { providerRequiresSessionKey, hasSavedProviderKey } from '@shared/lib/provider-keys'
 
 function hasAdminProviderKey(
   provider: string,
diff --git a/Chatbot UI and Admin Console/src/features/chat/components/ChatWidget.tsx b/Chatbot UI and Admin Console/src/features/chat/components/ChatWidget.tsx
index 62427ad..38544a0 100644
--- a/Chatbot UI and Admin Console/src/features/chat/components/ChatWidget.tsx	
+++ b/Chatbot UI and Admin Console/src/features/chat/components/ChatWidget.tsx	
@@ -21,10 +21,11 @@ import { toast } from 'sonner'
 import { ChatMessage } from './ChatMessage'
 import { ChatInput } from './ChatInput'
 import { useChatStream } from '@features/chat/hooks/useChatStream'
-import { fetchSessionConfig, saveSessionConfig, type SessionConfig } from '@shared/api/sessions'
+import { fetchSessionConfig, saveSessionConfig } from '@shared/api/sessions'
 import type { AgentModel } from '@features/admin/api/health'
 import { useAvailableModels } from '@shared/hooks/useModels'
 import { cn } from '@components/ui/utils'
+import { providerRequiresSessionKey, hasSavedProviderKey } from '@shared/lib/provider-keys'
 
 const PUBLIC_PROMPTS = [
   {
@@ -67,17 +68,6 @@ const AUTHENTICATED_PROMPTS = [
 const DEFAULT_CHAT_PROVIDER = 'groq'
 const DEFAULT_CHAT_MODEL = 'openai/gpt-oss-120b'
 
-function providerRequiresSessionKey(provider: string) {
-  return provider === 'openrouter' || provider === 'nvidia'
-}
-
-function hasSavedProviderKey(provider: string, sessionCfg?: SessionConfig) {
-  if (provider === 'openrouter') return !!sessionCfg?.has_openrouter_key
-  if (provider === 'nvidia') return !!sessionCfg?.has_nvidia_key
-  if (provider === 'groq') return !!sessionCfg?.has_groq_key
-  return false
-}
-
 function providerKeyHeading(provider: string) {
   if (provider === 'openrouter') return 'OpenRouter Key (Required)'
   if (provider === 'nvidia') return 'NVIDIA Key (Required)'
diff --git a/Chatbot UI and Admin Console/src/shared/lib/provider-keys.ts b/Chatbot UI and Admin Console/src/shared/lib/provider-keys.ts
new file mode 100644
index 0000000..1045bff
--- /dev/null
+++ b/Chatbot UI and Admin Console/src/shared/lib/provider-keys.ts	
@@ -0,0 +1,23 @@
+import type { SessionConfig } from '@shared/api/sessions'
+
+/**
+ * Returns `true` when the given provider requires the user to supply a
+ * session-level API key before inference can proceed.
+ */
+export function providerRequiresSessionKey(provider: string): boolean {
+  return provider === 'openrouter' || provider === 'nvidia'
+}
+
+/**
+ * Checks whether the backend already stores a provider key for the given
+ * provider within the supplied session config.
+ */
+export function hasSavedProviderKey(
+  provider: string,
+  sessionCfg?: SessionConfig,
+): boolean {
+  if (provider === 'openrouter') return !!sessionCfg?.has_openrouter_key
+  if (provider === 'nvidia') return !!sessionCfg?.has_nvidia_key
+  if (provider === 'groq') return !!sessionCfg?.has_groq_key
+  return false
+}
```

---

<a id="commit-3"></a>
## Commit 3: .editorconfig (`f46787a`)
```diff
diff --git a/.editorconfig b/.editorconfig
new file mode 100644
index 0000000..d51074b
--- /dev/null
+++ b/.editorconfig
@@ -0,0 +1,21 @@
+# EditorConfig — enforces consistent formatting across all editors and tools
+# https://editorconfig.org
+
+root = true
+
+[*]
+end_of_line = lf
+insert_final_newline = true
+trim_trailing_whitespace = true
+charset = utf-8
+
+[*.{py,pyi}]
+indent_style = space
+indent_size = 4
+
+[*.{ts,tsx,js,jsx,json,css,yaml,yml,toml,md}]
+indent_style = space
+indent_size = 2
+
+[Makefile]
+indent_style = tab
```
