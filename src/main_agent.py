"""
HFCL Agent Service - Main Application Entry Point
Production-grade AI agent API with LangGraph integration.
"""
import logging

from src.agent_service.core.app_factory import app_factory

# Import endpoint routers
from src.agent_service.api.endpoints.health import router as health_router
from src.agent_service.api.endpoints.models import router as models_router
from src.agent_service.api.endpoints.sessions import router as sessions_router
from src.agent_service.api.endpoints.router_endpoints import router as router_router

# Import agent-specific endpoints (to be created separately)
from src.agent_service.api.endpoints.agent_query import router as query_router
from src.agent_service.api.endpoints.agent_stream import router as stream_router
from src.agent_service.api.endpoints.follow_up import router as follow_up_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
log = logging.getLogger("main_agent")

# Create application
app = app_factory.create_app()

# Mount endpoint routers
app.include_router(health_router)
app.include_router(models_router)
app.include_router(sessions_router)
app.include_router(router_router)

# Agent query/stream endpoints would be added here
app.include_router(query_router)
app.include_router(stream_router)
app.include_router(follow_up_router)

if __name__ == "__main__":
    import uvicorn
    from src.agent_service.core.config import PORT
    
    log.info(f"🚀 Starting HFCL Agent Service on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")