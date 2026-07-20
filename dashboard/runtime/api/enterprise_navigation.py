"""Read-only enterprise navigation contract API (Phase 177H.1)."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from dashboard.enterprise_shell.nav_contract import build_enterprise_navigation_contract


def create_enterprise_navigation_router(
    *,
    surface: str = "launcher_spa",
    platform_status_provider: Callable[[], Mapping[str, Any]] | None = None,
) -> Any:
    try:
        from fastapi import APIRouter
    except Exception:  # pragma: no cover
        return None

    router = APIRouter(tags=["enterprise-navigation"])

    @router.get("/api/navigation/enterprise")
    def get_enterprise_navigation() -> dict[str, Any]:
        status = platform_status_provider() if platform_status_provider else None
        return build_enterprise_navigation_contract(surface=surface, platform_status=status)

    return router


__all__ = ["create_enterprise_navigation_router"]
