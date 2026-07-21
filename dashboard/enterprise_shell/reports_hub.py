"""Reports hub discovery payload (Phase 177H) — read-only catalogue view."""

from __future__ import annotations

from typing import Any

from backend.reports_center.rbac import ReportsAccessControl
from backend.reports_center.registry import by_category, category_menu
from backend.reports_center.ui_contract import ui_report_definition
from dashboard.enterprise_shell.routes import ROUTES, mobile_home_href


# Operator-facing hub groups (map onto registry categories + special entries).
HUB_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "key": "executive",
        "label": "Executive",
        "registry_categories": ("executive_intelligence",),
        "planned": (
            {"title": "CEO Daily Brief", "status": "COMING_SOON"},
            {"title": "Weekly Executive Report", "status": "COMING_SOON"},
            {"title": "Monthly Executive Report", "status": "COMING_SOON"},
            {"title": "Quarterly Report", "status": "COMING_SOON"},
            {"title": "Annual Report", "status": "COMING_SOON"},
        ),
    },
    {
        "key": "financial",
        "label": "Financial",
        "registry_categories": ("accounts_cash", "portfolio_performance", "treasury"),
        "planned": (
            {"title": "Income Statement", "status": "COMING_SOON"},
            {"title": "Profitability Run Rate", "status": "COMING_SOON"},
            {"title": "Premium Accounting", "status": "COMING_SOON"},
        ),
        "special": (
            {
                "report_id": "options_income_executive",
                "title": "Options Income",
                "category": "financial",
                "status": "AVAILABLE",
                "readiness": "ADVISORY_ONLY",
                "source": "OPTIONS_INCOME_RUNTIME",
                "format": "HTML",
                "api_href": "/api/reports/options_income_executive",
                "print_href": "/api/options-income/report.html",
                "metadata_href": "/api/reports/options_income_executive/metadata",
            },
        ),
    },
    {
        "key": "risk_operations",
        "label": "Risk and Operations",
        "registry_categories": ("risk_exposure", "broker_execution", "operations_system", "trading_transactions"),
        "special": (
            {
                "report_id": "broker_executive",
                "title": "Broker Operational State",
                "category": "risk_operations",
                "status": "AVAILABLE",
                "readiness": "ADVISORY_ONLY",
                "source": "BROKER_OPERATIONAL_STATE",
                "format": "HTML",
                "api_href": "/api/reports/broker_executive",
                "print_href": None,
                "metadata_href": "/api/reports/broker_executive/metadata",
            },
        ),
        "planned": (
            {"title": "Runtime Health", "status": "COMING_SOON"},
            {"title": "Operational Intelligence", "status": "COMING_SOON"},
            {"title": "Alerts and Incidents", "status": "COMING_SOON"},
        ),
    },
    {
        "key": "governance",
        "label": "Governance",
        "registry_categories": ("compliance_audit", "distribution_print_audit"),
        "planned": (
            {"title": "Certification", "status": "COMING_SOON"},
            {"title": "Data Provenance", "status": "COMING_SOON"},
            {"title": "Change and Release Reports", "status": "COMING_SOON"},
        ),
    },
)


def _status_label(status: str) -> str:
    s = str(status or "UNKNOWN").upper()
    mapping = {
        "AVAILABLE": "available",
        "AVAILABLE_WITH_LIMITATIONS": "available",
        "COMING_SOON": "not_yet_implemented",
        "DATA_UNAVAILABLE": "dependency_blocked",
        "DISABLED": "not_yet_implemented",
        "FAILED": "failed",
        "STALE": "stale",
        "GENERATING": "generating",
    }
    return mapping.get(s, "unavailable")


def build_reports_hub_payload(
    *,
    role: str = "VIEWER",
    surface: str = "mobile",
) -> dict[str, Any]:
    """Read-only hub catalogue — never fabricates financial report bodies."""
    access = ReportsAccessControl()
    role_u = str(role or "VIEWER").upper()
    if not access.can_view_catalog(role_u):
        return {
            "ok": False,
            "error": "reports_view_denied",
            "groups": [],
            "schema_version": "css.reports_hub.v1",
        }

    reports_home = ROUTES.mobile_reports if surface == "mobile" else ROUTES.mc_reports
    viewer_base = ROUTES.report_viewer if surface == "mobile" else ROUTES.mc_report_viewer

    groups_out: list[dict[str, Any]] = []
    for group in HUB_GROUPS:
        cards: list[dict[str, Any]] = []
        for cat in group.get("registry_categories") or ():
            for d in by_category(str(cat)):
                row = ui_report_definition(d, role=role_u, access=access)
                code = str(row.get("report_code") or row.get("report_type") or "")
                status = str(row.get("status") or "COMING_SOON")
                view_href = (
                    f"{viewer_base}?source=reports_center&report_code={code}"
                    if code
                    else None
                )
                cards.append(
                    {
                        "report_id": code or None,
                        "title": row.get("title"),
                        "category": group["key"],
                        "registry_category": cat,
                        "status": status,
                        "readiness": _status_label(status),
                        "source": "REPORTS_CENTER",
                        "format": row.get("primary_human_format") or "HTML",
                        "page_count": None,
                        "generated_at": None,
                        "last_successful_generation": None,
                        "data_freshness": None,
                        "certification_state": None,
                        "view_href": view_href,
                        "viewer_href": view_href,
                        "rendered_href": view_href,
                        "report_page_href": view_href,
                        "api_href": f"/api/reports/{code}" if code else None,
                        "export_href": f"/api/v1/reports/{{id}}/pdf" if row.get("pdf_supported") else None,
                        "open_action": "view" if view_href else "none",
                        "export_action": "pdf" if row.get("pdf_supported") else "none",
                        "can_generate": bool(row.get("can_generate")),
                    }
                )
        for special in group.get("special") or ():
            card = dict(special)
            report_id = str(card.get("report_id") or "")
            viewer_href = f"{viewer_base}?report_code={report_id}"
            card["api_href"] = card.get("metadata_href")
            card["viewer_href"] = viewer_href
            card["rendered_href"] = viewer_href
            card["report_page_href"] = viewer_href
            card["view_href"] = viewer_href
            card["print_href"] = None
            card["readiness"] = _status_label(str(card.get("status") or ""))
            cards.append(card)
        for planned in group.get("planned") or ():
            # Skip planned titles that already appear from registry
            titles = {str(c.get("title") or "").lower() for c in cards}
            if str(planned.get("title") or "").lower() in titles:
                continue
            cards.append(
                {
                    "report_id": None,
                    "title": planned.get("title"),
                    "category": group["key"],
                    "status": planned.get("status") or "COMING_SOON",
                    "readiness": _status_label(str(planned.get("status") or "COMING_SOON")),
                    "source": "HUB_PLANNED",
                    "format": None,
                    "view_href": None,
                    "export_href": None,
                    "open_action": "none",
                    "export_action": "none",
                    "can_generate": False,
                }
            )
        groups_out.append(
            {
                "key": group["key"],
                "label": group["label"],
                "reports": cards,
            }
        )

    return {
        "ok": True,
        "schema_version": "css.reports_hub.v1",
        "surface": surface,
        "reports_home": reports_home,
        "home_href": mobile_home_href(
            for_surface="mobile" if surface == "mobile" else "mission_control"
        ),
        "registry_categories": category_menu(),
        "groups": groups_out,
        "write_routes": False,
        "advisory_only": True,
        "execution_allowed": False,
    }


__all__ = ["HUB_GROUPS", "build_reports_hub_payload"]
