import os
from typing import Final

# --- SERVER SETTINGS ---
SERVER_NAME = "mock_fintech"
SERVER_URL = os.getenv("MCP_SERVER_URL", "http://0.0.0.0:8050/sse")
PORT = int(os.getenv("PORT", "8000"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# --- EXTERNAL SERVICES ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CRM_BASE_URL = os.getenv("CRM_BASE_URL", "http://localhost:8080").rstrip("/")
DOWNLOAD_TOKEN_REDIS_PREFIX = "dl_token:"
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "").strip()
POSTGRES_POOL_MIN = int(os.getenv("POSTGRES_POOL_MIN", "10"))
POSTGRES_POOL_MAX = int(os.getenv("POSTGRES_POOL_MAX", "50"))

# =============================================================================
# MILVUS VECTOR STORE
# =============================================================================
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530").strip()
# Optional — set for Zilliz Cloud (cloud.zilliz.com). Leave empty for self-hosted.
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN", "").strip() or None

# --- LOGIC SETTINGS ---
# LangGraph history limit
KEEP_LAST = int(os.getenv("KEEP_LAST_MESSAGES", "20"))

# --- PROVIDER CONSTANTS (BASE URLS) ---
# These are architectural constants, not secrets.
GROQ_BASE_URL = "https://api.groq.com"
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# --- SERVER-SIDE KEYS (OPTIONAL FALLBACKS) ---
# In BYOK mode, these are typically None.
# We define them here so imports in other modules do not crash.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

# Groq support for multiple keys (Load Balancing)
_groq_env = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))
GROQ_API_KEYS = [k.strip() for k in _groq_env.split(",") if k.strip()]

# Optional OpenRouter Branding
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "Enterprise Agent")

# --- EMBEDDINGS ---
# Default embedding model used across the platform.
# Must match the Milvus vector index dimensions (1536).
OPENROUTER_EMBED_MODEL_DEFAULT = os.getenv(
    "OPENROUTER_EMBED_MODEL_DEFAULT", "openai/text-embedding-3-small"
).strip()

# --- MODEL DEFAULTS ---
DEFAULT_CHAT_PROVIDER = os.getenv("DEFAULT_CHAT_PROVIDER", "groq").strip().lower()
DEFAULT_CHAT_MODEL = os.getenv(
    "DEFAULT_CHAT_MODEL", os.getenv("MODEL", "openai/gpt-oss-120b")
).strip()
MODEL_NAME = DEFAULT_CHAT_MODEL

# --- NBFC ROUTER CONFIGURATION ---
NBFC_ROUTER_ENABLED = os.getenv("NBFC_ROUTER_ENABLED", "true").lower() in ("1", "true", "yes", "y")
NBFC_ROUTER_MODE = os.getenv("NBFC_ROUTER_MODE", "hybrid").strip().lower()
NBFC_ROUTER_CHAT_MODEL = os.getenv("NBFC_ROUTER_CHAT_MODEL", "z-ai/glm-4.7").strip()
NBFC_ROUTER_EMBED_MODEL = os.getenv(
    "NBFC_ROUTER_EMBED_MODEL", OPENROUTER_EMBED_MODEL_DEFAULT
).strip()
NBFC_ROUTER_CACHE_DIR = os.getenv("NBFC_ROUTER_CACHE_DIR", ".cache_nbfc_router").strip()

# Router Thresholds (Tuned for production)
NBFC_ROUTER_SENTIMENT_THRESHOLD = float(os.getenv("NBFC_ROUTER_SENTIMENT_THRESHOLD", "0.26"))
NBFC_ROUTER_SENTIMENT_MARGIN = float(os.getenv("NBFC_ROUTER_SENTIMENT_MARGIN", "0.03"))
NBFC_ROUTER_REASON_UNKNOWN_GATE = float(os.getenv("NBFC_ROUTER_REASON_UNKNOWN_GATE", "0.30"))
NBFC_ROUTER_REASON_MARGIN = float(os.getenv("NBFC_ROUTER_REASON_MARGIN", "0.03"))
NBFC_ROUTER_FALLBACK_SENTIMENT_SCORE = float(
    os.getenv("NBFC_ROUTER_FALLBACK_SENTIMENT_SCORE", "0.33")
)
NBFC_ROUTER_FALLBACK_REASON_SCORE = float(os.getenv("NBFC_ROUTER_FALLBACK_REASON_SCORE", "0.60"))
NBFC_ROUTER_ANSWERABILITY_ENABLED = os.getenv(
    "NBFC_ROUTER_ANSWERABILITY_ENABLED", "true"
).lower() in ("1", "true", "yes", "y")
NBFC_ROUTER_ANSWERABILITY_KB_THRESHOLD = float(
    os.getenv("NBFC_ROUTER_ANSWERABILITY_KB_THRESHOLD", "0.58")
)
NBFC_ROUTER_ANSWERABILITY_KB_HEURISTIC_THRESHOLD = float(
    os.getenv("NBFC_ROUTER_ANSWERABILITY_KB_HEURISTIC_THRESHOLD", "0.38")
)
NBFC_ROUTER_ANSWERABILITY_MCP_THRESHOLD = float(
    os.getenv("NBFC_ROUTER_ANSWERABILITY_MCP_THRESHOLD", "0.52")
)
NBFC_ROUTER_ANSWERABILITY_MARGIN = float(os.getenv("NBFC_ROUTER_ANSWERABILITY_MARGIN", "0.04"))
NBFC_ROUTER_ANSWERABILITY_MAX_TOOLS = int(os.getenv("NBFC_ROUTER_ANSWERABILITY_MAX_TOOLS", "60"))
NBFC_ROUTER_ANSWERABILITY_VECTOR_CACHE_SIZE = int(
    os.getenv("NBFC_ROUTER_ANSWERABILITY_VECTOR_CACHE_SIZE", "64")
)

# Agent/Router Separation
AGENT_INLINE_ROUTER_ENABLED = os.getenv("AGENT_INLINE_ROUTER_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)
AGENT_INLINE_ROUTER_EXPOSE = os.getenv("AGENT_INLINE_ROUTER_EXPOSE", "false").lower() in (
    "1",
    "true",
    "yes",
)

# Streaming Contract Controls
AGENT_STREAM_EXPOSE_INTERNAL_EVENTS = os.getenv(
    "AGENT_STREAM_EXPOSE_INTERNAL_EVENTS", "false"
).lower() in ("1", "true", "yes")
AGENT_STREAM_EXPOSE_REASONING = os.getenv("AGENT_STREAM_EXPOSE_REASONING", "true").lower() in (
    "1",
    "true",
    "yes",
)
ADMIN_CURSOR_APIS_V2 = os.getenv("ADMIN_CURSOR_APIS_V2", "true").lower() in ("1", "true", "yes")

# --- JUDGE CONFIGURATION ---
JUDGE_MODEL_NAME = os.getenv("JUDGE_MODEL_NAME", "openai/gpt-4o")
ENABLE_LLM_JUDGE = os.getenv("ENABLE_LLM_JUDGE", "true").lower() in ("1", "true", "yes")

# =============================================================================
# RATE LIMITING CONFIGURATION (Production-Grade)
# =============================================================================

# Enable/Disable rate limiting globally
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")

# Rate limiting algorithm: "sliding_window" (smooth) or "token_bucket" (bursty)
RATE_LIMIT_ALGORITHM = os.getenv("RATE_LIMIT_ALGORITHM", "sliding_window").strip().lower()

# Failure mode: "fail_open" (allow on Redis failure) or "fail_closed" (deny on Redis failure)
# Default: fail_closed — denies requests when Redis is unreachable to protect LLM API budgets.
# Set RATE_LIMIT_FAILURE_MODE=fail_open explicitly if availability is preferred over safety.
RATE_LIMIT_FAILURE_MODE = os.getenv("RATE_LIMIT_FAILURE_MODE", "fail_closed").strip().lower()

# Redis timeout for rate limit operations (seconds)
RATE_LIMIT_REDIS_TIMEOUT = float(os.getenv("RATE_LIMIT_REDIS_TIMEOUT", "1.0"))

# --- Per-Endpoint Rate Limits (requests per second) ---
# Global default for all endpoints
RATE_LIMIT_DEFAULT_RPS = float(os.getenv("RATE_LIMIT_DEFAULT_RPS", "10.0"))

# Agent streaming endpoint (most critical)
RATE_LIMIT_AGENT_STREAM_RPS = float(os.getenv("RATE_LIMIT_AGENT_STREAM_RPS", "5.0"))

# Agent query endpoint
RATE_LIMIT_AGENT_QUERY_RPS = float(os.getenv("RATE_LIMIT_AGENT_QUERY_RPS", "10.0"))

# Follow-up suggestions
RATE_LIMIT_FOLLOW_UP_RPS = float(os.getenv("RATE_LIMIT_FOLLOW_UP_RPS", "20.0"))

# Session management
RATE_LIMIT_SESSION_RPS = float(os.getenv("RATE_LIMIT_SESSION_RPS", "30.0"))

# Model listing (can be higher - read-only)
RATE_LIMIT_MODELS_RPS = float(os.getenv("RATE_LIMIT_MODELS_RPS", "100.0"))

# Health checks (should be very high or unlimited)
RATE_LIMIT_HEALTH_RPS = float(os.getenv("RATE_LIMIT_HEALTH_RPS", "1000.0"))

# Admin auth — login and MFA verify (brute-force protection, fail-closed).
# 5 requests per minute ≈ 0.083 rps per-IP. Plan 2026-04-10 §D17/D18.
RATE_LIMIT_ADMIN_AUTH_LOGIN_RPS = float(os.getenv("RATE_LIMIT_ADMIN_AUTH_LOGIN_RPS", "0.083"))
RATE_LIMIT_ADMIN_AUTH_MFA_RPS = float(os.getenv("RATE_LIMIT_ADMIN_AUTH_MFA_RPS", "0.083"))

# --- Per-User/Tenant Rate Limits ---
# Free tier users
RATE_LIMIT_FREE_TIER_RPS = float(os.getenv("RATE_LIMIT_FREE_TIER_RPS", "1.0"))

# Premium users
RATE_LIMIT_PREMIUM_TIER_RPS = float(os.getenv("RATE_LIMIT_PREMIUM_TIER_RPS", "50.0"))

# Admin users (very high limit)
RATE_LIMIT_ADMIN_TIER_RPS = float(os.getenv("RATE_LIMIT_ADMIN_TIER_RPS", "500.0"))

# --- Burst Control (Token Bucket Only) ---
# Maximum burst size for token bucket algorithm
RATE_LIMIT_MAX_BURST = int(os.getenv("RATE_LIMIT_MAX_BURST", "20"))

# --- Advanced Settings ---
# Enable detailed metrics collection
RATE_LIMIT_ENABLE_METRICS = os.getenv("RATE_LIMIT_ENABLE_METRICS", "true").lower() == "true"

# Key prefix for Redis keys (for namespace isolation)
RATE_LIMIT_KEY_PREFIX = os.getenv("RATE_LIMIT_KEY_PREFIX", "ratelimit")

# Per-IP rate limiting (in addition to per-user)
RATE_LIMIT_PER_IP_ENABLED = os.getenv("RATE_LIMIT_PER_IP_ENABLED", "true").lower() == "true"
RATE_LIMIT_PER_IP_RPS = float(os.getenv("RATE_LIMIT_PER_IP_RPS", "100.0"))

# =============================================================================
# REDIS CONNECTION POOL
# =============================================================================
REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
REDIS_HEALTH_CHECK_INTERVAL = int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30"))

# =============================================================================
# SECURITY HARDENING & TOR BLOCKING
# =============================================================================
SECURITY_ENABLED = os.getenv("SECURITY_ENABLED", "true").lower() in ("1", "true", "yes")
SECURITY_TRUST_PROXY_HEADERS = os.getenv("SECURITY_TRUST_PROXY_HEADERS", "false").lower() in (
    "1",
    "true",
    "yes",
)
SECURITY_PREFER_IP_HEADER = os.getenv("SECURITY_PREFER_IP_HEADER", "").strip().lower() or None

SECURITY_CRITICAL_PATHS = tuple(
    p.strip()
    for p in os.getenv("SECURITY_CRITICAL_PATHS", "/agent,/graphql,/eval").split(",")
    if p.strip()
)
SECURITY_MONITORED_PATHS = tuple(
    p.strip()
    for p in os.getenv("SECURITY_MONITORED_PATHS", "/health,/metrics").split(",")
    if p.strip()
)

TOR_REFRESH_SECONDS = int(os.getenv("TOR_REFRESH_SECONDS", "1800"))
TOR_STALE_AFTER_SECONDS = int(os.getenv("TOR_STALE_AFTER_SECONDS", "7200"))
TOR_NEGATIVE_CACHE_TTL_SECONDS = int(os.getenv("TOR_NEGATIVE_CACHE_TTL_SECONDS", "300"))
TOR_NEGATIVE_CACHE_CLEANUP_INTERVAL = int(os.getenv("TOR_NEGATIVE_CACHE_CLEANUP_INTERVAL", "1000"))

SECURITY_IMPOSSIBLE_TRAVEL_KMH = float(os.getenv("SECURITY_IMPOSSIBLE_TRAVEL_KMH", "900.0"))
SECURITY_CONCURRENT_IP_WINDOW_SECONDS = int(
    os.getenv("SECURITY_CONCURRENT_IP_WINDOW_SECONDS", "300")
)
SECURITY_CONCURRENT_IP_THRESHOLD = int(os.getenv("SECURITY_CONCURRENT_IP_THRESHOLD", "3"))

SECURITY_RISK_IMPOSSIBLE_TRAVEL = float(os.getenv("SECURITY_RISK_IMPOSSIBLE_TRAVEL", "0.6"))
SECURITY_RISK_CONCURRENT_IP = float(os.getenv("SECURITY_RISK_CONCURRENT_IP", "0.5"))
SECURITY_RISK_DEVICE_MISMATCH = float(os.getenv("SECURITY_RISK_DEVICE_MISMATCH", "0.4"))
SECURITY_RISK_GEO_ANOMALY = float(os.getenv("SECURITY_RISK_GEO_ANOMALY", "0.3"))
SECURITY_RISK_ALLOW_THRESHOLD = float(os.getenv("SECURITY_RISK_ALLOW_THRESHOLD", "0.4"))
SECURITY_RISK_STEP_UP_THRESHOLD = float(os.getenv("SECURITY_RISK_STEP_UP_THRESHOLD", "0.7"))

GEOIP_DB_PATH = os.getenv("GEOIP_DB_PATH", "").strip()
PROMETHEUS_METRICS_ENABLED = os.getenv("PROMETHEUS_METRICS_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)

# =============================================================================
# KNOWLEDGE BASE (FAQ INGEST)
# =============================================================================
KB_FAQ_BATCH_MAX_ITEMS = int(os.getenv("KB_FAQ_BATCH_MAX_ITEMS", "1000"))
KB_FAQ_PDF_MAX_BYTES = int(os.getenv("KB_FAQ_PDF_MAX_BYTES", str(10 * 1024 * 1024)))

# =============================================================================
# INLINE PROMPT GUARDRAILS
# =============================================================================
INLINE_GUARD_ENABLED = os.getenv("INLINE_GUARD_ENABLED", "true").lower() in ("1", "true", "yes")
INLINE_GUARD_TOTAL_TIMEOUT_MS = int(os.getenv("INLINE_GUARD_TOTAL_TIMEOUT_MS", "3200"))
INLINE_GUARD_GROQ_TIMEOUT_MS = int(os.getenv("INLINE_GUARD_GROQ_TIMEOUT_MS", "2200"))
INLINE_GUARD_GROQ_MODEL = os.getenv(
    "INLINE_GUARD_GROQ_MODEL", "openai/gpt-oss-safeguard-20b"
).strip()
GROQ_GUARD_BASE_URL = os.getenv("GROQ_GUARD_BASE_URL", "https://api.groq.com/openai/v1").strip()

# =============================================================================
# SHARED HTTP CLIENT (ASYNC)
# =============================================================================
SHARED_HTTP_MAX_CONNECTIONS = int(os.getenv("SHARED_HTTP_MAX_CONNECTIONS", "200"))
SHARED_HTTP_MAX_KEEPALIVE = int(os.getenv("SHARED_HTTP_MAX_KEEPALIVE", "50"))
SHARED_HTTP_TIMEOUT_CONNECT_SECONDS = float(os.getenv("SHARED_HTTP_TIMEOUT_CONNECT_SECONDS", "5.0"))
SHARED_HTTP_TIMEOUT_READ_SECONDS = float(os.getenv("SHARED_HTTP_TIMEOUT_READ_SECONDS", "30.0"))
SHARED_HTTP_TIMEOUT_WRITE_SECONDS = float(os.getenv("SHARED_HTTP_TIMEOUT_WRITE_SECONDS", "10.0"))
SHARED_HTTP_TIMEOUT_POOL_SECONDS = float(os.getenv("SHARED_HTTP_TIMEOUT_POOL_SECONDS", "5.0"))

# =============================================================================
# SHADOW TRACE QUEUE + WORKER
# =============================================================================
SHADOW_TRACE_QUEUE_KEY = os.getenv("SHADOW_TRACE_QUEUE_KEY", "agent:shadow:trace_queue").strip()
SHADOW_TRACE_QUEUE_MAXLEN = int(os.getenv("SHADOW_TRACE_QUEUE_MAXLEN", "50000"))
SHADOW_TRACE_DLQ_KEY = os.getenv("SHADOW_TRACE_DLQ_KEY", "agent:shadow:trace_dlq").strip()
SHADOW_TRACE_QUEUE_DLQ_MAXLEN = int(os.getenv("SHADOW_TRACE_QUEUE_DLQ_MAXLEN", "20000"))
SHADOW_TRACE_QUEUE_MAX_RETRIES = int(os.getenv("SHADOW_TRACE_QUEUE_MAX_RETRIES") or "3")
SHADOW_TRACE_QUEUE_PUSH_TIMEOUT_SECONDS = float(
    os.getenv("SHADOW_TRACE_QUEUE_PUSH_TIMEOUT_SECONDS", "0.25")
)
SHADOW_JUDGE_ENABLED = os.getenv("SHADOW_JUDGE_ENABLED", "true").lower() in ("1", "true", "yes")
SHADOW_JUDGE_POLL_SECONDS = int(os.getenv("SHADOW_JUDGE_POLL_SECONDS", "60"))
SHADOW_JUDGE_BATCH_SIZE = int(os.getenv("SHADOW_JUDGE_BATCH_SIZE", "50"))
SHADOW_JUDGE_MODEL = os.getenv("SHADOW_JUDGE_MODEL", "openai/gpt-oss-120b").strip()
SHADOW_JUDGE_MODEL_FALLBACK = os.getenv("SHADOW_JUDGE_MODEL_FALLBACK", "gpt-oss-120b").strip()
SHADOW_JUDGE_REASONING_EFFORT = os.getenv("SHADOW_JUDGE_REASONING_EFFORT", "medium").strip().lower()

# =============================================================================
# ADMIN AUTHENTICATION (JWT + TOTP + ARGON2ID — plan 2026-04-10, cutover 6h)
# =============================================================================
# JWT session cookie is the ONLY admin auth path. Legacy X-Admin-Key fallback
# and the ADMIN_AUTH_ENABLED feature flag were retired in Phase 6h. Env vars
# below are REQUIRED for the app to boot — enroll via
# `uv run python backend/scripts/enroll_super_admin.py`.

# Cookie settings — Secure flag must be True in prod; False only acceptable for local HTTP dev
ADMIN_AUTH_COOKIE_SECURE = os.getenv("ADMIN_AUTH_COOKIE_SECURE", "true").lower() in (
    "1",
    "true",
    "yes",
)
ADMIN_AUTH_COOKIE_NAME_ACCESS = os.getenv("ADMIN_AUTH_COOKIE_NAME_ACCESS", "mft_admin_at").strip()
ADMIN_AUTH_COOKIE_NAME_REFRESH = os.getenv("ADMIN_AUTH_COOKIE_NAME_REFRESH", "mft_admin_rt").strip()

# JWT settings — HS256 is intentional (single-issuer, single-verifier). Move to
# RS256+JWKS only when a second service needs to verify tokens.
#
# JWT_ALGORITHM is allowlisted at module import to block the classic 'alg=none'
# bypass and prevent algorithm-confusion if an operator misconfigures the env
# (e.g. setting RS256 while JWT_SECRET is still an HMAC string). The check runs
# unconditionally — NOT inside _validate_admin_auth_config(), which is bypassed
# in pytest contexts.
_ALLOWED_JWT_ALGORITHMS: Final[frozenset[str]] = frozenset({"HS256", "HS384", "HS512"})
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip()
if JWT_ALGORITHM not in _ALLOWED_JWT_ALGORITHMS:
    raise ValueError(
        f"JWT_ALGORITHM={JWT_ALGORITHM!r} is not in the allowed set "
        f"{sorted(_ALLOWED_JWT_ALGORITHMS)}. Asymmetric algorithms (RS256/ES256) "
        "require a separate JWKS verification path that this service does not implement."
    )
JWT_ISSUER = os.getenv("JWT_ISSUER", "mft-agent-service").strip()
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "mft-admin-console").strip()
JWT_ACCESS_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TTL_SECONDS", "900"))  # 15 min
JWT_REFRESH_TTL_SECONDS = int(os.getenv("JWT_REFRESH_TTL_SECONDS", "28800"))  # 8 hours
JWT_MFA_FRESHNESS_SECONDS = int(os.getenv("JWT_MFA_FRESHNESS_SECONDS", "300"))  # 5 min

# Secrets — required only when ADMIN_AUTH_ENABLED=True. See tasks/lessons.md L1:
# PyJWT 2.12.x enforces HS256 keys to be >=32 bytes (RFC 7518 §3.2) via InsecureKeyLengthWarning.
JWT_SECRET: str | None = os.getenv("JWT_SECRET") or None
FERNET_MASTER_KEY: str | None = os.getenv("FERNET_MASTER_KEY") or None

# Single super-admin identity — env-var seeded for prototype phase. When the user count
# grows beyond one, these scalars become a query against an admin_users Postgres table
# without any contract change in the JWT layer.
SUPER_ADMIN_EMAIL: str | None = os.getenv("SUPER_ADMIN_EMAIL") or None
SUPER_ADMIN_PASSWORD_HASH: str | None = os.getenv("SUPER_ADMIN_PASSWORD_HASH") or None  # argon2id
SUPER_ADMIN_TOTP_SECRET_ENC: str | None = (
    os.getenv("SUPER_ADMIN_TOTP_SECRET_ENC") or None
)  # Fernet-encrypted base32


def _validate_admin_auth_config() -> None:
    """Fail-closed validation — admin auth env vars are mandatory for app boot.

    Test contexts (pytest loaded in sys.modules) skip validation to allow fixtures
    to monkeypatch values after import. Production imports fail fast if any
    required value is missing, with a pointer at the enrollment script.
    """
    import sys

    if "pytest" in sys.modules:
        return
    missing: list[str] = []
    if not JWT_SECRET:
        missing.append("JWT_SECRET")
    elif len(JWT_SECRET.encode("utf-8")) < 32:
        raise ValueError(
            "JWT_SECRET must be >=32 bytes (RFC 7518 §3.2; PyJWT 2.12.x enforces "
            "via InsecureKeyLengthWarning). Generate one with: "
            'python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    if not FERNET_MASTER_KEY:
        missing.append("FERNET_MASTER_KEY")
    if not SUPER_ADMIN_EMAIL:
        missing.append("SUPER_ADMIN_EMAIL")
    if not SUPER_ADMIN_PASSWORD_HASH:
        missing.append("SUPER_ADMIN_PASSWORD_HASH")
    if not SUPER_ADMIN_TOTP_SECRET_ENC:
        missing.append("SUPER_ADMIN_TOTP_SECRET_ENC")
    if missing:
        raise ValueError(
            f"admin auth config missing required env vars: {', '.join(missing)}. "
            "Run `uv run python backend/scripts/enroll_super_admin.py` to generate them."
        )


_validate_admin_auth_config()
