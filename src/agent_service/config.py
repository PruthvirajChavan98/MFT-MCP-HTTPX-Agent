# ===== config.py =====
import os
import json
import itertools

# Server Settings
SERVER_NAME = "hero_fincorp"
SERVER_URL = os.getenv("MCP_SERVER_URL", "http://0.0.0.0:8050/sse")
PORT = int(os.getenv("PORT", "8000"))

# Logic Settings
KEEP_LAST = int(os.getenv("KEEP_LAST_MESSAGES", "20"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# External Services
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- GROQ LOAD BALANCING CONFIGURATION ---
GROQ_BASE_URL = "https://api.groq.com"

# 1. Get raw string from env (support both plural and singular env vars)
_GROQ_ENV_VAL = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))

# 2. Parse into a list
GROQ_API_KEYS = [k.strip() for k in _GROQ_ENV_VAL.split(",") if k.strip()]

# 3. Create a thread-safe infinite iterator (Round Robin)
GROQ_KEY_CYCLE = itertools.cycle(GROQ_API_KEYS) if GROQ_API_KEYS else None

if not GROQ_API_KEYS:
    print("WARNING: No GROQ_API_KEYS found. Groq models will fail.")
else:
    print(f"INFO: Loaded {len(GROQ_API_KEYS)} Groq API keys for internal load balancing.")

# --- OPENROUTER CONFIGURATION ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
if not OPENROUTER_API_KEY:
    print("WARNING: OPENROUTER_API_KEY is not set (OpenRouter models will be unavailable).")

# --- NVIDIA CONFIGURATION ---
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

if not NVIDIA_API_KEY:
    print("WARNING: NVIDIA_API_KEY is not set.")

# Default Model
MODEL_NAME = os.getenv("MODEL", "openai/gpt-oss-120b")

# -----------------------------------------------------------------------------
# OPTIONAL: Provider parameterSpecs overlays (for UI accuracy / GraphQL specs)
# -----------------------------------------------------------------------------
# You can override this at runtime by setting:
#   GROQ_PARAMETER_SPECS_JSON='{"data":{"models":[...]}}'
#
# This overlay is used to build parameter_specs for Groq models when present.
# -----------------------------------------------------------------------------

GROQ_PARAMETER_SPECS_PAYLOAD_DEFAULT = {
    "data": {
        "models": [
            {
                "name": "groq",
                "models": [
                    {"id": "allam-2-7b", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "canopylabs/orpheus-arabic-saudi", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "canopylabs/orpheus-v1-english", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "groq/compound", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "groq/compound-mini", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "llama-3.1-8b-instant", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "llama-3.3-70b-versatile", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "meta-llama/llama-guard-4-12b", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "meta-llama/llama-prompt-guard-2-22m", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "meta-llama/llama-prompt-guard-2-86m", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "moonshotai/kimi-k2-instruct", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "moonshotai/kimi-k2-instruct-0905", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "openai/gpt-oss-120b", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}, {"name": "reasoning_effort", "options": ["low", "medium", "high"]}]},
                    {"id": "openai/gpt-oss-20b", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}, {"name": "reasoning_effort", "options": ["low", "medium", "high"]}]},
                    {"id": "openai/gpt-oss-safeguard-20b", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}, {"name": "reasoning_effort", "options": ["low", "medium", "high"]}]},
                    {"id": "qwen/qwen3-32b", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}, {"name": "reasoning_effort", "options": ["default", "none"]}, {"name": "reasoning_format", "options": ["parsed", "raw", "hidden"]}]},
                ],
            }
        ]
    }
}

GROQ_PARAMETER_SPECS_PAYLOAD = GROQ_PARAMETER_SPECS_PAYLOAD_DEFAULT

_env_json = (os.getenv("GROQ_PARAMETER_SPECS_JSON") or "").strip()
if _env_json:
    try:
        GROQ_PARAMETER_SPECS_PAYLOAD = json.loads(_env_json)
        print("INFO: Loaded GROQ_PARAMETER_SPECS_PAYLOAD from GROQ_PARAMETER_SPECS_JSON.")
    except Exception:
        print("WARNING: GROQ_PARAMETER_SPECS_JSON is invalid JSON; using default overlay.")
