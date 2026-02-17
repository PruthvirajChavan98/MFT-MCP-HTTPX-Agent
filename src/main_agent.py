# src/main_agent.py

"""
HFCL Agent Service - Main Application Entry Point
Production-grade AI agent API with LangGraph integration.
"""
import logging
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from src.agent_service.core.config import REDIS_URL, PORT
from src.agent_service.core.session_utils import close_redis
from src.agent_service.tools.mcp_manager import mcp_manager
from src.agent_service.data.config_manager import config_manager
from src.agent_service.llm.catalog import model_service

# Import existing routers
from src.agent_service.api.graphql import schema
from src.agent_service.api.eval_ingest import router as eval_router
from src.agent_service.api.eval_read import router as eval_read_router
from src.agent_service.api.admin import router as admin_router

# Import new endpoint routers
from src.agent_service.api.endpoints.health import router as health_router
from src.agent_service.api.endpoints.models import router as models_router
from src.agent_service.api.endpoints.sessions import router as sessions_router
from src.agent_service.api.endpoints.router_endpoints import router as router_router
from src.agent_service.api.endpoints.agent_query import router as query_router
from src.agent_service.api.endpoints.agent_stream import router as stream_router
from src.agent_service.api.endpoints.follow_up import router as follow_up_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
log = logging.getLogger("main_agent")


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Application lifespan manager."""
    log.info(f"🚀 STARTUP: Initializing services...")
    log.info(f"📦 Redis Checkpointer: {REDIS_URL}")
    
    cache_task = asyncio.create_task(model_service.start_background_loop())
    
    try:
        async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
            app_instance.state.checkpointer = checkpointer
            
            await mcp_manager.initialize()
            log.info("✅ MCP Manager initialized")
            
            yield
            
            log.info("🛑 SHUTDOWN: Cleaning up resources...")
            cache_task.cancel()
            await mcp_manager.shutdown()
            await config_manager.close()
            await close_redis()
            log.info("✅ Shutdown complete")
            
    except Exception as e:
        log.critical(f"❌ CRITICAL STARTUP FAILURE: {e}")
        raise e


# Create FastAPI app
app = FastAPI(
    title="HFCL Agent Service",
    description="Production-grade AI Agent API with LangGraph",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount GraphQL
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql", tags=["graphql"])

# Mount evaluation endpoints
app.include_router(eval_router, prefix="/eval", tags=["evaluation"])
app.include_router(eval_read_router, prefix="/eval", tags=["evaluation"])

# Mount admin endpoints
app.include_router(admin_router, tags=["admin"])

# Mount new modular endpoints
app.include_router(health_router)
app.include_router(models_router)
app.include_router(sessions_router)
app.include_router(router_router)
app.include_router(query_router)
app.include_router(stream_router)
app.include_router(follow_up_router)

log.info("✅ All routers mounted")


if __name__ == "__main__":
    import uvicorn
    log.info(f"🚀 Starting HFCL Agent Service on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")