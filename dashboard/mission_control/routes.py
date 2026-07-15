from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS, section_for_key


StateProvider = Callable[[], Mapping[str, Any] | None]


def create_mission_control_router(state_provider: StateProvider | None = None) -> APIRouter:
    provider = state_provider or (lambda: None)
    router = APIRouter()

    @router.get("/mission-control", include_in_schema=False)
    async def mission_control_index() -> RedirectResponse:
        return RedirectResponse("/mission-control/executive-overview", status_code=303)

    @router.get("/mission-control/state")
    async def mission_control_state() -> JSONResponse:
        return JSONResponse(build_mission_control_state(provider()))

    @router.get("/mission-control/navigation")
    async def mission_control_navigation() -> JSONResponse:
        return JSONResponse([section.as_dict() for section in MISSION_CONTROL_SECTIONS])

    @router.get("/mission-control/{section_slug}", response_class=HTMLResponse)
    async def mission_control_page(section_slug: str) -> HTMLResponse:
        key = str(section_slug or "").replace("-", "_")
        section = section_for_key(key)
        state = build_mission_control_state(provider())
        return HTMLResponse(render_mission_control_shell(state, active_section=section.key))

    return router


__all__ = ["create_mission_control_router"]
