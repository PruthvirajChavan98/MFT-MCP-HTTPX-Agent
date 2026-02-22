"""HTTP middleware for session risk enforcement."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.agent_service.security.session_security import SessionSecurityValidator

log = logging.getLogger("security.middleware")


def _audit(event_type: str, **fields: object) -> None:
    payload = {
        "event_type": event_type,
        "event_time": int(time.time()),
        **fields,
    }
    log.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))


class SessionRiskMiddleware(BaseHTTPMiddleware):
    """Evaluate session risk and enforce deny/step-up responses."""

    def __init__(
        self,
        app: ASGIApp,
        validator: SessionSecurityValidator | None = None,
        *,
        critical_paths: Iterable[str] = (),
        monitored_paths: Iterable[str] = (),
    ) -> None:
        super().__init__(app)
        self.validator = validator
        self.critical_paths = tuple(critical_paths)
        self.monitored_paths = tuple(monitored_paths)

    def _path_mode(self, path: str) -> str:
        if any(path.startswith(prefix) for prefix in self.critical_paths):
            return "critical"
        if any(path.startswith(prefix) for prefix in self.monitored_paths):
            return "monitored"
        return "critical"

    async def dispatch(self, request: Request, call_next):
        validator = self.validator
        if validator is None:
            runtime = getattr(request.app.state, "security_runtime", None)
            validator = getattr(runtime, "session_validator", None) if runtime else None

        if validator is None:
            return await call_next(request)

        session_id = request.headers.get("x-session-id") or request.headers.get("session-id")
        device_fingerprint = request.headers.get("x-device-fingerprint")

        client_ip = getattr(request.state, "client_ip", None)
        if not client_ip and request.client:
            client_ip = request.client.host

        if not session_id or not client_ip:
            return await call_next(request)

        mode = self._path_mode(request.url.path)

        try:
            assessment = await validator.assess(
                session_id=session_id,
                client_ip=client_ip,
                device_fingerprint=device_fingerprint,
            )
        except Exception as exc:
            _audit(
                "session_risk_failed",
                session_id=session_id,
                ip=client_ip,
                path=request.url.path,
                error=repr(exc),
            )
            return await call_next(request)

        request.state.session_risk = assessment

        if assessment.decision == "deny" and mode == "critical":
            _audit(
                "session_risk_denied",
                session_id=session_id,
                ip=client_ip,
                path=request.url.path,
                score=assessment.score,
                reasons=assessment.reasons,
            )

            import asyncio

            from src.agent_service.core.event_bus import event_bus

            # Fire and forget without blocking the middleware
            asyncio.create_task(
                event_bus.publish(
                    channel="live:global:security",
                    event_type="risk_denied",
                    data={"ip": client_ip, "session_id": session_id, "path": request.url.path},
                )
            )

            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Request denied by session security policy",
                    "risk_score": assessment.score,
                    "reasons": assessment.reasons,
                },
                headers={"Cache-Control": "no-store"},
            )

        if assessment.decision == "step_up" and mode == "critical":
            _audit(
                "session_risk_step_up",
                session_id=session_id,
                ip=client_ip,
                path=request.url.path,
                score=assessment.score,
                reasons=assessment.reasons,
            )
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Step-up authentication required",
                    "required_action": assessment.required_action,
                    "risk_score": assessment.score,
                    "reasons": assessment.reasons,
                },
                headers={"X-Step-Up-Required": "1", "Cache-Control": "no-store"},
            )

        return await call_next(request)
