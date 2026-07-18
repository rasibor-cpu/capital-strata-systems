"""Shared desktop/mobile Reports UI contract (Phase 176A).

Keeps navigation categories and safe filter field maps aligned so Mission Control
and the mobile dashboard cannot drift independently. Does not alter producers,
archive paths, RBAC, or validation rules.
"""

from __future__ import annotations

from typing import Any

from backend.reports_center.registry import all_definitions, by_category, catalog_payload, category_menu

# Canonical mobile/desktop category navigation (compact labels).
REPORTS_NAV_CATEGORIES: tuple[dict[str, str], ...] = (
    {"key": "home", "label": "Report Home", "href_mobile": "/reports", "href_mc": "/mission-control/reports"},
    {"key": "latest", "label": "Latest Reports", "href_mobile": "/reports/library?view=latest", "href_mc": "/mission-control/reports#rc-library"},
    {"key": "create", "label": "Create Report", "href_mobile": "/reports/create", "href_mc": "/mission-control/reports#rc-create"},
    {"key": "library", "label": "Report Library", "href_mobile": "/reports/library", "href_mc": "/mission-control/reports#rc-library"},
    {"key": "trading_transactions", "label": "Trading & Transactions", "href_mobile": "/reports?category=trading_transactions", "href_mc": "/mission-control/reports#cat-trading_transactions"},
    {"key": "portfolio_performance", "label": "Portfolio & Performance", "href_mobile": "/reports?category=portfolio_performance", "href_mc": "/mission-control/reports#cat-portfolio_performance"},
    {"key": "accounts_cash", "label": "Accounts & Cash", "href_mobile": "/reports?category=accounts_cash", "href_mc": "/mission-control/reports#cat-accounts_cash"},
    {"key": "risk_exposure", "label": "Risk & Exposure", "href_mobile": "/reports?category=risk_exposure", "href_mc": "/mission-control/reports#cat-risk_exposure"},
    {"key": "broker_execution", "label": "Broker & Execution", "href_mobile": "/reports?category=broker_execution", "href_mc": "/mission-control/reports#cat-broker_execution"},
    {"key": "executive_intelligence", "label": "Executive Intelligence", "href_mobile": "/reports?category=executive_intelligence", "href_mc": "/mission-control/reports#cat-executive_intelligence"},
    {"key": "distribution_print_audit", "label": "Distribution & Audit", "href_mobile": "/reports?category=distribution_print_audit", "href_mc": "/mission-control/reports#cat-distribution_print_audit"},
)

# Map registry supported_scopes → safe form controls (no free-form SQL/path).
SCOPE_FIELD_MAP: dict[str, dict[str, Any]] = {
    "report_date": {"name": "report_date", "label": "Report date", "input": "date"},
    "date": {"name": "report_date", "label": "Date", "input": "date"},
    "as_of_date": {"name": "as_of_date", "label": "As-of date", "input": "date"},
    "date_range": {"name": "date_range", "label": "Date range", "input": "date_range"},
    "from_date": {"name": "from_date", "label": "From date", "input": "date"},
    "to_date": {"name": "to_date", "label": "To date", "input": "date"},
    "user": {"name": "user", "label": "User", "input": "text", "pattern": r"^[A-Za-z0-9_.:@-]{0,64}$"},
    "trader": {"name": "trader", "label": "Trader", "input": "text", "pattern": r"^[A-Za-z0-9_.:@-]{0,64}$"},
    "account": {"name": "account", "label": "Account", "input": "text"},
    "portfolio": {"name": "portfolio", "label": "Portfolio", "input": "text"},
    "broker": {"name": "broker", "label": "Broker", "input": "text"},
    "strategy": {"name": "strategy", "label": "Strategy", "input": "text"},
    "asset_class": {"name": "asset_class", "label": "Asset class", "input": "text"},
    "instrument": {"name": "instrument", "label": "Instrument", "input": "text"},
    "status": {"name": "status", "label": "Status", "input": "text"},
    "currency": {"name": "currency", "label": "Currency", "input": "text"},
    "execution_mode": {
        "name": "execution_mode",
        "label": "Paper / Live / Advisory",
        "input": "select",
        "options": ["advisory", "paper", "TEST", "LIVE"],
    },
    "mode": {
        "name": "mode",
        "label": "Ledger mode",
        "input": "select",
        "options": ["TEST", "LIVE"],
    },
    "transaction_id": {"name": "transaction_id", "label": "Transaction / ledger ID", "input": "text"},
    "ledger_txn_id": {"name": "ledger_txn_id", "label": "Ledger txn ID", "input": "text"},
    "execution_id": {"name": "execution_id", "label": "Execution ID", "input": "text"},
    "report_id": {"name": "report_id", "label": "Report ID", "input": "text"},
}


def ui_catalog(*, generatable_only: bool = False) -> dict[str, Any]:
    return catalog_payload(generatable_only=generatable_only)


def category_sections() -> list[dict[str, Any]]:
    """Category blocks with nested report definitions for interactive UIs."""
    out: list[dict[str, Any]] = []
    for meta in category_menu():
        defs = by_category(meta["key"])
        out.append(
            {
                **meta,
                "reports": [
                    {
                        "report_code": d.report_code,
                        "title": d.title,
                        "status": d.status,
                        "supported_formats": list(d.supported_formats),
                        "official_report": d.official_report,
                        "advisory_only": d.advisory_only,
                        "limitations": d.limitations,
                        "required_view_permission": d.required_view_permission,
                        "required_generate_permission": d.required_generate_permission,
                        "required_print_permission": d.required_print_permission,
                        "generatable": d.generatable,
                        "emailable": d.emailable,
                        "supported_scopes": list(d.supported_scopes),
                        "filter_fields": filter_fields_for_scopes(d.supported_scopes),
                    }
                    for d in defs
                ],
            }
        )
    return out


def filter_fields_for_scopes(scopes: tuple[str, ...] | list[str]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    for scope in scopes:
        if scope == "date_range":
            for name in ("from_date", "to_date"):
                if name not in seen:
                    fields.append(dict(SCOPE_FIELD_MAP[name]))
                    seen.add(name)
            continue
        spec = SCOPE_FIELD_MAP.get(str(scope))
        if not spec:
            continue
        name = str(spec["name"])
        if name in seen:
            continue
        fields.append(dict(spec))
        seen.add(name)
    # Always allow optional output format hint (validated against definition server-side)
    if "format" not in seen:
        fields.append(
            {
                "name": "format",
                "label": "Preferred format",
                "input": "select",
                "options": ["HTML", "JSON", "CSV", "Markdown", "PDF"],
            }
        )
    return fields


def generatable_selector_options() -> list[dict[str, Any]]:
    options = []
    for d in all_definitions():
        if not d.generatable:
            continue
        options.append(
            {
                "report_code": d.report_code,
                "title": d.title,
                "status": d.status,
                "supported_scopes": list(d.supported_scopes),
                "supported_formats": list(d.supported_formats),
                "limitations": d.limitations,
                "filter_fields": filter_fields_for_scopes(d.supported_scopes),
            }
        )
    return options


def navigation_payload(*, surface: str = "mobile") -> list[dict[str, str]]:
    key = "href_mobile" if surface == "mobile" else "href_mc"
    return [{"key": n["key"], "label": n["label"], "href": n[key]} for n in REPORTS_NAV_CATEGORIES]
