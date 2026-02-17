"""
FastAPI Application Factory
Handles app lifecycle, middleware configuration, and router mounting.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from strawberry.fastapi import GraphQLRouter

from src.agent_service.api.admin import router as admin_router
from src.agent_service.api.eval_ingest import router as eval_router
from src.agent_service.api.eval_read import router as eval_read_router

# Import routers
from src.agent_service.api.graphql import schema
from src.agent_service.core.config import REDIS_URL
from src.agent_service.data.config_manager import config_manager
from src.agent_service.llm.catalog import model_service
from src.agent_service.tools.mcp_manager import mcp_manager

log = logging.getLogger(__name__)


class AppFactory:
    """Factory for creating and configuring FastAPI application."""

    def __init__(self):
        self.checkpointer: Optional[AsyncRedisSaver] = None

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """
        Application lifespan manager.
        Handles startup and shutdown of all services.
        """
        log.info("🚀 STARTUP: Initializing services...")
        log.info(f"📦 Redis Checkpointer: {REDIS_URL}")

        # Start background cache refresh
        cache_task = asyncio.create_task(model_service.start_background_loop())

        try:
            # Initialize Redis checkpointer
            async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
                self.checkpointer = checkpointer
                app.state.checkpointer = checkpointer

                # Initialize MCP manager
                await mcp_manager.initialize()
                log.info("✅ MCP Manager initialized")

                yield

                # Cleanup on shutdown
                log.info("🛑 SHUTDOWN: Cleaning up resources...")
                cache_task.cancel()
                await mcp_manager.shutdown()
                await config_manager.close()
                log.info("✅ Shutdown complete")

        except Exception as e:
            log.critical(f"❌ CRITICAL STARTUP FAILURE: {e}")
            raise e

    def create_app(self) -> FastAPI:
        """
        Create and configure FastAPI application.

        Returns:
            Configured FastAPI instance
        """
        app = FastAPI(
            title="HFCL Agent Service",
            description="Production-grade AI Agent API with LangGraph",
            version="2.0.0",
            lifespan=self.lifespan,
        )

        # Configure CORS
        self._configure_cors(app)

        # Mount routers
        self._mount_routers(app)

        log.info("✅ FastAPI application configured")
        return app

    @staticmethod
    def _configure_cors(app: FastAPI) -> None:
        """Configure CORS middleware."""
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @staticmethod
    def _mount_routers(app: FastAPI) -> None:
        """Mount all API routers."""
        # GraphQL
        graphql_app = GraphQLRouter(schema)
        app.include_router(graphql_app, prefix="/graphql", tags=["graphql"])

        # Evaluation endpoints
        app.include_router(eval_router, prefix="/eval", tags=["evaluation"])
        app.include_router(eval_read_router, prefix="/eval", tags=["evaluation"])

        # Admin endpoints
        app.include_router(admin_router, tags=["admin"])

        log.info("✅ All routers mounted")


# Singleton factory instance
app_factory = AppFactory()
