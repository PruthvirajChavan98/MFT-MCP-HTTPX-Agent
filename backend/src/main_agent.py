"""MFT Agent Service main entrypoint."""

from __future__ import annotations

import logging

import uvicorn

from src.agent_service.core.app_factory import app_factory
from src.agent_service.core.config import PORT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger("main_agent")

# Keep this symbol stable because endpoint modules import `src.main_agent.app`.
app = app_factory.create_app()


if __name__ == "__main__":
    log.info("🚀 Starting MFT Agent Service on port %d", PORT)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
