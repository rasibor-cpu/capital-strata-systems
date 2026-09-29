from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.app.auth.session_dependency import require_operator_session
from backend.app.reporting.export_service import export_payload
from dashboard.runtime.api_bridge import (
    DashboardStateProvider,
    get_frontend_payload,
)


def create_report_export_router(
    state_provider: DashboardStateProvider | None = None,
) -> APIRouter:
    # Same operator-session gate as the dashboard-state/Mission Control feeds
    # this exports -- any valid session, no specific commercial permission.
    # Previously unauthenticated.
    router = APIRouter(dependencies=[Depends(require_operator_session)])

    @router.get("/api/v1/report-export")
    def export_dashboard_report(
        format: str = Query(default="html"),
        section: str | None = Query(default=None),
    ) -> Response:
        frontend = get_frontend_payload(state_provider)
        payload = frontend
        title = "CSS Dashboard Report"
        stem = "css_dashboard_report"

        if section:
            sections = frontend.get("sections", {})
            if section not in sections:
                raise HTTPException(
                    status_code=404,
                    detail=f"unknown dashboard section: {section}",
                )
            payload = sections[section]
            title = f"CSS Dashboard Report — {section}"
            stem = f"css_dashboard_{section}"

        try:
            artifact = export_payload(
                title=title,
                payload=payload,
                format_name=format,
                filename_stem=stem,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return Response(
            content=artifact.content,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{artifact.filename}"'
                ),
                "X-CSS-Read-Only": "true",
            },
        )

    return router
