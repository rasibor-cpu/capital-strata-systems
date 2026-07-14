from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any, Mapping

from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeRiskBudgetError(ValueError):
    """Raised when risk budget inputs are invalid."""


@dataclass(frozen=True)
class OptionsIncomeRiskBudgetConfig:
    max_net_delta: float = 80.0
    max_absolute_delta: float = 180.0
    max_gamma: float = 20.0
    min_theta: float = 0.0
    max_vega: float = 80.0
    max_rho: float = 80.0
    max_single_underlying_pct: float = 0.55
    max_single_expiry_pct: float = 0.55
    max_single_strategy_pct: float = 0.70
    max_assignment_exposure_pct: float = 1.0
    max_collateral_utilization: float = 0.85
    max_volatility_exposure: float = 0.60
    max_stressed_loss_pct: float = 0.12


class OptionsIncomeRiskBudgetEngine:
    def __init__(self, config: OptionsIncomeRiskBudgetConfig | None = None) -> None:
        self.config = config or OptionsIncomeRiskBudgetConfig()

    def evaluate(
        self,
        *,
        greeks: Mapping[str, Any],
        diversification: Mapping[str, Any],
        capital: Mapping[str, Any],
        assignment: Mapping[str, Any],
        volatility: Mapping[str, Any],
        stress: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        portfolio = dict(greeks.get("portfolio") or {})
        rows = {
            "portfolio_delta": _budget(abs(float(portfolio.get("delta", 0.0) or 0.0)), self.config.max_net_delta),
            "absolute_delta": _budget(float(portfolio.get("absolute_delta_exposure", 0.0) or 0.0), self.config.max_absolute_delta),
            "gamma": _budget(abs(float(portfolio.get("gamma", 0.0) or 0.0)), self.config.max_gamma),
            "theta": _min_budget(float(portfolio.get("theta_income", 0.0) or 0.0), self.config.min_theta),
            "vega": _budget(abs(float(portfolio.get("vega", 0.0) or 0.0)), self.config.max_vega),
            "rho": _budget(abs(float(portfolio.get("rho", 0.0) or 0.0)), self.config.max_rho),
            "single_underlying_exposure": _budget(_max(diversification.get("by_underlying", {})), self.config.max_single_underlying_pct),
            "single_expiry_exposure": _budget(_max(diversification.get("by_expiry", {})), self.config.max_single_expiry_pct),
            "single_strategy_exposure": _budget(_max(diversification.get("by_strategy", {})), self.config.max_single_strategy_pct),
            "assignment_exposure": _budget(float(assignment.get("portfolio_assignment_ratio", 0.0) or 0.0), self.config.max_assignment_exposure_pct),
            "collateral_utilization": _budget(float(capital.get("portfolio_utilization", 0.0) or 0.0), self.config.max_collateral_utilization),
            "volatility_exposure": _budget(float(volatility.get("short_volatility_concentration", 0.0) or 0.0), self.config.max_volatility_exposure),
        }
        if stress is not None:
            rows["stressed_loss"] = _budget(float(stress.get("max_estimated_loss_pct", 0.0) or 0.0), self.config.max_stressed_loss_pct)
        if greeks.get("status") == "UNAVAILABLE":
            rows["greeks_availability"] = _unavailable("Missing Greeks")
        if volatility.get("status") == "UNAVAILABLE":
            rows["volatility_availability"] = _unavailable("Missing implied volatility")
        overall = "GREEN"
        if any(row["status"] == "RED" for row in rows.values()):
            overall = "RED"
        elif any(row["status"] in {"AMBER", "UNAVAILABLE"} for row in rows.values()):
            overall = "AMBER"
        return {"status": overall, "budgets": rows, "config": asdict(self.config), **SAFE_FLAGS}


def _budget(current: float, limit: float) -> dict[str, Any]:
    _finite(current, "current")
    _finite(limit, "limit")
    if limit <= 0:
        return _unavailable("Non-positive limit")
    util = current / limit
    status = "GREEN" if util <= 0.75 else ("AMBER" if util <= 1.0 else "RED")
    return {
        "limit": round(limit, 8),
        "current_exposure": round(current, 8),
        "remaining_capacity": round(max(0.0, limit - current), 8),
        "utilization_pct": round(util, 8),
        "status": status,
        "reasons": [] if status == "GREEN" else [f"utilization {util:.2%}"],
        **SAFE_FLAGS,
    }


def _min_budget(current: float, minimum: float) -> dict[str, Any]:
    _finite(current, "current")
    _finite(minimum, "minimum")
    status = "GREEN" if current >= minimum else "RED"
    return {
        "limit": round(minimum, 8),
        "current_exposure": round(current, 8),
        "remaining_capacity": round(max(0.0, current - minimum), 8),
        "utilization_pct": 1.0 if minimum <= 0 else round(current / minimum, 8),
        "status": status,
        "reasons": [] if status == "GREEN" else ["below minimum theta income"],
        **SAFE_FLAGS,
    }


def _unavailable(reason: str) -> dict[str, Any]:
    return {"limit": 0.0, "current_exposure": 0.0, "remaining_capacity": 0.0, "utilization_pct": 0.0, "status": "UNAVAILABLE", "reasons": [reason], **SAFE_FLAGS}


def _max(row: Mapping[str, Any]) -> float:
    return max([0.0, *[float(value or 0.0) for value in dict(row).values()]])


def _finite(value: Any, field: str) -> None:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OptionsIncomeRiskBudgetError(f"{field} must be numeric") from exc
    if not isfinite(number):
        raise OptionsIncomeRiskBudgetError(f"{field} must be finite")


__all__ = ["OptionsIncomeRiskBudgetConfig", "OptionsIncomeRiskBudgetEngine", "OptionsIncomeRiskBudgetError"]
