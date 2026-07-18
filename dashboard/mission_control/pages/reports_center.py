from __future__ import annotations

from dashboard.mission_control.pages._components import detail_table, metric_grid, page_header, warning_banner


def render(state: dict) -> str:
    """Reports Center landing — catalogue-driven, permission-aware."""
    try:
        from backend.reports_center.service import ReportsCenterService

        home = ReportsCenterService().home(role="ADMIN")
    except Exception as exc:
        return (
            page_header("Reports", "Institutional Reports Center")
            + warning_banner(f"Reports Center unavailable: {type(exc).__name__}", status="bad")
        )

    cats = {c["label"]: c["count"] for c in home.get("categories") or []}
    recent = home.get("recent_reports") or []
    failed = home.get("report_generation_failures") or []
    freq = [
        {"code": r.get("report_code"), "title": r.get("title"), "status": r.get("status")}
        for r in (home.get("frequently_used") or [])[:10]
    ]
    recent_rows = [
        {
            "report_id": r.get("report_id"),
            "type": r.get("report_type"),
            "status": r.get("report_status"),
            "date": r.get("report_date"),
        }
        for r in recent[:8]
    ] or [{"report_id": "None archived yet"}]
    failed_rows = [
        {
            "report_id": r.get("report_id"),
            "type": r.get("report_type"),
            "status": r.get("report_status"),
        }
        for r in failed[:8]
    ] or [{"report_id": "None"}]
    auth = home.get("authorization") or {}
    return (
        page_header(
            "Reports",
            "Canonical gateway for printable, downloadable, archived, and distributable CSS reports.",
        )
        + warning_banner(
            "Advisory-only Reports Center. Live trading blocked. Server-side RBAC mandatory.",
            status="warn",
        )
        + metric_grid(
            (
                ("Registered Reports", home.get("total_registered"), "neutral"),
                ("Archive Recent", home.get("archive_health", {}).get("recent_count"), "neutral"),
                ("Generation Failures", home.get("archive_health", {}).get("failed_count"), "warn" if failed else "good"),
                ("reports_view", auth.get("reports_view"), "good" if auth.get("reports_view") else "bad"),
                ("reports_generate", auth.get("reports_generate"), "good" if auth.get("reports_generate") else "bad"),
                ("Email Default", home.get("email_policy_default"), "neutral"),
            )
        )
        + detail_table("Report Categories", cats)
        + detail_table("Frequently Used / Generatable", freq)
        + detail_table("Latest Daily Executive Brief", home.get("latest_daily_executive_brief") or {"status": "UNAVAILABLE"})
        + detail_table("Recent Reports", recent_rows)
        + detail_table("Report Generation Failures", failed_rows)
        + detail_table(
            "API Gateway",
            {
                "catalog": "GET /mission-control/api/reports/catalog",
                "home": "GET /mission-control/api/reports/home",
                "generate": "POST /api/v1/reports/generate",
                "library": "GET /api/v1/reports",
                "print": "GET /api/v1/reports/{report_id}/print",
                "note": "Mission Control is GET-only; controlled writes use /api/v1/reports.",
            },
        )
        + detail_table(
            "Create Report (canonical)",
            {
                "flow": "Select report_code from catalogue → readiness → filters → POST /api/v1/reports/generate",
                "safety": "Unsafe filters (paths/SQL/code) rejected server-side",
            },
        )
        + warning_banner(
            "Unsupported catalogue entries remain COMING_SOON / DATA_UNAVAILABLE — no fabricated statements.",
            status="good",
        )
    )
