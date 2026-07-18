from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
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
        return JSONResponse(safe_serialize(_runtime_snapshot_payload(state())))

    @router.get("/mission-control/api/runtime-source")
    async def mission_control_api_runtime_source() -> JSONResponse:
        return JSONResponse(safe_serialize(_runtime_source_payload(state())))

    @router.get("/mission-control/api/heartbeat")
    async def mission_control_api_heartbeat() -> JSONResponse:
        return JSONResponse(safe_serialize(_heartbeat_payload(state())))

    @router.get("/mission-control/navigation")
    async def mission_control_navigation() -> JSONResponse:
        return JSONResponse([section.as_dict() for section in MISSION_CONTROL_SECTIONS])

    @router.get("/mission-control/api/navigation")
    async def mission_control_api_navigation() -> JSONResponse:
        return JSONResponse([section.as_dict() for section in MISSION_CONTROL_SECTIONS])

    @router.get("/mission-control/api/page-metadata")
    async def mission_control_api_page_metadata() -> JSONResponse:
        return JSONResponse(_page_metadata_payload(state()))

    @router.get("/mission-control/api/brokers")
    async def mission_control_api_brokers() -> JSONResponse:
        return JSONResponse(safe_serialize(state().get("brokers", {})))

    @router.get("/mission-control/api/certification")
    async def mission_control_api_certification() -> JSONResponse:
        return JSONResponse(safe_serialize(state().get("certification", {})))

    @router.get("/mission-control/api/final-certification")
    async def mission_control_api_final_certification() -> JSONResponse:
        return JSONResponse(safe_serialize(state().get("final_certification", {})))

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

    # ── Phase 174: Daily Executive Brief / morning briefings (GET-only) ──
    @router.get("/mission-control/api/morning-briefings")
    async def mission_control_morning_briefings(
        date_from: str | None = None,
        date_to: str | None = None,
        include_failed: bool = False,
    ) -> JSONResponse:
        retrieval = _morning_brief_retrieval()
        return JSONResponse(
            safe_serialize(
                _read_only_payload(
                    {
                        "items": retrieval.list_summaries(
                            date_from=date_from,
                            date_to=date_to,
                            include_failed=include_failed,
                        ),
                        "manifest": retrieval.manifest(),
                    }
                )
            )
        )

    @router.get("/mission-control/api/morning-briefings/latest")
    async def mission_control_morning_briefings_latest() -> JSONResponse:
        brief = _morning_brief_retrieval().latest()
        if brief is None:
            return JSONResponse(
                safe_serialize(
                    _read_only_payload(
                        {
                            "status": "DATA UNAVAILABLE",
                            "reason": "no_final_morning_brief",
                        }
                    )
                ),
                status_code=404,
            )
        return JSONResponse(safe_serialize(_read_only_payload(brief)))

    @router.get("/mission-control/api/morning-briefings/manifest")
    async def mission_control_morning_briefings_manifest() -> JSONResponse:
        return JSONResponse(safe_serialize(_read_only_payload(_morning_brief_retrieval().manifest())))

    @router.get("/mission-control/api/morning-briefings/compare")
    async def mission_control_morning_briefings_compare(
        from_date: str = Query("", alias="from"),
        to_date: str = Query("", alias="to"),
    ) -> JSONResponse:
        return JSONResponse(
            safe_serialize(_read_only_payload(_morning_brief_retrieval().compare_stub(from_date, to_date)))
        )

    @router.get("/mission-control/api/morning-briefings/{report_date}")
    async def mission_control_morning_briefings_by_date(report_date: str) -> JSONResponse:
        retrieval = _morning_brief_retrieval()
        try:
            brief = retrieval.by_date(report_date)
        except ValueError:
            return JSONResponse(
                safe_serialize(_read_only_payload({"status": "BAD_REQUEST", "reason": "invalid_report_date"})),
                status_code=400,
            )
        if brief is None:
            return JSONResponse(
                safe_serialize(_read_only_payload({"status": "DATA UNAVAILABLE", "report_date": report_date})),
                status_code=404,
            )
        return JSONResponse(safe_serialize(_read_only_payload(brief)))

    @router.get("/mission-control/api/morning-briefings/{report_date}/versions")
    async def mission_control_morning_briefings_versions(report_date: str) -> JSONResponse:
        retrieval = _morning_brief_retrieval()
        try:
            versions = retrieval.versions(report_date)
        except ValueError:
            return JSONResponse(
                safe_serialize(_read_only_payload({"status": "BAD_REQUEST", "reason": "invalid_report_date"})),
                status_code=400,
            )
        return JSONResponse(
            safe_serialize(_read_only_payload({"report_date": report_date, "versions": versions}))
        )

    @router.get("/mission-control/api/morning-briefings/{report_date}/previous")
    async def mission_control_morning_briefings_previous(report_date: str) -> JSONResponse:
        brief = _morning_brief_retrieval().previous(report_date)
        if brief is None:
            return JSONResponse(
                safe_serialize(_read_only_payload({"status": "DATA UNAVAILABLE", "report_date": report_date})),
                status_code=404,
            )
        return JSONResponse(safe_serialize(_read_only_payload(brief)))

    @router.get("/mission-control/api/morning-briefings/{report_date}/next")
    async def mission_control_morning_briefings_next(report_date: str) -> JSONResponse:
        brief = _morning_brief_retrieval().next(report_date)
        if brief is None:
            return JSONResponse(
                safe_serialize(_read_only_payload({"status": "DATA UNAVAILABLE", "report_date": report_date})),
                status_code=404,
            )
        return JSONResponse(safe_serialize(_read_only_payload(brief)))

    @router.get("/mission-control/api/morning-briefings/{report_date}/distribution-status")
    async def mission_control_morning_briefings_distribution_status(report_date: str) -> JSONResponse:
        """Read-only distribution status. Write actions are under /api/v1/executive-brief (freeze)."""
        retrieval = _morning_brief_retrieval()
        brief = retrieval.by_date(report_date)
        year, month = report_date.split("-")[0], report_date.split("-")[1] if len(report_date) >= 7 else ("", "")
        pdf_path = None
        printable_status = "UNAVAILABLE"
        if brief is not None:
            ver = brief.get("report_version") or brief.get("version")
            candidate = (
                Path.cwd()
                / "artifacts"
                / "runtime_reports"
                / "morning_briefings"
                / year
                / month
                / report_date
                / str(ver)
                / "executive_morning_brief.pdf"
            )
            if candidate.is_file():
                pdf_path = str(candidate)
                printable_status = "OK"
            else:
                man = (
                    Path.cwd()
                    / "artifacts"
                    / "runtime_reports"
                    / "morning_briefings"
                    / year
                    / month
                    / report_date
                    / str(ver)
                    / "manifest.json"
                )
                if man.is_file():
                    try:
                        meta = json.loads(man.read_text(encoding="utf-8"))
                        printable_status = str(meta.get("printable_status") or meta.get("pdf", {}).get("status") or "PARTIAL")
                    except Exception:
                        printable_status = "PARTIAL"
        return JSONResponse(
            safe_serialize(
                _read_only_payload(
                    {
                        "report_date": report_date,
                        "report_present": brief is not None,
                        "report_status": None if brief is None else brief.get("report_status"),
                        "printable_status": printable_status,
                        "pdf_archived": pdf_path is not None,
                        "controlled_write_api": "/api/v1/executive-brief",
                        "note": "Mission Control is GET-only; print/email POST actions use /api/v1/executive-brief.",
                    }
                )
            )
        )

    @router.get("/mission-control/api/morning-briefings/{report_date}/print")
    async def mission_control_morning_briefings_print_info(report_date: str) -> JSONResponse:
        return JSONResponse(
            safe_serialize(
                _read_only_payload(
                    {
                        "report_date": report_date,
                        "print_endpoint": f"/api/v1/executive-brief/{report_date}/print",
                        "pdf_endpoint": f"/api/v1/executive-brief/{report_date}/pdf",
                        "requires_permission": "executive_brief_print",
                        "note": "Use /api/v1/executive-brief for RBAC-gated printable HTML/PDF (MC remains GET-only).",
                    }
                )
            )
        )

    @router.get("/mission-control/api/morning-briefings/{report_date}/pdf")
    async def mission_control_morning_briefings_pdf_info(report_date: str) -> JSONResponse:
        return JSONResponse(
            safe_serialize(
                _read_only_payload(
                    {
                        "report_date": report_date,
                        "pdf_endpoint": f"/api/v1/executive-brief/{report_date}/pdf",
                        "requires_permission": "executive_brief_print",
                        "note": "PDF bytes are served from /api/v1/executive-brief to preserve Mission Control GET-only freeze.",
                    }
                )
            )
        )

    @router.get("/mission-control/{section_slug}", response_class=HTMLResponse)
    async def mission_control_page(section_slug: str) -> HTMLResponse:
        key = str(section_slug or "").replace("-", "_")
        section = section_for_key(key)
        current = state()
        return HTMLResponse(render_mission_control_shell(current, active_section=section.key))

    return router


def _morning_brief_retrieval():
    from pathlib import Path

    from backend.executive_intelligence.retrieval import MorningBriefRetrieval

    root = Path.cwd() / "artifacts" / "runtime_reports" / "morning_briefings"
    return MorningBriefRetrieval(root)


def _runtime_snapshot_payload(current: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = current.get("runtime_snapshot", {})
    return dict(snapshot) if isinstance(snapshot, Mapping) else {}


def _runtime_source_payload(current: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = _runtime_snapshot_payload(current)
    diagnostics = snapshot.get("source_diagnostics")
    if not isinstance(diagnostics, Mapping):
        diagnostics = current.get("runtime_source_diagnostics", {})
    return _read_only_payload(
        {
            "source": snapshot.get("source", "UNAVAILABLE"),
            "runtime_status": snapshot.get("runtime_status", "UNAVAILABLE"),
            "heartbeat_status": snapshot.get("heartbeat_status", "UNAVAILABLE"),
            "state_hash": snapshot.get("state_hash", "UNAVAILABLE"),
            "diagnostics": diagnostics if isinstance(diagnostics, Mapping) else {},
        }
    )


def _heartbeat_payload(current: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = _runtime_snapshot_payload(current)
    return _read_only_payload(
        {
            "runtime_id": snapshot.get("runtime_id", "UNAVAILABLE"),
            "last_heartbeat": snapshot.get("last_heartbeat", "UNAVAILABLE"),
            "heartbeat_status": snapshot.get("heartbeat_status", "UNAVAILABLE"),
            "heartbeat_age_seconds": snapshot.get("heartbeat_age_seconds", "UNAVAILABLE"),
            "state_hash": snapshot.get("state_hash", "UNAVAILABLE"),
        }
    )


def _page_metadata_payload(current: Mapping[str, Any]) -> dict[str, Any]:
    runtime = current.get("runtime") if isinstance(current.get("runtime"), Mapping) else {}
    freshness = current.get("freshness") if isinstance(current.get("freshness"), Mapping) else {}
    return _read_only_payload(
        {
            "pages": [section.as_dict() for section in MISSION_CONTROL_SECTIONS],
            "schema_version": current.get("schema_version", "UNAVAILABLE"),
            "generated_at": current.get("generated_at", "UNAVAILABLE"),
            "state_hash": current.get("state_hash", "UNAVAILABLE"),
            "runtime_id": runtime.get("runtime_id", "UNAVAILABLE"),
            "runtime_state_hash": runtime.get("state_hash", "UNAVAILABLE"),
            "freshness": freshness.get("overall_freshness", "UNAVAILABLE"),
        }
    )


def _read_only_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(payload),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


__all__ = ["create_mission_control_router"]
