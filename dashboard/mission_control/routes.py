from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.security.authorization_context import apply_auth_to_mission_control_state
from backend.security.auth_diagnostics import log_authorization_denial
from dashboard.auth.session_bridge import resolve_authorization_context
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

    def state_base() -> dict[str, Any]:
        now = time.time()
        if now - float(cached_state.get("updated_at", 0.0)) <= 5.0 and isinstance(cached_state.get("payload"), dict) and cached_state["payload"]:
            return dict(cached_state["payload"])
        payload = build_mission_control_state(provider(), allow_mock=False)
        cached_state["updated_at"] = time.time()
        cached_state["payload"] = payload
        return dict(payload)

    def state(request: Request | None = None) -> dict[str, Any]:
        """Dashboard snapshot overlaid with the canonical authorization context."""
        auth = resolve_authorization_context(channel="mission_control", request=request)
        return apply_auth_to_mission_control_state(state_base(), auth)

    def _reports_role_user(request: Request) -> tuple[str, str, Any]:
        auth = resolve_authorization_context(channel="mission_control_reports_api", request=request)
        if not auth.authenticated or not auth.active:
            log_authorization_denial(
                route=str(request.url.path),
                auth=auth,
                permission_requested="reports_view",
                denial_reason=auth.denial_reason or "not_authenticated",
            )
        return auth.role, auth.user_id, auth

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

    @router.get("/mission-control/api/reports/catalog")
    async def mission_control_reports_catalog(
        request: Request,
        category: str | None = None,
        status: str | None = None,
        q: str | None = None,
        generatable_only: bool = False,
    ) -> JSONResponse:
        from backend.reports_center.registry import catalog_payload
        from backend.reports_center.rbac import ReportsAccessControl

        role, _user, auth = _reports_role_user(request)
        if not auth.authenticated or not ReportsAccessControl().can_view_catalog(role):
            return JSONResponse(
                safe_serialize(_read_only_payload({"status": "DENIED", "authorization": auth.reports_authorization()})),
                status_code=403,
            )
        return JSONResponse(
            safe_serialize(
                _read_only_payload(
                    catalog_payload(
                        category=category,
                        status=status,
                        q=q,
                        generatable_only=generatable_only,
                    )
                )
            )
        )

    @router.get("/mission-control/api/reports/home")
    async def mission_control_reports_home(request: Request) -> JSONResponse:
        from backend.reports_center.service import ReportsCenterService

        role, user_id, auth = _reports_role_user(request)
        home = ReportsCenterService().home(role=role, user_id=user_id)
        home["authorization"] = auth.reports_authorization()
        if not auth.authenticated or not home["authorization"].get("reports_view"):
            return JSONResponse(safe_serialize(_read_only_payload(home)), status_code=403)
        return JSONResponse(safe_serialize(_read_only_payload(home)))

    @router.get("/mission-control/api/reports/categories")
    async def mission_control_reports_categories(request: Request) -> JSONResponse:
        from backend.reports_center.registry import category_menu
        from backend.reports_center.rbac import ReportsAccessControl

        role, _user, auth = _reports_role_user(request)
        if not auth.authenticated or not ReportsAccessControl().can_view_catalog(role):
            return JSONResponse(safe_serialize(_read_only_payload({"status": "DENIED"})), status_code=403)
        return JSONResponse(safe_serialize(_read_only_payload({"categories": category_menu()})))

    @router.get("/mission-control/api/reports/definitions/{report_code}")
    async def mission_control_reports_definition(report_code: str, request: Request) -> JSONResponse:
        from backend.reports_center.registry import by_code
        from backend.reports_center.rbac import ReportsAccessControl

        role, _user, auth = _reports_role_user(request)
        item = by_code(report_code)
        if item is None:
            return JSONResponse(safe_serialize(_read_only_payload({"status": "NOT_FOUND"})), status_code=404)
        if not auth.authenticated or not ReportsAccessControl().can_view_report(role, item.required_view_permission):
            return JSONResponse(safe_serialize(_read_only_payload({"status": "DENIED"})), status_code=403)
        return JSONResponse(safe_serialize(_read_only_payload({"status": "OK", "definition": item.as_dict()})))

    @router.get("/mission-control/api/reports/readiness/{report_code}")
    async def mission_control_reports_readiness(report_code: str, request: Request) -> JSONResponse:
        from backend.reports_center.service import ReportsCenterService

        role, _user, auth = _reports_role_user(request)
        if not auth.authenticated:
            return JSONResponse(safe_serialize(_read_only_payload({"status": "DENIED"})), status_code=403)
        return JSONResponse(
            safe_serialize(_read_only_payload(ReportsCenterService().readiness(report_code, role=role)))
        )

    @router.get("/mission-control/api/reports")
    async def mission_control_reports_library(
        request: Request,
        category: str | None = None,
        report_type: str | None = None,
        status: str | None = None,
        report_id: str | None = None,
    ) -> JSONResponse:
        from backend.reports_center.service import ReportsCenterService

        role, _user, auth = _reports_role_user(request)
        if not auth.authenticated:
            return JSONResponse(safe_serialize(_read_only_payload({"status": "DENIED"})), status_code=403)
        return JSONResponse(
            safe_serialize(
                _read_only_payload(
                    ReportsCenterService().list_library(
                        filters={
                            "category": category,
                            "report_type": report_type,
                            "status": status,
                            "report_id": report_id,
                        },
                        role=role,
                    )
                )
            )
        )

    @router.get("/mission-control/api/reports/{report_id}")
    async def mission_control_reports_get(report_id: str, request: Request) -> JSONResponse:
        from backend.reports_center.service import ReportsCenterService

        role, _user, auth = _reports_role_user(request)
        if not auth.authenticated:
            return JSONResponse(safe_serialize(_read_only_payload({"status": "DENIED"})), status_code=403)
        result = ReportsCenterService().retrieve(report_id, role=role)
        code = 200 if result.get("status") == "OK" else 404
        return JSONResponse(safe_serialize(_read_only_payload(result)), status_code=code)

    @router.get("/mission-control/api/reports/{report_id}/versions")
    async def mission_control_reports_versions(report_id: str, request: Request) -> JSONResponse:
        from backend.reports_center.service import ReportsCenterService

        role, _user, auth = _reports_role_user(request)
        if not auth.authenticated:
            return JSONResponse(safe_serialize(_read_only_payload({"status": "DENIED"})), status_code=403)
        svc = ReportsCenterService()
        result = svc.retrieve(report_id, role=role)
        if result.get("status") != "OK":
            return JSONResponse(safe_serialize(_read_only_payload(result)), status_code=404)
        report = result["report"]
        vers = svc.archive.versions(
            str(report.get("report_family") or "unknown"),
            str(report.get("report_type") or ""),
            str(report.get("report_date") or ""),
        )
        return JSONResponse(safe_serialize(_read_only_payload({"report_id": report_id, "versions": vers})))

    @router.get("/mission-control/api/reports/{report_id}/print")
    async def mission_control_reports_print_info(report_id: str, request: Request) -> JSONResponse:
        _role, _user, auth = _reports_role_user(request)
        if not auth.authenticated:
            return JSONResponse(safe_serialize(_read_only_payload({"status": "DENIED"})), status_code=403)
        return JSONResponse(
            safe_serialize(
                _read_only_payload(
                    {
                        "report_id": report_id,
                        "print_endpoint": f"/api/v1/reports/{report_id}/print",
                        "pdf_endpoint": f"/api/v1/reports/{report_id}/pdf",
                        "note": "Printable HTML/PDF delivery is under /api/v1/reports (MC remains GET-only).",
                    }
                )
            )
        )

    @router.get("/mission-control/api/reports/{report_id}/pdf")
    async def mission_control_reports_pdf_info(report_id: str, request: Request) -> JSONResponse:
        from backend.reports_center.service import ReportsCenterService

        role, user, auth = _reports_role_user(request)
        if not auth.authenticated:
            return JSONResponse(safe_serialize(_read_only_payload({"status": "DENIED"})), status_code=403)
        info = ReportsCenterService().print_info(report_id, role=role, user_id=user)
        return JSONResponse(
            safe_serialize(
                _read_only_payload(
                    {
                        **info,
                        "pdf_endpoint": f"/api/v1/reports/{report_id}/pdf",
                        "note": "Controlled PDF bytes are delivered by GET /api/v1/reports/{id}/pdf.",
                    }
                )
            )
        )

    @router.get("/mission-control/api/reports/{report_id}/audit")
    async def mission_control_reports_audit(report_id: str, request: Request) -> JSONResponse:
        from backend.reports_center.service import ReportsCenterService

        role, _user, auth = _reports_role_user(request)
        if not auth.authenticated:
            return JSONResponse(safe_serialize(_read_only_payload({"status": "DENIED"})), status_code=403)
        return JSONResponse(
            safe_serialize(_read_only_payload(ReportsCenterService().audit_history(report_id, role=role)))
        )

    @router.get("/mission-control/{section_slug}", response_class=HTMLResponse)
    async def mission_control_page(section_slug: str, request: Request) -> HTMLResponse:
        key = str(section_slug or "").replace("-", "_")
        section = section_for_key(key)
        current = state(request)
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
