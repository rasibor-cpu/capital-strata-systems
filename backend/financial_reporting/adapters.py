"""
Phase 177 helpers — build FinancialDataContract from Mission Control–shaped state.

Read-only mapping. Never invent healthy zeros for missing money fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.financial_reporting.data_contracts import FinancialDataContract
from backend.financial_reporting.models import FinancialAmount, MissingReason
from backend.financial_reporting.periods import month_to_date


def _amt_from_state(value: Any) -> FinancialAmount:
    if value is None:
        return FinancialAmount.missing(MissingReason.MISSING)
    if isinstance(value, str) and value.strip().upper() in {"UNAVAILABLE", "N/A", "NA", ""}:
        return FinancialAmount.missing(MissingReason.UNAVAILABLE)
    try:
        return FinancialAmount.of(value)
    except Exception:
        return FinancialAmount.missing(MissingReason.UNAVAILABLE)


def _split_signed(
    amt: FinancialAmount,
) -> tuple[FinancialAmount, FinancialAmount]:
    """Split a signed PnL into positive gain and positive loss lines (no double-count)."""
    if not amt.present:
        missing = FinancialAmount.missing(amt.reason)
        return missing, missing
    val = amt.value
    if val > 0:
        return FinancialAmount.of(val), FinancialAmount.zero()
    if val < 0:
        return FinancialAmount.zero(), FinancialAmount.of(abs(val))
    return FinancialAmount.zero(), FinancialAmount.zero()


def contract_from_mission_control_state(state: dict[str, Any] | None) -> FinancialDataContract:
    """
    Map available portfolio / reporting evidence into the Phase 177 contract.

    Missing sections remain missing. Does not touch brokers or execution.
    """
    raw = state if isinstance(state, dict) else {}
    portfolio = raw.get("portfolio") if isinstance(raw.get("portfolio"), dict) else {}
    reporting = raw.get("institutional_reporting") if isinstance(raw.get("institutional_reporting"), dict) else {}
    fr = raw.get("financial_reporting") if isinstance(raw.get("financial_reporting"), dict) else {}

    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    period = month_to_date(as_of)

    # Prefer explicit financial_reporting block when present (tests / future producers).
    if fr:
        contract = FinancialDataContract.from_mapping(fr)
        if contract.reporting_period is None:
            contract.reporting_period = period
        if contract.as_of.tzinfo is None:
            contract.as_of = as_of
        return contract

    realized_gains, realized_losses = _split_signed(_amt_from_state(portfolio.get("realized_pnl")))
    unrealized_gains, unrealized_losses = _split_signed(_amt_from_state(portfolio.get("unrealized_pnl")))
    cash = _amt_from_state(portfolio.get("cash"))
    equity = _amt_from_state(portfolio.get("equity"))

    evidence: list[str] = ["mission_control.portfolio"]
    if reporting:
        evidence.append("mission_control.institutional_reporting")

    freshness = None
    df = raw.get("data_freshness")
    if isinstance(df, dict) and df.get("generated_at"):
        freshness = str(df["generated_at"])

    target = _amt_from_state(raw.get("target_profit"))

    return FinancialDataContract(
        currency=str(raw.get("currency") or portfolio.get("currency") or "USD"),
        reporting_period=period,
        as_of=as_of,
        source_system="css.mission_control",
        data_freshness=freshness,
        data_completeness="partial",
        evidence_references=evidence,
        realized_trading_gains=realized_gains,
        realized_trading_losses=realized_losses,
        unrealized_gains=unrealized_gains,
        unrealized_losses=unrealized_losses,
        cash=cash,
        investments_fair_value=equity if equity.present else FinancialAmount.missing(MissingReason.MISSING),
        target_profit=target,
        advisory_only=True,
    )


def summarize_package(package: dict[str, Any]) -> dict[str, Any]:
    """Flatten package fields for GET /api/financial-reporting/summary."""
    income = package.get("income_statement") or {}
    totals = income.get("totals") if isinstance(income, dict) else {}
    run = package.get("profitability_run_rate") or {}
    readiness = package.get("readiness") or {}
    return {
        "schema_version": package.get("schema_version"),
        "report_id": package.get("report_id"),
        "generated_at": package.get("generated_at"),
        "reporting_period": package.get("reporting_period"),
        "currency": package.get("currency"),
        "net_profit": (totals or {}).get("net_profit") if isinstance(totals, dict) else None,
        "target_profit": run.get("target_profit") if isinstance(run, dict) else None,
        "target_achieved_percentage": run.get("percentage_of_target_achieved")
        if isinstance(run, dict)
        else None,
        "required_daily_run_rate": run.get("required_daily_run_rate") if isinstance(run, dict) else None,
        "projected_period_end_profit": run.get("projected_period_end_profit")
        if isinstance(run, dict)
        else None,
        "profitability_traffic_light": run.get("traffic_light") if isinstance(run, dict) else "NOT_AVAILABLE",
        "readiness": readiness,
        "income_statement": package.get("income_statement"),
        "balance_sheet": package.get("balance_sheet"),
        "cash_flow_statement": package.get("cash_flow_statement"),
        "profitability_run_rate": package.get("profitability_run_rate"),
        "warnings": package.get("warnings") or [],
        "blockers": package.get("blockers") or [],
        "advisories": package.get("advisories") or [],
        "evidence": package.get("evidence") or [],
        "advisory_only": True,
        "trading_impact": False,
    }
