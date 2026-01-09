import os

# Server Settings
SERVER_NAME = "hero_fincorp"
SERVER_URL = os.getenv("MCP_SERVER_URL", "http://0.0.0.0:8050/sse")
PORT = int(os.getenv("PORT", "8000"))

# Logic Settings
KEEP_LAST = int(os.getenv("KEEP_LAST_MESSAGES", "20"))
DEBUG_MODE = False

# External Services
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
GROQ_API_KEY = os.getenv("API_KEY", "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")
GROQ_BASE_URL = "https://api.groq.com"
MODEL_NAME = os.getenv("MODEL", "openai/gpt-oss-120b")
