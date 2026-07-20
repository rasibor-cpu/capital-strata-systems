"""Phase 178 — ExecutiveFinancialReportPackage (Phase 177-backed)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.executive_reporting.management_actions import generate_management_actions
from backend.executive_reporting.narrative import generate_executive_narrative
from backend.executive_reporting.summary import build_executive_financial_summary
from backend.financial_reporting.models import deep_freeze_dict

SCHEMA_VERSION = "css.executive_financial_report_package.v1"

PERIOD_TYPES = (
    "DAILY",
    "WEEKLY",
    "MONTHLY",
    "QUARTERLY",
    "YEAR_TO_DATE",
    "ANNUAL",
    "CUSTOM",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _kpi_table(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        ("Net Profit", summary.get("net_profit")),
        ("Operating Profit", summary.get("operating_profit")),
        ("Total Revenue", summary.get("total_revenue")),
        ("Total Expenses", summary.get("total_expenses")),
        ("Total Assets", summary.get("total_assets")),
        ("Total Liabilities", summary.get("total_liabilities")),
        ("Total Equity", summary.get("total_equity")),
        ("Net Change in Cash", summary.get("net_change_in_cash")),
        ("Current Cash", summary.get("current_cash")),
        ("Target Profit", summary.get("target_profit")),
        ("Target Achieved %", summary.get("target_achieved_percentage")),
        ("Required Daily Run Rate", summary.get("required_daily_run_rate")),
        ("Projected Period-End Profit", summary.get("projected_period_end_profit")),
        ("Projected Target Variance", summary.get("projected_target_variance")),
        ("Profitability Traffic Light", summary.get("profitability_traffic_light")),
        ("Reporting Readiness", summary.get("reporting_readiness")),
    ]
    return [{"kpi": k, "value": v} for k, v in rows]


def build_executive_financial_report_package(
    phase177_package: dict[str, Any],
    *,
    report_id: str | None = None,
    report_type: str = "executive_financial_summary",
) -> dict[str, Any]:
    """Assemble the executive package exclusively from a Phase 177 package dict."""
    pkg177 = phase177_package if isinstance(phase177_package, dict) else {}
    summary = build_executive_financial_summary(pkg177)
    actions = generate_management_actions(summary=summary, phase177_package=pkg177)
    narrative = generate_executive_narrative(
        summary=summary,
        phase177_package=pkg177,
        management_actions=actions,
    )
    period = pkg177.get("reporting_period") if isinstance(pkg177.get("reporting_period"), dict) else {}
    period_type = str(period.get("period_type") or "CUSTOM")
    if period_type not in PERIOD_TYPES:
        period_type = "CUSTOM"

    package = {
        "schema_version": SCHEMA_VERSION,
        "report_id": report_id or str(uuid4()),
        "report_type": report_type,
        "generated_at": summary.get("generated_at") or _utc_now(),
        "period_type": period_type,
        "reporting_period": period,
        "currency": summary.get("currency"),
        "metadata": {
            "source_engine": "backend.financial_reporting.CanonicalFinancialReportingEngine",
            "source_report_id": pkg177.get("report_id"),
            "source_schema_version": pkg177.get("schema_version"),
            "not_audited_statutory_statements": True,
            "management_report": True,
        },
        "financial_summary": summary,
        "income_statement": pkg177.get("income_statement"),
        "balance_sheet": pkg177.get("balance_sheet"),
        "cash_flow_statement": pkg177.get("cash_flow_statement"),
        "profitability_run_rate": pkg177.get("profitability_run_rate"),
        "readiness": pkg177.get("readiness"),
        "narrative": narrative,
        "kpi_table": _kpi_table(summary),
        "management_actions": actions,
        "evidence_index": list(dict.fromkeys(summary.get("evidence_references") or [])),
        "warnings": list(dict.fromkeys(summary.get("financial_warnings") or [])),
        "blockers": list(dict.fromkeys(summary.get("financial_blockers") or [])),
        "limitations": [
            "Management reporting foundation only — not audited statutory financial statements.",
            "Derived exclusively from Phase 177 Canonical Financial Reporting Engine outputs.",
            "Missing inputs are not converted into healthy zeros.",
        ],
        "formats": {"json": True, "html": True, "pdf": True},
        "advisory_only": True,
        "trading_impact": False,
    }
    return deep_freeze_dict(package)


# Type documentation alias
ExecutiveFinancialReportPackage = dict
