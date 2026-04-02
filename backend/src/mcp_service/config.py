import os

CRM_BASE_URL = os.getenv("CRM_BASE_URL", "http://localhost:8080").rstrip("/")
MCP_SERVER_HOST = "0.0.0.0"
MCP_SERVER_PORT = 8050
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- DOWNLOAD PROXY ---
DOWNLOAD_PROXY_BASE_URL = os.getenv("DOWNLOAD_PROXY_BASE_URL", "http://localhost:8000").rstrip("/")
DOWNLOAD_TOKEN_TTL_SECONDS = int(os.getenv("DOWNLOAD_TOKEN_TTL_SECONDS", "600"))
