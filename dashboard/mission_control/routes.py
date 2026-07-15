from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from dashboard.mission_control.contracts import build_mission_control_state
from dashboard.mission_control.health import build_health_summary
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS, section_for_key
from dashboard.mission_control.serializers import safe_serialize


StateProvider = Callable[[], Mapping[str, Any] | None]


def create_mission_control_router(state_provider: StateProvider | None = None) -> APIRouter:
    provider = state_provider or (lambda: None)
    router = APIRouter()

    def state() -> dict[str, Any]:
        return build_mission_control_state(provider(), allow_mock=False)

    @router.get("/mission-control", include_in_schema=False)
    async def mission_control_index() -> RedirectResponse:
        return RedirectResponse("/mission-control/executive-overview", status_code=303)

    @router.get("/mission-control/state")
    async def mission_control_state() -> JSONResponse:
        return JSONResponse(safe_serialize(state()))

    @router.get("/mission-control/api/state")
    async def mission_control_api_state() -> JSONResponse:
        return JSONResponse(safe_serialize(state()))

    @router.get("/mission-control/api/health")
    async def mission_control_api_health() -> JSONResponse:
        current = state()
        freshness = current.get("freshness") if isinstance(current.get("freshness"), Mapping) else {}
        return JSONResponse(safe_serialize(build_health_summary(current, freshness_summary=freshness)))

    @router.get("/mission-control/navigation")
    async def mission_control_navigation() -> JSONResponse:
        return JSONResponse([section.as_dict() for section in MISSION_CONTROL_SECTIONS])

    @router.get("/mission-control/api/navigation")
    async def mission_control_api_navigation() -> JSONResponse:
        return JSONResponse([section.as_dict() for section in MISSION_CONTROL_SECTIONS])

    @router.get("/mission-control/api/page-metadata")
    async def mission_control_api_page_metadata() -> JSONResponse:
        return JSONResponse(
            {
                "pages": [section.as_dict() for section in MISSION_CONTROL_SECTIONS],
                "read_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "advisory_only": True,
            }
        )

    @router.get("/mission-control/api/brokers")
    async def mission_control_api_brokers() -> JSONResponse:
        return JSONResponse(safe_serialize(state().get("brokers", {})))

    @router.get("/mission-control/api/certification")
    async def mission_control_api_certification() -> JSONResponse:
        return JSONResponse(safe_serialize(state().get("certification", {})))

    @router.get("/mission-control/{section_slug}", response_class=HTMLResponse)
    async def mission_control_page(section_slug: str) -> HTMLResponse:
        key = str(section_slug or "").replace("-", "_")
        section = section_for_key(key)
        current = state()
        return HTMLResponse(render_mission_control_shell(current, active_section=section.key))

    return router


__all__ = ["create_mission_control_router"]
