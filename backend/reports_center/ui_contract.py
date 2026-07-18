"""Shared desktop/mobile Reports UI contract (Phase 176A).

Keeps navigation categories and safe filter field maps aligned so Mission Control
and the mobile dashboard cannot drift independently. Does not alter producers,
archive paths, RBAC, or validation rules.
"""

from __future__ import annotations

from typing import Any

from backend.reports_center.capabilities import evaluate_report_capabilities, ui_report_definition
from backend.reports_center.rbac import ReportsAccessControl
from backend.reports_center.registry import all_definitions, by_category, catalog_payload, category_menu

# Static Reports menu entries (not category disclosures).
_REPORTS_NAV_STATIC: tuple[dict[str, str], ...] = (
    {"key": "home", "label": "Report Home", "href_mobile": "/reports", "href_mc": "/mission-control/reports"},
    {"key": "latest", "label": "Latest Reports", "href_mobile": "/reports/library?view=latest", "href_mc": "/mission-control/reports#rc-library"},
    {"key": "create", "label": "Create Report", "href_mobile": "/reports/create", "href_mc": "/mission-control/reports#rc-create"},
    {"key": "library", "label": "Report Library", "href_mobile": "/reports/library", "href_mc": "/mission-control/reports#rc-library"},
)


def _reports_nav_categories() -> tuple[dict[str, str], ...]:
    """Build full category deep-links from the registry menu (keeps MC/mobile in sync).

    Mission Control anchors use ``#cat-{key}`` which maps to disclosure wrapper ids
    (``id="cat-{key}"``) and opens the matching panel via CSSUIInteraction.
    """
    entries = list(_REPORTS_NAV_STATIC)
    for meta in category_menu():
        key = str(meta["key"])
        label = str(meta["label"])
        entries.append(
            {
                "key": key,
                "label": label,
                "href_mobile": f"/reports?category={key}",
                "href_mc": f"/mission-control/reports#cat-{key}",
            }
        )
    return tuple(entries)


# Lazy-friendly alias: call navigation_payload() / iterate via REPORTS_NAV_CATEGORIES property helper.
REPORTS_NAV_CATEGORIES = _reports_nav_categories()  # evaluated at import; category_menu is static registry

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


def _ui_row(d: Any, *, role: str, access: ReportsAccessControl) -> dict[str, Any]:
    row = ui_report_definition(d, role=role, access=access)
    row["filter_fields"] = filter_fields_for_scopes(d.supported_scopes)
    return row


def category_sections(*, role: str = "VIEWER") -> list[dict[str, Any]]:
    """Category blocks with nested canonical UI report definitions."""
    access = ReportsAccessControl()
    role_u = str(role or "VIEWER").upper()
    out: list[dict[str, Any]] = []
    for meta in category_menu():
        defs = by_category(meta["key"])
        out.append(
            {
                **meta,
                "reports": [_ui_row(d, role=role_u, access=access) for d in defs],
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


def generatable_selector_options(*, role: str = "VIEWER") -> list[dict[str, Any]]:
    """Reports the user may legitimately generate (server-side capability eval)."""
    access = ReportsAccessControl()
    role_u = str(role or "VIEWER").upper()
    options: list[dict[str, Any]] = []
    for d in all_definitions():
        row = _ui_row(d, role=role_u, access=access)
        if not row.get("can_generate"):
            continue
        options.append(row)
    return options


def capability_parity_payload(*, role: str) -> dict[str, Any]:
    """Desktop/mobile shared capability snapshot for a role."""
    access = ReportsAccessControl()
    role_u = str(role or "VIEWER").upper()
    rows = [
        evaluate_report_capabilities(d, role=role_u, access=access)
        for d in all_definitions()
    ]
    return {
        "role": role_u,
        "reports": rows,
        "generatable_count": sum(1 for r in rows if r.get("can_generate")),
        "available_generatable": sum(
            1 for r in rows if r.get("can_generate") and r.get("status") == "AVAILABLE"
        ),
        "available_with_limitations_generatable": sum(
            1
            for r in rows
            if r.get("can_generate") and r.get("status") == "AVAILABLE_WITH_LIMITATIONS"
        ),
    }


def navigation_payload(*, surface: str = "mobile") -> list[dict[str, str]]:
    key = "href_mobile" if surface == "mobile" else "href_mc"
    return [{"key": n["key"], "label": n["label"], "href": n[key]} for n in REPORTS_NAV_CATEGORIES]
