"""Ensure the chat-widget eval-status poll is NOT admin-gated.

Regression lock for:
  GET /eval/trace/{trace_id}/eval-status
polled by `features/chat/hooks/useEvalStatus.ts` after each assistant
response. Chat users have no admin cookie, so the endpoint must live on
the public sibling router — not the admin-gated one. Every other
`/eval/*` read stays admin-only.
"""

from __future__ import annotations

from src.agent_service.api import eval_read


def _dep_funcs(router) -> list:
    return [d.dependency for d in (router.dependencies or [])]


def _route_paths(router) -> set[str]:
    return {getattr(r, "path", "") for r in router.routes}


def test_admin_router_requires_admin() -> None:
    funcs = _dep_funcs(eval_read.router)
    # The admin-gated router must still carry require_admin.
    assert any(
        getattr(fn, "__name__", "") == "require_admin" for fn in funcs
    ), f"admin router lost its require_admin dependency; deps={funcs}"


def test_public_router_has_no_admin_dependency() -> None:
    assert _dep_funcs(eval_read.public_router) == []


def test_eval_status_route_is_on_public_router() -> None:
    assert "/trace/{trace_id}/eval-status" in _route_paths(eval_read.public_router)
    assert "/trace/{trace_id}/eval-status" not in _route_paths(eval_read.router)


def test_other_eval_routes_stay_admin_gated() -> None:
    admin_paths = _route_paths(eval_read.router)
    # Spot-check a few endpoints that must remain admin-only.
    for path in (
        "/search",
        "/sessions",
        "/fulltext",
        "/vector-search",
        "/metrics/summary",
        "/metrics/failures",
        "/question-types",
    ):
        assert path in admin_paths, f"{path} must stay on admin-gated router"
