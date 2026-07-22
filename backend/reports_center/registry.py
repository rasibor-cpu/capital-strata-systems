"""Canonical report registry lookups."""

from __future__ import annotations

from typing import Any

from backend.reports_center.catalogue import CATALOGUE
from backend.reports_center.definition import CSSReportDefinition


def all_definitions() -> tuple[CSSReportDefinition, ...]:
    return CATALOGUE


def by_code(report_code: str) -> CSSReportDefinition | None:
    code = str(report_code or "").strip()
    for item in CATALOGUE:
        if item.report_code == code:
            return item
    return None


def by_category(category: str) -> list[CSSReportDefinition]:
    cat = str(category or "").strip()
    return [i for i in CATALOGUE if i.category == cat]


def catalog_payload(
    *,
    category: str | None = None,
    status: str | None = None,
    q: str | None = None,
    generatable_only: bool = False,
) -> dict[str, Any]:
    items = list(CATALOGUE)
    if category:
        items = [i for i in items if i.category == category]
    if status:
        items = [i for i in items if i.status == status]
    if generatable_only:
        items = [i for i in items if i.generatable]
    if q:
        needle = q.lower()
        items = [
            i
            for i in items
            if needle in i.title.lower()
            or needle in i.report_code.lower()
            or needle in i.description.lower()
            or needle in i.category.lower()
        ]
    by_cat: dict[str, int] = {}
    for i in CATALOGUE:
        by_cat[i.category] = by_cat.get(i.category, 0) + 1
    from backend.product_honesty import catalogue_honesty_summary

    honesty = catalogue_honesty_summary()
    return {
        "schema_version": "css.report_catalog.v1",
        "count": len(items),
        "total_registered": len(CATALOGUE),
        "counts_by_category": by_cat,
        "reports": [i.as_dict() for i in items],
        # AR-017 / AR-047 Gate 2 honesty — registered catalogue ≠ delivered suite
        "honesty": honesty,
        "generatable_count": honesty["generatable_count"],
        "coming_soon_count": honesty["coming_soon_count"],
        "mvp_eligible_count": honesty["mvp_eligible_count"],
        "registered_implies_delivered": False,
        "board_investor_regulatory_scope": "OUT_OF_SCOPE",
        "customer_banner": honesty["customer_banner"],
        "certification_claimed": False,
        "execution_allowed": False,
    }


def category_menu() -> list[dict[str, Any]]:
    labels = {
        "executive_intelligence": "Executive Intelligence",
        "trading_transactions": "Trading & Transactions",
        "accounts_cash": "Accounts & Cash",
        "portfolio_performance": "Portfolio & Performance",
        "risk_exposure": "Risk & Exposure",
        "broker_execution": "Broker & Execution",
        "treasury": "Treasury",
        "compliance_audit": "Compliance & Audit",
        "operations_system": "Operations & System",
        "distribution_print_audit": "Distribution & Print Audit",
    }
    out = []
    for key, label in labels.items():
        defs = by_category(key)
        out.append(
            {
                "key": key,
                "label": label,
                "count": len(defs),
                "available": sum(1 for d in defs if d.status in {"AVAILABLE", "AVAILABLE_WITH_LIMITATIONS"}),
                "coming_soon": sum(1 for d in defs if d.status == "COMING_SOON"),
            }
        )
    return out
