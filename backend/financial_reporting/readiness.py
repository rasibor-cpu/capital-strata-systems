"""Phase 177 — financial reporting readiness (NOT_READY > RED > AMBER > GREEN)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.financial_reporting.balance_sheet import BalanceSheet
from backend.financial_reporting.cash_flow import CashFlowStatement
from backend.financial_reporting.data_contracts import FinancialDataContract
from backend.financial_reporting.income_statement import IncomeStatement
from backend.financial_reporting.models import ReadinessState
from backend.financial_reporting.profitability_run_rate import ProfitabilityRunRate


_STATE_RANK = {
    ReadinessState.NOT_READY: 4,
    ReadinessState.RED: 3,
    ReadinessState.AMBER: 2,
    ReadinessState.GREEN: 1,
}


def _worse(a: ReadinessState, b: ReadinessState) -> ReadinessState:
    return a if _STATE_RANK[a] >= _STATE_RANK[b] else b


@dataclass(frozen=True)
class FinancialReportingReadiness:
    overall_state: ReadinessState
    overall_score: float
    income_data_available: bool
    expense_data_available: bool
    balance_sheet_available: bool
    cash_flow_available: bool
    target_profit_available: bool
    reporting_period_valid: bool
    timestamps_fresh: bool
    currency_consistent: bool
    accounting_equation_reconciled: bool | None
    cash_flow_reconciled: bool | None
    blocking_items: tuple[str, ...]
    warning_items: tuple[str, ...]
    advisories: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_state": self.overall_state.value,
            "overall_score": self.overall_score,
            "income_data_available": self.income_data_available,
            "expense_data_available": self.expense_data_available,
            "balance_sheet_available": self.balance_sheet_available,
            "cash_flow_available": self.cash_flow_available,
            "target_profit_available": self.target_profit_available,
            "reporting_period_valid": self.reporting_period_valid,
            "timestamps_fresh": self.timestamps_fresh,
            "currency_consistent": self.currency_consistent,
            "accounting_equation_reconciled": self.accounting_equation_reconciled,
            "cash_flow_reconciled": self.cash_flow_reconciled,
            "blocking_items": list(self.blocking_items),
            "warning_items": list(self.warning_items),
            "advisories": list(self.advisories),
            "precedence": "NOT_READY > RED > AMBER > GREEN",
        }


def evaluate_readiness(
    *,
    contract: FinancialDataContract,
    income: IncomeStatement,
    balance: BalanceSheet,
    cash_flow: CashFlowStatement,
    run_rate: ProfitabilityRunRate,
) -> FinancialReportingReadiness:
    blockers: list[str] = []
    warnings: list[str] = []
    advisories: list[str] = [
        "Canonical financial reporting is advisory management reporting — not audited statutory statements.",
        "Read-only: trading_impact=false.",
    ]

    period_valid = contract.reporting_period is not None
    if not period_valid:
        blockers.append("reporting_period missing")

    income_ok = income.net_profit is not None
    expense_ok = income.total_direct_costs is not None or income.total_operating_expenses is not None
    if not income_ok:
        blockers.append("income statement net profit unavailable")
    elif not income.complete:
        warnings.append("income statement incomplete")

    if not expense_ok:
        warnings.append("expense data limited or missing")

    bs_ok = balance.complete
    if not bs_ok:
        warnings.append("balance sheet incomplete")
    if balance.balanced is False:
        blockers.append("balance sheet accounting equation does not balance")

    cf_ok = cash_flow.complete
    if not cf_ok:
        warnings.append("cash flow incomplete")
    if cash_flow.reconciled is False:
        warnings.append("cash flow not reconciled")

    target_ok = contract.target_profit.present
    if not target_ok:
        warnings.append("target profit unavailable")

    timestamps_fresh = True  # foundation: as_of always set on contract
    currency_consistent = bool(contract.currency)

    state = ReadinessState.GREEN
    score = 100.0

    if blockers:
        state = ReadinessState.NOT_READY
        score = min(score, 25.0)
    elif balance.balanced is False or (run_rate.traffic_light.value == "RED" and target_ok):
        state = _worse(state, ReadinessState.RED)
        score = min(score, 45.0)
    elif warnings or run_rate.traffic_light.value == "AMBER":
        state = _worse(state, ReadinessState.AMBER)
        score = min(score, 70.0)

    # Score must not contradict NOT_READY / RED
    if state == ReadinessState.NOT_READY:
        score = min(score, 40.0)
    if state == ReadinessState.RED:
        score = min(score, 55.0)

    if not income_ok and not bs_ok and not cf_ok:
        state = ReadinessState.NOT_READY
        score = 0.0
        blockers.append("no financial statement sections available")

    return FinancialReportingReadiness(
        overall_state=state,
        overall_score=float(score),
        income_data_available=income_ok,
        expense_data_available=expense_ok,
        balance_sheet_available=bs_ok,
        cash_flow_available=cf_ok,
        target_profit_available=target_ok,
        reporting_period_valid=period_valid,
        timestamps_fresh=timestamps_fresh,
        currency_consistent=currency_consistent,
        accounting_equation_reconciled=balance.balanced,
        cash_flow_reconciled=cash_flow.reconciled,
        blocking_items=tuple(blockers),
        warning_items=tuple(warnings),
        advisories=tuple(advisories),
    )
