from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from backend.options.options_income_risk_budget import OptionsIncomeRiskBudgetConfig
from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeRiskLimitError(ValueError):
    """Raised when risk limits cannot be evaluated."""


@dataclass(frozen=True)
class RiskLimitResult:
    status: str
    hard_breaches: list[str]
    advisory_breaches: list[str]
    limit_details: dict[str, Any]
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, **SAFE_FLAGS}


class OptionsIncomeRiskLimitEngine:
    def __init__(self, config: OptionsIncomeRiskBudgetConfig | None = None) -> None:
        self.config = config or OptionsIncomeRiskBudgetConfig()

    def evaluate(self, budgets: Mapping[str, Any]) -> RiskLimitResult:
        rows = dict(budgets.get("budgets") or {})
        if not rows:
            raise OptionsIncomeRiskLimitError("Missing risk budget rows")
        hard_fields = {
            "portfolio_delta",
            "absolute_delta",
            "gamma",
            "vega",
            "assignment_exposure",
            "collateral_utilization",
            "stressed_loss",
        }
        advisory_fields = {"theta", "rho", "single_underlying_exposure", "single_expiry_exposure", "single_strategy_exposure", "volatility_exposure"}
        hard = sorted(field for field in hard_fields if rows.get(field, {}).get("status") == "RED")
        advisory = sorted(field for field in advisory_fields if rows.get(field, {}).get("status") in {"AMBER", "RED", "UNAVAILABLE"})
        if any(row.get("status") == "UNAVAILABLE" for row in rows.values()):
            advisory.append("unavailable_data")
        status = "RED" if hard else ("AMBER" if advisory else "GREEN")
        return RiskLimitResult(status=status, hard_breaches=hard, advisory_breaches=sorted(set(advisory)), limit_details=rows)


__all__ = ["OptionsIncomeRiskLimitEngine", "OptionsIncomeRiskLimitError", "RiskLimitResult"]
