from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from fastapi import FastAPI

from dashboard.mission_control.routes import create_mission_control_router


MISSION_CONTROL_ROUTE_PREFIX = "/mission-control"
MISSION_CONTROL_HOST_MARKER = "mission_control_registered"


def register_mission_control(
    app: FastAPI,
    state_provider: Callable[[], Mapping[str, Any] | None] | None = None,
) -> FastAPI:
    if getattr(app.state, MISSION_CONTROL_HOST_MARKER, False):
        return app

    existing = [route for route in app.router.routes if str(getattr(route, "path", "")).startswith(MISSION_CONTROL_ROUTE_PREFIX)]
    if existing:
        raise RuntimeError("mission_control_route_prefix_conflict")

    router = create_mission_control_router(state_provider)
    for route in router.routes:
        methods = set(getattr(route, "methods", set()) or set())
        unsafe_methods = methods.intersection({"POST", "PUT", "PATCH", "DELETE"})
        if unsafe_methods:
            raise RuntimeError(f"mission_control_write_route_rejected:{sorted(unsafe_methods)}")

    app.include_router(router)
    setattr(app.state, MISSION_CONTROL_HOST_MARKER, True)
    return app


__all__ = [
    "MISSION_CONTROL_HOST_MARKER",
    "MISSION_CONTROL_ROUTE_PREFIX",
    "register_mission_control",
]
