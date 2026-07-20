"""Phase 178 — executive financial summary derived only from Phase 177 package."""

from __future__ import annotations

from typing import Any

from backend.financial_reporting.models import deep_freeze_dict


SCHEMA_VERSION = "css.executive_financial_summary.v1"


def build_executive_financial_summary(phase177_package: dict[str, Any] | None) -> dict[str, Any]:
    """
    Flatten Phase 177 package into an executive summary.

    Does not recalculate statements — reads Phase 177 outputs only.
    """
    pkg = phase177_package if isinstance(phase177_package, dict) else {}
    income = pkg.get("income_statement") if isinstance(pkg.get("income_statement"), dict) else {}
    totals = income.get("totals") if isinstance(income.get("totals"), dict) else {}
    balance = pkg.get("balance_sheet") if isinstance(pkg.get("balance_sheet"), dict) else {}
    assets = balance.get("assets") if isinstance(balance.get("assets"), dict) else {}
    liabilities = balance.get("liabilities") if isinstance(balance.get("liabilities"), dict) else {}
    equity = balance.get("equity") if isinstance(balance.get("equity"), dict) else {}
    cash_flow = pkg.get("cash_flow_statement") if isinstance(pkg.get("cash_flow_statement"), dict) else {}
    run = pkg.get("profitability_run_rate") if isinstance(pkg.get("profitability_run_rate"), dict) else {}
    readiness = pkg.get("readiness") if isinstance(pkg.get("readiness"), dict) else {}

    total_expenses = None
    # Prefer sum of direct costs + opex when both present (still from 177 fields, no recompute of P&L)
    direct = totals.get("total_direct_costs")
    opex = totals.get("total_operating_expenses")
    tax = totals.get("tax")
    if direct is not None or opex is not None or tax is not None:
        try:
            from decimal import Decimal

            total_expenses = format(
                (Decimal(str(direct or "0")) + Decimal(str(opex or "0")) + Decimal(str(tax or "0"))),
                "f",
            )
        except Exception:
            total_expenses = None

    summary = {
        "schema_version": SCHEMA_VERSION,
        "reporting_period": pkg.get("reporting_period"),
        "currency": pkg.get("currency"),
        "generated_at": pkg.get("generated_at"),
        "net_profit": totals.get("net_profit"),
        "operating_profit": totals.get("operating_profit"),
        "total_revenue": totals.get("total_revenue"),
        "total_expenses": total_expenses,
        "total_assets": assets.get("total_assets"),
        "total_liabilities": liabilities.get("total_liabilities"),
        "total_equity": equity.get("total_equity"),
        "net_change_in_cash": cash_flow.get("net_change_in_cash"),
        "current_cash": cash_flow.get("reported_closing_cash") or assets.get("cash_and_equivalents"),
        "target_profit": run.get("target_profit"),
        "target_achieved_percentage": run.get("percentage_of_target_achieved"),
        "required_daily_run_rate": run.get("required_daily_run_rate"),
        "actual_daily_run_rate": run.get("actual_daily_run_rate"),
        "remaining_profit_required": run.get("remaining_profit_required"),
        "projected_period_end_profit": run.get("projected_period_end_profit"),
        "projected_target_variance": run.get("projected_target_variance"),
        "profitability_traffic_light": run.get("traffic_light") or "NOT_AVAILABLE",
        "reporting_readiness": readiness.get("overall_state") or "NOT_READY",
        "reporting_readiness_score": readiness.get("overall_score"),
        "financial_blockers": list(pkg.get("blockers") or readiness.get("blocking_items") or []),
        "financial_warnings": list(pkg.get("warnings") or readiness.get("warning_items") or []),
        "financial_advisories": list(pkg.get("advisories") or readiness.get("advisories") or []),
        "data_completeness": pkg.get("data_completeness"),
        "data_freshness": pkg.get("data_freshness"),
        "evidence_references": list(pkg.get("evidence") or []),
        "balance_sheet_balanced": balance.get("balanced"),
        "cash_flow_reconciled": cash_flow.get("reconciled"),
        "source_schema_version": pkg.get("schema_version"),
        "source_report_id": pkg.get("report_id"),
        "advisory_only": True,
        "trading_impact": False,
        "not_audited_statutory_statements": True,
    }
    return deep_freeze_dict(summary)


# Back-compat alias name used in package docs
ExecutiveFinancialSummary = dict  # type alias documentation helper
