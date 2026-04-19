from __future__ import annotations

import functools
import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from .session_context import SessionContext, SessionContextError
from .session_store import RedisSessionStore, valid_session_id

log = logging.getLogger(name="mcp_auth_decorator")

AUTH_REJECT_MESSAGE = (
    "Please log in first. Use the generate_otp tool to start the login flow, "
    "then validate_otp with the code you received."
)

_CTX_PARAM_NAME = "ctx"

_R = TypeVar("_R")


_default_session_store = RedisSessionStore()


def _get_default_session_store() -> RedisSessionStore:
    """Indirection so tests can monkeypatch the default store.

    Tools that live in server.py share the module-level singleton; this
    helper lets unit tests swap the singleton without touching every
    decorated tool's call-site.
    """
    return _default_session_store


def requires_authenticated_session(
    fn: Callable[..., Awaitable[_R]],
) -> Callable[..., Awaitable[_R | str]]:
    """Enforce a populated, authenticated session before a tool runs.

    The decorated (inner) function MUST declare a ``ctx: SessionContext``
    parameter. The decorator replaces that parameter with a public
    ``session_id: str`` parameter in the MCP-facing signature — FastMCP's
    schema introspection sees ``session_id``, while the inner function
    receives a typed, read-only ``SessionContext`` proving the caller is
    authenticated.

    On any failure path — missing session_id, unknown session, session
    without ``auth_state="authenticated"``, malformed identity anchors —
    the wrapper returns the canonical ``AUTH_REJECT_MESSAGE`` string
    instead of raising. The agent LLM sees this as the tool's response
    and surfaces a user-friendly re-login prompt.
    """
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())

    ctx_index: int | None = None
    for i, p in enumerate(params):
        if p.name == _CTX_PARAM_NAME:
            ctx_index = i
            break
    if ctx_index is None:
        raise TypeError(
            f"@requires_authenticated_session requires '{fn.__name__}' to "
            f"declare a '{_CTX_PARAM_NAME}: SessionContext' parameter"
        )

    public_params = list(params)
    public_params[ctx_index] = inspect.Parameter(
        name="session_id",
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=str,
    )
    public_sig = sig.replace(parameters=public_params)
    tool_name = fn.__name__

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> _R | str:
        try:
            bound = public_sig.bind(*args, **kwargs)
        except TypeError:
            log.warning("auth decorator: bad args for %s", tool_name)
            return AUTH_REJECT_MESSAGE
        bound.apply_defaults()

        session_id_raw = bound.arguments.pop("session_id", None)
        try:
            sid = valid_session_id(session_id_raw)
        except (ValueError, TypeError):
            return AUTH_REJECT_MESSAGE

        store = _get_default_session_store()
        raw = await store.get(sid) or {}
        if raw.get("auth_state") != "authenticated":
            log.info(
                "auth decorator: reject tool=%s sid=%s reason=%s",
                tool_name,
                sid,
                "unauthenticated" if raw else "missing_session",
            )
            return AUTH_REJECT_MESSAGE

        try:
            ctx = SessionContext.from_session_dict(sid, raw)
        except SessionContextError as exc:
            log.warning(
                "auth decorator: malformed session tool=%s sid=%s err=%s",
                tool_name,
                sid,
                exc,
            )
            return AUTH_REJECT_MESSAGE

        await store.update(sid, {"_last_tool": tool_name, "_last_touch_ts": time.time()})

        bound.arguments[_CTX_PARAM_NAME] = ctx
        # Call the inner fn by keyword so the ctx we just injected isn't
        # dropped: bound.args/kwargs derives from the PUBLIC signature,
        # which no longer contains `ctx` by construction.
        return await fn(**bound.arguments)

    wrapper.__signature__ = public_sig  # type: ignore[attr-defined]
    new_annotations: dict[str, Any] = {}
    for p in public_params:
        if p.annotation is not inspect.Parameter.empty:
            new_annotations[p.name] = p.annotation
    if sig.return_annotation is not inspect.Signature.empty:
        new_annotations["return"] = sig.return_annotation
    wrapper.__annotations__ = new_annotations

    return wrapper
