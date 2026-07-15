from __future__ import annotations

from collections.abc import Callable, Mapping
import time
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
    cached_state: dict[str, Any] = {"updated_at": 0.0, "payload": {}}

    def state() -> dict[str, Any]:
        now = time.time()
        if now - float(cached_state.get("updated_at", 0.0)) <= 5.0 and isinstance(cached_state.get("payload"), dict) and cached_state["payload"]:
            return dict(cached_state["payload"])
        payload = build_mission_control_state(provider(), allow_mock=False)
        cached_state["updated_at"] = time.time()
        cached_state["payload"] = payload
        return dict(payload)

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

    @router.get("/mission-control/api/runtime")
    async def mission_control_api_runtime() -> JSONResponse:
        return JSONResponse(safe_serialize(state().get("runtime_snapshot", {})))

    @router.get("/mission-control/api/runtime-source")
    async def mission_control_api_runtime_source() -> JSONResponse:
        snapshot = state().get("runtime_snapshot", {})
        snapshot = snapshot if isinstance(snapshot, Mapping) else {}
        diagnostics = snapshot.get("source_diagnostics")
        if not isinstance(diagnostics, Mapping):
            diagnostics = state().get("runtime_source_diagnostics", {})
        return JSONResponse(
            safe_serialize(
                {
                    "source": snapshot.get("source", "UNAVAILABLE"),
                    "runtime_status": snapshot.get("runtime_status", "UNAVAILABLE"),
                    "heartbeat_status": snapshot.get("heartbeat_status", "UNAVAILABLE"),
                    "state_hash": snapshot.get("state_hash", "UNAVAILABLE"),
                    "diagnostics": diagnostics if isinstance(diagnostics, Mapping) else {},
                    "read_only": True,
                    "execution_allowed": False,
                    "live_trading_blocked": True,
                    "broker_execution_armed": False,
                    "advisory_only": True,
                }
            )
        )

    @router.get("/mission-control/api/heartbeat")
    async def mission_control_api_heartbeat() -> JSONResponse:
        snapshot = state().get("runtime_snapshot", {})
        snapshot = snapshot if isinstance(snapshot, Mapping) else {}
        return JSONResponse(
            safe_serialize(
                {
                    "runtime_id": snapshot.get("runtime_id", "UNAVAILABLE"),
                    "last_heartbeat": snapshot.get("last_heartbeat", "UNAVAILABLE"),
                    "heartbeat_status": snapshot.get("heartbeat_status", "UNAVAILABLE"),
                    "heartbeat_age_seconds": snapshot.get("heartbeat_age_seconds", "UNAVAILABLE"),
                    "state_hash": snapshot.get("state_hash", "UNAVAILABLE"),
                    "read_only": True,
                    "execution_allowed": False,
                    "live_trading_blocked": True,
                    "broker_execution_armed": False,
                    "advisory_only": True,
                }
            )
        )

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

    @router.get("/mission-control/api/decision")
    async def mission_control_api_decision() -> JSONResponse:
        return JSONResponse(safe_serialize(state().get("decision_panel", {})))

    @router.get("/mission-control/api/decision-trace")
    async def mission_control_api_decision_trace() -> JSONResponse:
        return JSONResponse(safe_serialize(state().get("decision_trace", {})))

    @router.get("/mission-control/api/explanation")
    async def mission_control_api_explanation() -> JSONResponse:
        return JSONResponse(safe_serialize(state().get("decision_explanation", {})))

    @router.get("/mission-control/api/recommendation")
    async def mission_control_api_recommendation() -> JSONResponse:
        return JSONResponse(safe_serialize(state().get("recommendation_panel", {})))

    @router.get("/mission-control/api/evidence")
    async def mission_control_api_evidence() -> JSONResponse:
        return JSONResponse(safe_serialize(state().get("evidence_graph", {})))

    @router.get("/mission-control/{section_slug}", response_class=HTMLResponse)
    async def mission_control_page(section_slug: str) -> HTMLResponse:
        key = str(section_slug or "").replace("-", "_")
        section = section_for_key(key)
        current = state()
        return HTMLResponse(render_mission_control_shell(current, active_section=section.key))

    return router


__all__ = ["create_mission_control_router"]
