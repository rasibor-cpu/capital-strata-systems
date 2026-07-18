"""Controlled write/read APIs for Institutional Reports Center.

Mission Control remains GET-only. Mutations and print delivery live under
``/api/v1/reports/...``.

Phase 176D: identity comes from the canonical authorization context
(session bridge and/or trusted internal headers). No silent VIEWER/ADMIN
substitution; empty user_id is never treated as 00000.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from backend.reports_center.constants import SAFETY_LOCKS
from backend.reports_center.registry import by_code, catalog_payload
from backend.reports_center.service import ReportsCenterService
from backend.security.auth_diagnostics import log_authorization_denial
from dashboard.auth.session_bridge import resolve_authorization_context
from dashboard.mission_control.serializers import safe_serialize


def create_reports_center_router(
    *,
    repo_root: Path | str | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/reports", tags=["reports-center"])
    service = ReportsCenterService(repo_root=repo_root)

    def _resolve(request: Request, *, permission: str = "reports_view"):
        auth = resolve_authorization_context(channel="api_v1_reports", request=request)
        if not auth.authenticated or not auth.active:
            log_authorization_denial(
                route=str(request.url.path),
                auth=auth,
                permission_requested=permission,
                denial_reason=auth.denial_reason or "not_authenticated",
            )
        return auth

    @router.get("/authorization")
    async def authorization(request: Request) -> JSONResponse:
        auth = _resolve(request, permission="reports_view")
        return JSONResponse(safe_serialize(auth.reports_authorization()))

    @router.get("/catalog")
    async def catalog(
        request: Request,
        category: str | None = None,
        status: str | None = None,
        q: str | None = None,
        generatable_only: bool = False,
    ) -> JSONResponse:
        auth = _resolve(request)
        if not auth.authenticated or not service.access.can_view_catalog(auth.role):
            return JSONResponse(
                safe_serialize({"status": "DENIED", **auth.reports_authorization(), **SAFETY_LOCKS}),
                status_code=403,
            )
        return JSONResponse(
            safe_serialize(catalog_payload(category=category, status=status, q=q, generatable_only=generatable_only))
        )

    @router.get("/definitions/{report_code}")
    async def definition(report_code: str, request: Request) -> JSONResponse:
        auth = _resolve(request)
        item = by_code(report_code)
        if item is None:
            return JSONResponse(safe_serialize({"status": "NOT_FOUND"}), status_code=404)
        if not auth.authenticated or not service.access.can_view_report(auth.role, item.required_view_permission):
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        return JSONResponse(safe_serialize({"status": "OK", "definition": item.as_dict(), **SAFETY_LOCKS}))

    @router.get("/readiness/{report_code}")
    async def readiness(report_code: str, request: Request) -> JSONResponse:
        auth = _resolve(request)
        if not auth.authenticated:
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        return JSONResponse(safe_serialize(service.readiness(report_code, role=auth.role)))

    @router.get("/home")
    async def home(request: Request) -> JSONResponse:
        auth = _resolve(request)
        if not auth.authenticated or not service.access.can_view_catalog(auth.role):
            return JSONResponse(safe_serialize({"status": "DENIED", **auth.reports_authorization()}), status_code=403)
        payload = service.home(role=auth.role, user_id=auth.user_id)
        payload["authorization"] = auth.reports_authorization()
        return JSONResponse(safe_serialize(payload))

    @router.get("")
    async def list_reports(
        request: Request,
        category: str | None = None,
        report_type: str | None = None,
        status: str | None = None,
        report_id: str | None = None,
    ) -> JSONResponse:
        auth = _resolve(request)
        if not auth.authenticated:
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        return JSONResponse(
            safe_serialize(
                service.list_library(
                    filters={
                        "category": category,
                        "report_type": report_type,
                        "status": status,
                        "report_id": report_id,
                    },
                    role=auth.role,
                )
            )
        )

    @router.post("/generate")
    async def generate(request: Request, payload: dict[str, Any]) -> JSONResponse:
        auth = _resolve(request, permission="reports_generate")
        if not auth.authenticated:
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        for banned in ("sql", "path", "filesystem", "recipients", "to", "cc", "bcc"):
            if banned in payload:
                return JSONResponse(
                    safe_serialize({"status": "DENIED", "reason": f"banned_field:{banned}", **SAFETY_LOCKS}),
                    status_code=400,
                )
        result = service.generate(
            str(payload.get("report_code") or payload.get("report_type") or ""),
            filters=dict(payload.get("filters") or {}),
            role=auth.role,
            user_id=auth.user_id,
            persist=bool(payload.get("persist", True)),
        )
        code = 200 if result.get("status") == "OK" else (403 if result.get("status") == "DENIED" else 400)
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.get("/{report_id}")
    async def get_report(report_id: str, request: Request) -> JSONResponse:
        auth = _resolve(request)
        if not auth.authenticated:
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        result = service.retrieve(report_id, role=auth.role)
        code = 200 if result.get("status") == "OK" else (403 if result.get("status") == "DENIED" else 404)
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.get("/{report_id}/versions")
    async def versions(report_id: str, request: Request) -> JSONResponse:
        auth = _resolve(request)
        if not auth.authenticated:
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        result = service.retrieve(report_id, role=auth.role)
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
    async def print_html(report_id: str, request: Request) -> Response:
        auth = _resolve(request, permission="reports_print")
        if not auth.authenticated:
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        result = service.printable_html(report_id, role=auth.role, user_id=auth.user_id)
        if result.get("status") != "OK":
            code = 403 if result.get("status") == "DENIED" else 404
            return JSONResponse(safe_serialize(result), status_code=code)
        return HTMLResponse(str(result.get("html") or ""))

    @router.get("/{report_id}/pdf")
    async def pdf_download(report_id: str, request: Request) -> Response:
        auth = _resolve(request, permission="reports_print")
        if not auth.authenticated:
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        result = service.pdf_bytes(report_id, role=auth.role, user_id=auth.user_id)
        if result.get("status") == "BRIDGE":
            return JSONResponse(safe_serialize(result))
        if result.get("status") == "OK" and result.get("pdf_bytes"):
            return Response(
                content=result["pdf_bytes"],
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{result.get("filename") or (report_id + ".pdf")}"'
                },
            )
        code = 403 if result.get("status") == "DENIED" else (404 if result.get("status") == "NOT_FOUND" else 409)
        return JSONResponse(safe_serialize({k: v for k, v in result.items() if k != "pdf_bytes"}), status_code=code)

    @router.get("/{report_id}/audit")
    async def audit(report_id: str, request: Request) -> JSONResponse:
        auth = _resolve(request, permission="reports_audit_view")
        if not auth.authenticated:
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        result = service.audit_history(report_id, role=auth.role)
        code = 200 if result.get("status") == "OK" else 403
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.get("/{report_id}/export/json")
    async def export_json(report_id: str, request: Request) -> JSONResponse:
        auth = _resolve(request, permission="reports_export")
        if not auth.authenticated:
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        result = service.export_json(report_id, role=auth.role, user_id=auth.user_id)
        code = 200 if result.get("status") == "OK" else (403 if result.get("status") == "DENIED" else 404)
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.post("/{report_id}/print-audit")
    async def print_audit(
        report_id: str,
        request: Request,
        payload: dict[str, Any] | None = None,
    ) -> JSONResponse:
        auth = _resolve(request, permission="reports_print")
        if not auth.authenticated:
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        info = service.print_info(report_id, role=auth.role, user_id=auth.user_id)
        if info.get("status") != "OK":
            code = 403 if info.get("status") == "DENIED" else 404
            return JSONResponse(safe_serialize(info), status_code=code)
        data = service.archive.retrieve(report_id) or {}
        service.audit.record(
            action="print_audit",
            outcome="OK",
            actor_id=auth.user_id,
            actor_role=auth.role,
            report_id=report_id,
            report_type=str(data.get("report_type") or ""),
            report_hash=str(data.get("report_hash") or ""),
            destination_class=str((payload or {}).get("destination_class") or "LOCAL_PRINTER"),
            official=str(data.get("report_status") or "").upper() == "FINAL",
        )
        return JSONResponse(safe_serialize({"status": "OK", **SAFETY_LOCKS}))

    @router.post("/{report_id}/verify-integrity")
    async def verify(report_id: str, request: Request) -> JSONResponse:
        auth = _resolve(request, permission="reports_admin")
        if not auth.authenticated:
            return JSONResponse(safe_serialize({"status": "DENIED", **SAFETY_LOCKS}), status_code=403)
        result = service.verify_integrity(report_id, role=auth.role, user_id=auth.user_id)
        code = 200 if result.get("status") in {"OK", "MISMATCH", "NOT_FOUND"} and result.get("status") != "DENIED" else 403
        if result.get("status") == "DENIED":
            code = 403
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.post("/{report_id}/email")
    async def email_disabled(report_id: str, request: Request, payload: dict[str, Any] | None = None) -> JSONResponse:
        _ = (report_id, payload, request)
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
