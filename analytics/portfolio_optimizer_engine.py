from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from analytics.portfolio_optimizer import (
    PortfolioAllocationPlan,
    StrategyAllocation,
)


class PortfolioOptimizerEngine:
    """
    Phase 129B Portfolio Optimizer Engine.

    Level 1:
        Deterministic equal-weight allocation.

    Level 2:
        Risk-profile-aware allocation using ordered strategy IDs.

    This engine recommends allocations only. It does not authorize
    trade execution. Downstream governance remains responsible for
    validation and approval.
    """

    _PROFILE_TOP_WEIGHT = {
        "DEFENSIVE": 1.00,
        "CONSERVATIVE": 1.15,
        "BALANCED": 1.00,
        "GROWTH": 1.35,
        "OPPORTUNISTIC": 1.60,
    }

    def build_equal_weight_plan(
        self,
        strategy_ids: Iterable[str],
        *,
        total_capital: float,
        market_regime: str = "UNKNOWN",
        risk_profile: str = "BALANCED",
    ) -> PortfolioAllocationPlan:
        ids = self._clean_strategy_ids(strategy_ids)
        return self._build_plan_from_weights(
            ids,
            [1.0 for _ in ids],
            total_capital=total_capital,
            market_regime=market_regime,
            risk_profile=risk_profile,
            rationale="Equal-weight deterministic allocation",
        )

    def build_risk_profile_plan(
        self,
        strategy_ids: Iterable[str],
        *,
        total_capital: float,
        market_regime: str = "UNKNOWN",
        risk_profile: str = "BALANCED",
    ) -> PortfolioAllocationPlan:
        ids = self._clean_strategy_ids(strategy_ids)
        profile = str(risk_profile or "BALANCED").strip().upper()

        if profile == "BALANCED":
            return self.build_equal_weight_plan(
                ids,
                total_capital=total_capital,
                market_regime=market_regime,
                risk_profile=profile,
            )

        top_weight = self._PROFILE_TOP_WEIGHT.get(profile, 1.0)
        weights = self._profile_weights(len(ids), top_weight)

        return self._build_plan_from_weights(
            ids,
            weights,
            total_capital=total_capital,
            market_regime=market_regime,
            risk_profile=profile,
            rationale=f"Risk-profile-aware allocation: {profile}",
        )

    @staticmethod
    def _clean_strategy_ids(strategy_ids: Iterable[str]) -> list[str]:
        return [str(s).strip() for s in strategy_ids if str(s).strip()]

    @staticmethod
    def _profile_weights(count: int, top_weight: float) -> list[float]:
        if count <= 0:
            return []

        if count == 1:
            return [1.0]

        if top_weight <= 1.0:
            return [1.0 for _ in range(count)]

        step = (top_weight - 1.0) / max(count - 1, 1)
        return [round(top_weight - (i * step), 8) for i in range(count)]

    def _build_plan_from_weights(
        self,
        strategy_ids: list[str],
        weights: list[float],
        *,
        total_capital: float,
        market_regime: str,
        risk_profile: str,
        rationale: str,
    ) -> PortfolioAllocationPlan:
        plan = PortfolioAllocationPlan(
            generated_at=datetime.now(UTC).isoformat(),
            market_regime=market_regime,
            risk_profile=risk_profile,
            total_capital=total_capital,
        )

        if not strategy_ids:
            return plan

        total_weight = sum(weights)
        allocated_percent = 0.0
        allocated_amount = 0.0

        for i, strategy_id in enumerate(strategy_ids):
            if i == len(strategy_ids) - 1:
                allocation_percent = round(100.0 - allocated_percent, 4)
                allocation_amount = round(total_capital - allocated_amount, 2)
            else:
                allocation_percent = round((weights[i] / total_weight) * 100.0, 4)
                allocation_amount = round(total_capital * allocation_percent / 100.0, 2)
                allocated_percent += allocation_percent
                allocated_amount += allocation_amount

            plan.allocations.append(
                StrategyAllocation(
                    strategy_id=strategy_id,
                    allocation_percent=allocation_percent,
                    allocation_amount=allocation_amount,
                    confidence=1.0,
                    expected_risk=0.0,
                    rationale=rationale,
                )
            )

        plan.diversification_metrics = {
            "strategy_count": len(strategy_ids),
            "max_allocation_percent": max(
                item.allocation_percent for item in plan.allocations
            ),
            "min_allocation_percent": min(
                item.allocation_percent for item in plan.allocations
            ),
        }

        return plan
