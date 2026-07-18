"""Controlled write APIs for Executive Brief distribution (outside Mission Control).

Freeze-compliant: Mission Control remains GET-only. These routes live under
``/api/v1/executive-brief/...`` and enforce server-side RBAC.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse, Response

from backend.executive_intelligence.constants import SAFETY_LOCKS
from backend.executive_intelligence.distribution import ExecutiveBriefDistributionService
from backend.executive_intelligence.print_report import render_printable_html
from backend.executive_intelligence.rbac_grants import ACTION_PRINT, ExecutiveBriefAccessControl
from backend.executive_intelligence.retrieval import MorningBriefRetrieval
from dashboard.mission_control.serializers import safe_serialize


def create_executive_brief_distribution_router(
    *,
    archive_root: Path | str | None = None,
    dist_root: Path | str | None = None,
    grant_path: Path | str | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/executive-brief", tags=["executive-brief-distribution"])
    retrieval = MorningBriefRetrieval(
        Path(archive_root) if archive_root else Path.cwd() / "artifacts/runtime_reports/morning_briefings"
    )
    access = ExecutiveBriefAccessControl(grant_path=grant_path)
    distribution = ExecutiveBriefDistributionService(root=dist_root, access=access)

    def _auth_headers(
        x_css_role: str | None,
        x_css_user_id: str | None,
    ) -> tuple[str, str]:
        return str(x_css_role or "VIEWER"), str(x_css_user_id or "anonymous")

    @router.get("/authorization")
    async def authorization_status(
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        role, user = _auth_headers(x_css_role, x_css_user_id)
        return JSONResponse(safe_serialize({**distribution.authorization_status(role=role, user_id=user), **SAFETY_LOCKS}))

    @router.post("/grants/designate")
    async def designate_staff(
        payload: dict[str, Any],
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        role, user = _auth_headers(x_css_role, x_css_user_id)
        result = access.designate_staff(
            admin_role=role,
            admin_user_id=user,
            staff_user_id=str(payload.get("staff_user_id") or ""),
            actions=list(payload.get("actions") or []),
        )
        code = 200 if result.get("status") == "OK" else 403
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.post("/grants/revoke")
    async def revoke_staff(
        payload: dict[str, Any],
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        role, user = _auth_headers(x_css_role, x_css_user_id)
        result = access.revoke_staff(
            admin_role=role,
            admin_user_id=user,
            staff_user_id=str(payload.get("staff_user_id") or ""),
        )
        code = 200 if result.get("status") == "OK" else (404 if result.get("status") == "NOT_FOUND" else 403)
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.post("/recipient-lists/{list_id}")
    async def upsert_list(
        list_id: str,
        payload: dict[str, Any],
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        role, user = _auth_headers(x_css_role, x_css_user_id)
        result = distribution.upsert_recipient_list(
            admin_role=role,
            admin_user_id=user,
            list_id=list_id,
            recipient_ids=list(payload.get("recipient_ids") or []),
        )
        code = 200 if result.get("status") == "OK" else 403
        return JSONResponse(safe_serialize(result), status_code=code)

    @router.post("/{report_date}/email")
    async def send_email(
        report_date: str,
        payload: dict[str, Any],
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        role, user = _auth_headers(x_css_role, x_css_user_id)
        brief = retrieval.by_date(report_date)
        if brief is None:
            return JSONResponse(safe_serialize({"status": "DATA UNAVAILABLE", **SAFETY_LOCKS}), status_code=404)

        # Reject direct recipient bypass attempts in API payloads
        bypass = payload.get("recipients") or payload.get("recipient_ids") or payload.get("to") or payload.get("emails")
        if bypass:
            result = distribution.send_email(
                brief=brief,
                role=role,
                user_id=user,
                list_id=str(payload.get("list_id") or ""),
                bypass_recipients=list(bypass) if isinstance(bypass, list) else [str(bypass)],
            )
            return JSONResponse(safe_serialize({k: v for k, v in result.items() if k != "pdf_bytes"}), status_code=403)

        result = distribution.send_email(
            brief=brief,
            role=role,
            user_id=user,
            list_id=str(payload.get("list_id") or ""),
        )
        code = 200 if result.get("status") in {"SENT", "NOT_CONFIGURED"} else (403 if result.get("status") == "DENIED" else 500)
        safe = {k: v for k, v in result.items() if k != "pdf_bytes"}
        return JSONResponse(safe_serialize(safe), status_code=code)

    @router.post("/{report_date}/print-audit")
    async def print_audit(
        report_date: str,
        payload: dict[str, Any],
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> JSONResponse:
        role, user = _auth_headers(x_css_role, x_css_user_id)
        brief = retrieval.by_date(report_date)
        if brief is None:
            return JSONResponse(safe_serialize({"status": "DATA UNAVAILABLE", **SAFETY_LOCKS}), status_code=404)
        auth = access.authorize(role=role, user_id=user, action=ACTION_PRINT)
        outcome = str(payload.get("outcome") or ("OK" if auth["allowed"] else "DENIED"))
        event = distribution.record_print_audit(
            brief=brief,
            role=role,
            user_id=user,
            destination=str(payload.get("destination") or "printer"),
            outcome=outcome if auth["allowed"] else "DENIED",
            failure_reason=None if auth["allowed"] else auth["reason"],
            permission_used=auth.get("permission_used"),
        )
        code = 200 if auth["allowed"] else 403
        return JSONResponse(safe_serialize({"audit": event, **SAFETY_LOCKS}), status_code=code)

    @router.get("/{report_date}/print")
    async def printable_html(
        report_date: str,
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> Response:
        role, user = _auth_headers(x_css_role, x_css_user_id)
        brief = retrieval.by_date(report_date)
        if brief is None:
            return JSONResponse(safe_serialize({"status": "DATA UNAVAILABLE", **SAFETY_LOCKS}), status_code=404)
        auth = access.authorize(role=role, user_id=user, action=ACTION_PRINT)
        if not auth["allowed"]:
            distribution.record_print_audit(
                brief=brief,
                role=role,
                user_id=user,
                destination="html_print",
                outcome="DENIED",
                failure_reason=auth["reason"],
            )
            return JSONResponse(safe_serialize({"status": "DENIED", "reason": auth["reason"], **SAFETY_LOCKS}), status_code=403)
        try:
            html = render_printable_html(brief, printed_by=user)
        except PermissionError as exc:
            return JSONResponse(safe_serialize({"status": "DENIED", "reason": str(exc), **SAFETY_LOCKS}), status_code=403)
        distribution.record_print_audit(
            brief=brief,
            role=role,
            user_id=user,
            destination="html_print",
            outcome="OK",
            permission_used=auth.get("permission_used"),
        )
        return Response(content=html, media_type="text/html; charset=utf-8")

    @router.get("/{report_date}/pdf")
    async def printable_pdf(
        report_date: str,
        x_css_role: str | None = Header(default=None),
        x_css_user_id: str | None = Header(default=None),
    ) -> Response:
        role, user = _auth_headers(x_css_role, x_css_user_id)
        brief = retrieval.by_date(report_date)
        if brief is None:
            return JSONResponse(safe_serialize({"status": "DATA UNAVAILABLE", **SAFETY_LOCKS}), status_code=404)
        result = distribution.authorize_and_render_pdf(brief=brief, role=role, user_id=user, destination="pdf_export")
        if result.get("status") != "OK":
            code = 403 if result.get("status") == "DENIED" else 500
            return JSONResponse(safe_serialize({k: v for k, v in result.items() if k != "pdf_bytes"}), status_code=code)
        return Response(
            content=result["pdf_bytes"],
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="executive_morning_brief_{report_date}.pdf"',
                "X-CSS-PDF-SHA256": result["pdf_sha256"],
            },
        )

    @router.get("/history/print")
    async def print_history() -> JSONResponse:
        return JSONResponse(safe_serialize({"items": distribution.print_history(), **SAFETY_LOCKS}))

    @router.get("/history/email")
    async def email_history() -> JSONResponse:
        return JSONResponse(safe_serialize({"items": distribution.email_history(), **SAFETY_LOCKS}))

    return router
