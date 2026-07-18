"""Controlled write/read APIs for Institutional Reports Center.

Mission Control remains GET-only. Mutations and print delivery live under
``/api/v1/reports/...``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import HTMLResponse, JSONResponse, Response

from backend.reports_center.constants import SAFETY_LOCKS
from backend.reports_center.registry import by_code, catalog_payload
from backend.reports_center.service import ReportsCenterService
from dashboard.mission_control.serializers import safe_serialize


def create_reports_center_router(
    *,
    repo_root: Path | str | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/reports", tags=["reports-center"])
    service = ReportsCenterService(repo_root=repo_root)

    def _auth(x_css_role: str | None, x_css_user_id: str | None) -> tuple[str, str]:
        return str(x_css_role or "VIEWER"), str(x_css_user_id or "anonymous")

    @router.get("/authorization")
    async def authorization(
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        role, user = _auth(x_css_role, x_css_user_id)
        return JSONResponse(safe_serialize({**service.access.authorization_status(role, user), **SAFETY_LOCKS}))

    @router.get("/catalog")
    async def catalog(
        category: str | None = None,
        status: str | None = None,
        q: str | None = None,
        generatable_only: bool = False,
        x_css_role: str | None = Header(default=None),
    ) -> JSONResponse:
        role = str(x_css_role or "VIEWER")
        if not service.access.can_view_catalog(role):
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        return JSONResponse(
            safe_serialize(catalog_payload(category=category, status=status, q=q, generatable_only=generatable_only))
        )

    @router.get("/definitions/{report_code}")
    async def definition(report_code: str, x_css_role: str | None = Header(default=None)) -> JSONResponse:
        role = str(x_css_role or "VIEWER")
        item = by_code(report_code)
        if item is None:
            return JSONResponse(safe_serialize({"status": "NOT_FOUND"}), status_code=404)
        if not service.access.can_view_report(role, item.required_view_permission):
            return JSONResponse(safe_serialize({"status": "DENIED"}), status_code=403)
        return JSONResponse(safe_serialize({"status": "OK", "definition": item.as_dict(), **SAFETY_LOCKS}))

    @router.get("/readiness/{report_code}")
    async def readiness(report_code: str, x_css_role: str | None = Header(default=None)) -> JSONResponse:
        return JSONResponse(safe_serialize(service.readiness(report_code, role=str(x_css_role or "VIEWER"))))

    @router.get("/home")
    async def home(x_css_role: str | None = Header(default=None)) -> JSONResponse:
        role = str(x_css_role or "VIEWER")
        if not service.access.can_view_catalog(role):
            return JSONResponse(safe_serialize({"status": "DENIED"}), status_code=403)
        return JSONResponse(safe_serialize(service.home(role=role)))

    @router.get("")
    async def list_reports(
        category: str | None = None,
        report_type: str | None = None,
        status: str | None = None,
        report_id: str | None = None,
        x_css_role: str | None = Header(default=None),
    ) -> JSONResponse:
        return JSONResponse(
            safe_serialize(
                service.list_library(
                    filters={
                        "category": category,
                        "report_type": report_type,
                        "status": status,
                        "report_id": report_id,
                    },
                    role=str(x_css_role or "VIEWER"),
                )
            )
        )

    @router.post("/generate")
    async def generate(
        payload: dict[str, Any],
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        role, user = _auth(x_css_role, x_css_user_id)
        # Reject unsafe bypass keys
        for banned in ("sql", "path", "filesystem", "recipients", "to", "cc", "bcc"):
            if banned in payload:
                return JSONResponse(
                    safe_serialize({"status": "DENIED", "reason": f"banned_field:{banned}", **SAFETY_LOCKS}),
                    status_code=400,
                )
        result = service.generate(
            str(payload.get("report_code") or payload.get("report_type") or ""),
            filters=dict(payload.get("filters") or {}),
            role=role,
            user_id=user,
            persist=bool(payload.get("persist", True)),
        )
        code = 200 if result.get("status") == "OK" else (403 if result.get("status") == "DENIED" else 400)
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.get("/{report_id}")
    async def get_report(report_id: str, x_css_role: str | None = Header(default=None)) -> JSONResponse:
        result = service.retrieve(report_id, role=str(x_css_role or "VIEWER"))
        code = 200 if result.get("status") == "OK" else (403 if result.get("status") == "DENIED" else 404)
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.get("/{report_id}/versions")
    async def versions(report_id: str, x_css_role: str | None = Header(default=None)) -> JSONResponse:
        result = service.retrieve(report_id, role=str(x_css_role or "VIEWER"))
        if result.get("status") != "OK":
            code = 403 if result.get("status") == "DENIED" else 404
            return JSONResponse(safe_serialize(result), status_code=code)
        report = result["report"]
        vers = service.archive.versions(
            str(report.get("report_family") or report.get("category") or "unknown"),
            str(report.get("report_type") or ""),
            str(report.get("report_date") or ""),
        )
        return JSONResponse(safe_serialize({"status": "OK", "report_id": report_id, "versions": vers, **SAFETY_LOCKS}))

    @router.get("/{report_id}/print")
    async def print_html(
        report_id: str,
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> Response:
        role, user = _auth(x_css_role, x_css_user_id)
        result = service.printable_html(report_id, role=role, user_id=user)
        if result.get("status") != "OK":
            code = 403 if result.get("status") == "DENIED" else 404
            return JSONResponse(safe_serialize(result), status_code=code)
        return HTMLResponse(str(result.get("html") or ""))

    @router.get("/{report_id}/pdf")
    async def pdf_info(
        report_id: str,
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        """PDF bytes for executive brief remain on /api/v1/executive-brief; others return guidance."""
        role, user = _auth(x_css_role, x_css_user_id)
        info = service.print_info(report_id, role=role, user_id=user)
        if info.get("status") != "OK":
            code = 403 if info.get("status") == "DENIED" else 404
            return JSONResponse(safe_serialize(info), status_code=code)
        data = service.archive.retrieve(report_id) or {}
        if data.get("report_type") == "daily_executive_brief" or str(report_id).startswith("cssrpt_executive_"):
            date = str(data.get("report_date") or "")
            return JSONResponse(
                safe_serialize(
                    {
                        **info,
                        "pdf_bytes_endpoint": f"/api/v1/executive-brief/{date}/pdf",
                        "note": "Executive brief PDF served by Phase 175 distribution API.",
                    }
                )
            )
        return JSONResponse(
            safe_serialize(
                {
                    **info,
                    "pdf_status": "HTML_PRINT_FALLBACK",
                    "note": "Use printable HTML; dedicated PDF renderer is available for executive briefs.",
                    "print_html": f"/api/v1/reports/{report_id}/print",
                }
            )
        )

    @router.get("/{report_id}/audit")
    async def audit(report_id: str, x_css_role: str | None = Header(default=None)) -> JSONResponse:
        result = service.audit_history(report_id, role=str(x_css_role or "VIEWER"))
        code = 200 if result.get("status") == "OK" else 403
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.get("/{report_id}/export/json")
    async def export_json(
        report_id: str,
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        role, user = _auth(x_css_role, x_css_user_id)
        result = service.export_json(report_id, role=role, user_id=user)
        code = 200 if result.get("status") == "OK" else (403 if result.get("status") == "DENIED" else 404)
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.post("/{report_id}/print-audit")
    async def print_audit(
        report_id: str,
        payload: dict[str, Any] | None = None,
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        role, user = _auth(x_css_role, x_css_user_id)
        info = service.print_info(report_id, role=role, user_id=user)
        if info.get("status") != "OK":
            code = 403 if info.get("status") == "DENIED" else 404
            return JSONResponse(safe_serialize(info), status_code=code)
        # Explicit print-audit event (in addition to printable_html audit)
        data = service.archive.retrieve(report_id) or {}
        service.audit.record(
            action="print_audit",
            outcome="OK",
            actor_id=user,
            actor_role=role,
            report_id=report_id,
            report_type=str(data.get("report_type") or ""),
            report_hash=str(data.get("report_hash") or ""),
            destination_class=str((payload or {}).get("destination_class") or "LOCAL_PRINTER"),
            official=str(data.get("report_status") or "").upper() == "FINAL",
        )
        return JSONResponse(safe_serialize({"status": "OK", **SAFETY_LOCKS}))

    @router.post("/{report_id}/verify-integrity")
    async def verify(
        report_id: str,
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        role, user = _auth(x_css_role, x_css_user_id)
        result = service.verify_integrity(report_id, role=role, user_id=user)
        code = 200 if result.get("status") in {"OK", "MISMATCH", "NOT_FOUND"} and result.get("status") != "DENIED" else 403
        if result.get("status") == "DENIED":
            code = 403
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.post("/{report_id}/email")
    async def email_disabled(
        report_id: str,
        payload: dict[str, Any] | None = None,
        x_css_role: str | None = Header(default=None),
    ) -> JSONResponse:
        _ = (report_id, payload, x_css_role)
        return JSONResponse(
            safe_serialize(
                {
                    "status": "EMAIL_DISABLED",
                    "reason": "Report-family email is EMAIL_DISABLED by default. "
                    "Daily Executive Brief email remains on /api/v1/executive-brief (Phase 175).",
                    **SAFETY_LOCKS,
                }
            ),
            status_code=403,
        )

    return router
