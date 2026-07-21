"""Read-only report discovery and paginated viewer routes (Phase 177H)."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from dashboard.enterprise_shell.reports_hub import build_reports_hub_payload
from dashboard.enterprise_shell.routes import ROUTES, mobile_home_href
from dashboard.reports_viewer.paginated_viewer import render_paginated_viewer
from dashboard.reports_viewer.report_adapter import (
    archived_report_document,
    registered_report_document,
    unavailable_report_document,
)


def create_reports_discovery_router(
    *,
    role_provider: Callable[[], str] | None = None,
    options_income_snapshot_provider: Callable[[], Mapping[str, Any]] | None = None,
    surface: str = "mobile",
) -> Any:
    try:
        from fastapi import APIRouter, HTTPException, Query
        from fastapi.responses import HTMLResponse, JSONResponse
    except Exception:  # pragma: no cover
        return None

    router = APIRouter(tags=["reports-discovery"])

    def _role() -> str:
        if role_provider:
            return str(role_provider() or "VIEWER").upper()
        return "VIEWER"

    @router.get("/api/reports")
    def get_reports_hub() -> dict[str, Any]:
        return build_reports_hub_payload(role=_role(), surface=surface)

    @router.get("/api/reports/categories")
    def get_report_categories() -> dict[str, Any]:
        hub = build_reports_hub_payload(role=_role(), surface=surface)
        return {
            "ok": hub.get("ok", False),
            "categories": [
                {"key": g["key"], "label": g["label"], "count": len(g.get("reports") or [])}
                for g in hub.get("groups") or []
            ],
            "registry_categories": hub.get("registry_categories") or [],
            "write_routes": False,
        }

    @router.get("/api/reports/audit-matrix")
    def get_report_audit_matrix() -> dict[str, Any]:
        from backend.reports_center.viewer_audit import audit_report_catalogue

        return audit_report_catalogue()

    @router.get("/api/reports/{report_id}/metadata")
    def get_report_metadata(report_id: str) -> dict[str, Any]:
        return _metadata_for(report_id, role=_role(), oi_provider=options_income_snapshot_provider)

    @router.get("/api/reports/{report_id}")
    def get_report_stub(report_id: str) -> dict[str, Any]:
        meta = _metadata_for(report_id, role=_role(), oi_provider=options_income_snapshot_provider)
        return {**meta, "body": None, "note": "Use /view for paginated HTML; this endpoint is metadata-only."}

    @router.get("/api/reports/{report_id}/view")
    def get_report_view(report_id: str) -> Any:
        viewer_base = (
            ROUTES.report_viewer
            if surface == "mobile"
            else ROUTES.mc_report_viewer
        )
        return JSONResponse(
            {
                **_metadata_for(
                    report_id,
                    role=_role(),
                    oi_provider=options_income_snapshot_provider,
                ),
                "viewer_href": f"{viewer_base}?report_code={report_id}",
                "note": "API routes return JSON. Open viewer_href for rendered HTML.",
            }
        )

    # HTML viewer entry for mobile/MC shells (query-driven)
    @router.get(ROUTES.report_viewer if surface == "mobile" else ROUTES.mc_report_viewer)
    def reports_viewer_page(
        source: str = Query("options_income"),
        report_code: str | None = Query(None),
        report_id: str | None = Query(None),
    ) -> Any:
        rid = report_id or report_code or ("options_income_executive" if source == "options_income" else "")
        if not rid:
            raise HTTPException(status_code=400, detail="report_id_required")
        if source == "reports_center" and report_id:
            document, _ = archived_report_document(report_id, role=_role())
            html = _render_document(document, surface=surface)
        elif source == "reports_center" or rid not in {
            "options_income_executive",
            "broker_executive",
        }:
            document, _ = registered_report_document(rid, role=_role())
            html = _render_document(document, surface=surface)
        else:
            html = _view_html(
                rid,
                role=_role(),
                oi_provider=options_income_snapshot_provider,
                surface=surface,
            )
            if html is None:
                document, _ = unavailable_report_document(
                    report_name=rid,
                    status="DATA_UNAVAILABLE",
                    reason="REPORT_DEPENDENCY_UNAVAILABLE",
                    producer=None,
                )
                html = _render_document(document, surface=surface)
        return HTMLResponse(html, media_type="text/html")

    return router


def _metadata_for(
    report_id: str,
    *,
    role: str,
    oi_provider: Callable[[], Mapping[str, Any]] | None,
) -> dict[str, Any]:
    rid = str(report_id or "").strip()
    if rid == "options_income_executive":
        doc = _options_income_document(oi_provider)
        if not doc:
            return {
                "ok": False,
                "report_id": rid,
                "status": "DEPENDENCY_BLOCKED",
                "readiness": "dependency_blocked",
                "reason": "options_income_unavailable_on_this_surface",
            }
        return {
            "ok": True,
            "report_id": rid,
            "title": doc.get("title"),
            "category": "financial",
            "status": "AVAILABLE",
            "readiness": "available",
            "source": "OPTIONS_INCOME_RUNTIME",
            "format": "HTML",
            "page_count": doc.get("page_count"),
            "generated_at": doc.get("generated_at"),
            "css_version": doc.get("css_version"),
            "commit_reference": doc.get("commit_reference"),
            "certification_state": "ADVISORY_ONLY",
            "api_href": f"/api/reports/{rid}",
            "viewer_href": f"{ROUTES.report_viewer}?report_code={rid}",
            "print_api_href": "/api/options-income/report.html",
            "write_routes": False,
            "advisory_only": True,
            "execution_allowed": False,
        }
    if rid == "broker_executive":
        doc = _broker_document()
        return {
            "ok": True,
            "report_id": rid,
            "title": doc.get("title"),
            "category": "risk_operations",
            "status": "AVAILABLE",
            "readiness": "advisory_only",
            "source": "BROKER_OPERATIONAL_STATE",
            "format": "HTML",
            "page_count": doc.get("page_count"),
            "generated_at": doc.get("generated_at"),
            "css_version": doc.get("css_version"),
            "commit_reference": doc.get("commit_reference"),
            "certification_state": "ADVISORY_ONLY",
            "api_href": f"/api/reports/{rid}",
            "viewer_href": f"{ROUTES.report_viewer}?report_code={rid}",
            "print_api_href": None,
            "write_routes": False,
            "advisory_only": True,
            "execution_allowed": False,
        }

    from backend.reports_center.rbac import ReportsAccessControl
    from backend.reports_center.registry import by_code
    from backend.reports_center.ui_contract import ui_report_definition

    access = ReportsAccessControl()
    if not access.can_view_catalog(role):
        return {"ok": False, "error": "reports_view_denied", "report_id": rid}
    d = by_code(rid)
    if d is None:
        return {"ok": False, "error": "not_found", "report_id": rid, "status": "NOT_FOUND"}
    row = ui_report_definition(d, role=role, access=access)
    return {
        "ok": True,
        "report_id": rid,
        "title": row.get("title"),
        "category": row.get("category"),
        "status": row.get("status"),
        "readiness": str(row.get("status") or "").lower(),
        "source": "REPORTS_CENTER",
        "format": row.get("primary_human_format"),
        "page_count": None,
        "generated_at": None,
        "pdf_supported": row.get("pdf_supported"),
        "can_generate": row.get("can_generate"),
        "view_href": None,
        "note": "Open an archived instance from the Reports library for paginated view/print.",
        "write_routes": False,
        "advisory_only": True,
    }


def _options_income_document(
    oi_provider: Callable[[], Mapping[str, Any]] | None,
) -> dict[str, Any] | None:
    if oi_provider is None:
        return None
    try:
        from backend.options.options_income_reporting import build_options_income_executive_report

        report = build_options_income_executive_report(snapshot=oi_provider())
        doc = report.get("document")
        return dict(doc) if isinstance(doc, Mapping) else None
    except Exception:
        return None


def _broker_document() -> dict[str, Any]:
    from backend.broker_reporting import build_broker_executive_report_package

    return build_broker_executive_report_package().document


def _view_html(
    report_id: str,
    *,
    role: str,
    oi_provider: Callable[[], Mapping[str, Any]] | None,
    surface: str,
) -> str | None:
    rid = str(report_id or "").strip()
    if rid not in {"options_income_executive", "broker_executive"}:
        return None
    doc = _broker_document() if rid == "broker_executive" else _options_income_document(oi_provider)
    if not doc:
        return None
    reports = ROUTES.mc_reports if surface == "mission_control" else ROUTES.mobile_reports
    home = mobile_home_href(for_surface="mission_control" if surface == "mission_control" else "mobile")
    return render_paginated_viewer(
        doc,
        reports_href=reports,
        home_href=home,
        surface=surface,
    )


def _render_document(document: Mapping[str, Any], *, surface: str) -> str:
    reports = ROUTES.mc_reports if surface == "mission_control" else ROUTES.mobile_reports
    home = mobile_home_href(
        for_surface="mission_control" if surface == "mission_control" else "mobile"
    )
    return render_paginated_viewer(
        document,
        reports_href=reports,
        home_href=home,
        surface=surface,
    )


__all__ = ["create_reports_discovery_router"]
