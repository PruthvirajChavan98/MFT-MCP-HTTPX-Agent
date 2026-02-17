import os

# --- SERVER SETTINGS ---
SERVER_NAME = "mock_fintech"
SERVER_URL = os.getenv("MCP_SERVER_URL", "http://0.0.0.0:8050/sse")
PORT = int(os.getenv("PORT", "8000"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# --- EXTERNAL SERVICES ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

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
# Must match the Neo4j vector index dimensions (1536).
OPENROUTER_EMBED_MODEL_DEFAULT = os.getenv(
    "OPENROUTER_EMBED_MODEL_DEFAULT", "openai/text-embedding-3-small"
).strip()

# --- MODEL DEFAULTS ---
MODEL_NAME = os.getenv("MODEL", "openai/gpt-4o")

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

# --- JUDGE CONFIGURATION ---
JUDGE_MODEL_NAME = os.getenv("JUDGE_MODEL_NAME", "openai/gpt-4o")
ENABLE_LLM_JUDGE = os.getenv("ENABLE_LLM_JUDGE", "true").lower() == "true"

# =============================================================================
# RATE LIMITING CONFIGURATION (Production-Grade)
# =============================================================================

# Enable/Disable rate limiting globally
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")

# Rate limiting algorithm: "sliding_window" (smooth) or "token_bucket" (bursty)
RATE_LIMIT_ALGORITHM = os.getenv("RATE_LIMIT_ALGORITHM", "sliding_window").strip().lower()

# Failure mode: "fail_open" (allow on Redis failure) or "fail_closed" (deny on Redis failure)
RATE_LIMIT_FAILURE_MODE = os.getenv("RATE_LIMIT_FAILURE_MODE", "fail_open").strip().lower()

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
