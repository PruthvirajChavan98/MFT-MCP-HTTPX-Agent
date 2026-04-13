"""
FastAPI Application Factory
Handles app lifecycle, middleware configuration, and router mounting.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from src.agent_service.api.admin import router as admin_router
from src.agent_service.api.admin_analytics import router as admin_analytics_router
from src.agent_service.api.endpoints.agent_query import router as query_router
from src.agent_service.api.endpoints.agent_stream import router as stream_router
from src.agent_service.api.endpoints.download_proxy import router as download_proxy_router
from src.agent_service.api.endpoints.health import router as health_router
from src.agent_service.api.endpoints.live_dashboards import router as live_router
from src.agent_service.api.endpoints.models import router as models_router
from src.agent_service.api.endpoints.rate_limit_metrics import router as rate_limit_metrics_router
from src.agent_service.api.endpoints.router_endpoints import router as router_router
from src.agent_service.api.endpoints.sessions import router as sessions_router
from src.agent_service.api.eval_ingest import router as eval_router
from src.agent_service.api.eval_read import router as eval_read_router
from src.agent_service.api.feedback import router as feedback_router
from src.agent_service.core.config import (
    POSTGRES_DSN,
    POSTGRES_POOL_MAX,
    POSTGRES_POOL_MIN,
    REDIS_URL,
    SECURITY_CRITICAL_PATHS,
    SECURITY_ENABLED,
    SECURITY_MONITORED_PATHS,
    SECURITY_PREFER_IP_HEADER,
    SECURITY_TRUST_PROXY_HEADERS,
)
from src.agent_service.core.event_bus import event_bus
from src.agent_service.core.http_client import close_http_client, initialize_http_client
from src.agent_service.core.session_utils import close_redis, get_redis
from src.agent_service.llm.catalog import model_service
from src.agent_service.security.middleware import SessionRiskMiddleware
from src.agent_service.security.postgres_pool import PostgresPoolManager
from src.agent_service.security.runtime import SecurityRuntime, build_security_runtime
from src.agent_service.security.tor_block import BlockTorMiddleware
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

        cache_task = asyncio.create_task(model_service.start_background_loop())
        security_runtime: SecurityRuntime | None = None
        postgres_pool: PostgresPoolManager | None = None

        try:
            async with AsyncRedisSaver.from_conn_string(
                REDIS_URL,
                ttl={"default_ttl": 10080, "refresh_on_read": True},
            ) as checkpointer:
                self.checkpointer = checkpointer
                app.state.checkpointer = checkpointer

                await initialize_http_client()
                log.info("✅ Shared HTTP client initialized")

                await mcp_manager.initialize()
                log.info("✅ MCP Manager initialized")

                from src.agent_service.core.prompts import prompt_manager

                prompt_manager.load()
                app.state.prompt_manager = prompt_manager

                from src.common.milvus_mgr import milvus_mgr

                await milvus_mgr.aconnect()
                log.info(
                    "✅ Milvus stores initialized (kb_faqs, eval_traces_emb, eval_results_emb)"
                )

                if POSTGRES_DSN:
                    postgres_pool = PostgresPoolManager(
                        dsn=POSTGRES_DSN,
                        min_size=POSTGRES_POOL_MIN,
                        max_size=POSTGRES_POOL_MAX,
                    )
                    await postgres_pool.start()
                    app.state.postgres_pool = postgres_pool
                    app.state.pool = postgres_pool.pool

                    from src.agent_service.eval_store.pg_store import (
                        configure_shared_pool,
                        eval_pg_store,
                    )

                    await eval_pg_store.ensure_schema(postgres_pool.pool)
                    configure_shared_pool(postgres_pool.pool)
                    log.info(
                        "✅ PostgreSQL pool initialized, eval schema verified, and shared pool wired"
                    )

                if SECURITY_ENABLED:
                    redis = await get_redis()
                    security_runtime = build_security_runtime(redis)
                    await security_runtime.start()
                    app.state.security_runtime = security_runtime
                    log.info("✅ Security runtime initialized")

                yield

                log.info("🛑 SHUTDOWN: Cleaning up resources...")
                cache_task.cancel()
                if security_runtime:
                    await security_runtime.stop()
                if postgres_pool:
                    await postgres_pool.stop()
                await mcp_manager.shutdown()
                await close_http_client()
                await milvus_mgr.close()

                # Graceful EventBus Shutdown
                await event_bus.close()
                log.info("✅ EventBus shut down")

                await close_redis()
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
            title="MFT Agent Service",
            description="Production-grade AI Agent API with LangGraph",
            version="2.0.0",
            lifespan=self.lifespan,
        )

        @app.middleware("http")
        async def security_headers_middleware(request: Request, call_next):
            response = await call_next(request)
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault(
                "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
            )
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
            return response

        self._configure_cors(app)

        if SECURITY_ENABLED:
            app.add_middleware(
                SessionRiskMiddleware,
                critical_paths=SECURITY_CRITICAL_PATHS,
                monitored_paths=SECURITY_MONITORED_PATHS,
            )
            app.add_middleware(
                BlockTorMiddleware,
                critical_paths=SECURITY_CRITICAL_PATHS,
                monitored_paths=SECURITY_MONITORED_PATHS,
                proxies_trusted=SECURITY_TRUST_PROXY_HEADERS,
                prefer_header=SECURITY_PREFER_IP_HEADER,
            )

        self._mount_routers(app)

        log.info("✅ FastAPI application configured")
        return app

    @staticmethod
    def _configure_cors(app: FastAPI) -> None:
        """Configure CORS middleware from CORS_ALLOWED_ORIGINS env var."""
        _cors_origins: list[str] = [
            o.strip()
            for o in os.getenv(
                "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4173"
            ).split(",")
            if o.strip()
        ] or ["*"]

        app.add_middleware(
            CORSMiddleware,
            allow_origins=_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @staticmethod
    def _mount_routers(app: FastAPI) -> None:
        """Mount all API routers."""
        app.include_router(eval_router, prefix="/eval", tags=["evaluation"])
        app.include_router(eval_read_router, prefix="/eval", tags=["evaluation"])

        app.include_router(admin_router, tags=["admin"])
        app.include_router(admin_analytics_router)
        # Admin auth router (Phase 3b). Dormant until ADMIN_AUTH_ENABLED=true — see
        # api/endpoints/admin_auth_routes.py and tasks/todo.md plan 2026-04-10.
        from src.agent_service.api.endpoints.admin_auth_routes import router as admin_auth_router

        app.include_router(admin_auth_router, tags=["admin-auth"])
        app.include_router(feedback_router)

        app.include_router(health_router)
        app.include_router(models_router)
        app.include_router(sessions_router)
        app.include_router(router_router)
        app.include_router(query_router)
        app.include_router(stream_router)
        app.include_router(rate_limit_metrics_router)
        app.include_router(live_router)
        app.include_router(download_proxy_router)

        log.info("✅ All routers mounted")


# Singleton factory instance
app_factory = AppFactory()
