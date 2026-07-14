from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any, Mapping, Sequence

from backend.options.paper_position_repository import SAFE_FLAGS


@dataclass(frozen=True)
class IncomeTargetReport:
    monthly_premium_target: float
    annual_premium_target: float
    portfolio_yield: float
    yield_on_collateral: float
    expected_premium: float
    premium_consistency: float
    capital_efficiency: float
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "monthly_premium_target": self.monthly_premium_target,
            "annual_premium_target": self.annual_premium_target,
            "portfolio_yield": self.portfolio_yield,
            "yield_on_collateral": self.yield_on_collateral,
            "expected_premium": self.expected_premium,
            "premium_consistency": self.premium_consistency,
            "capital_efficiency": self.capital_efficiency,
            **SAFE_FLAGS,
        }


class OptionsIncomeTargetCalculator:
    def calculate(
        self,
        allocations: Sequence[Mapping[str, Any]],
        *,
        total_capital: float,
        annual_target_yield: float = 0.12,
    ) -> IncomeTargetReport:
        capital = _positive(total_capital, "total_capital")
        target_yield = max(0.0, float(annual_target_yield))
        annual_target = capital * target_yield
        monthly_target = annual_target / 12.0
        expected = sum(float(row.get("expected_premium", 0.0) or 0.0) for row in allocations)
        collateral = sum(float(row.get("collateral", 0.0) or 0.0) for row in allocations)
        premiums = [float(row.get("expected_premium", 0.0) or 0.0) for row in allocations]
        consistency = 1.0
        if len(premiums) > 1 and mean(premiums) > 0:
            consistency = max(0.0, 1.0 - pstdev(premiums) / mean(premiums))
        return IncomeTargetReport(
            monthly_premium_target=round(monthly_target, 6),
            annual_premium_target=round(annual_target, 6),
            portfolio_yield=round((expected * 12.0) / capital, 8),
            yield_on_collateral=round((expected / collateral) if collateral > 0 else 0.0, 8),
            expected_premium=round(expected, 6),
            premium_consistency=round(consistency, 8),
            capital_efficiency=round((collateral / capital) if capital > 0 else 0.0, 8),
        )


def _positive(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if number <= 0.0:
        raise ValueError(f"{field} must be positive")
    return number


__all__ = ["IncomeTargetReport", "OptionsIncomeTargetCalculator"]
