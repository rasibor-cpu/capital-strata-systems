from __future__ import annotations

from datetime import datetime, UTC
from typing import Iterable

from analytics.portfolio_optimizer import (
    PortfolioAllocationPlan,
    StrategyAllocation,
)


class PortfolioOptimizerEngine:
    """
    Phase 129B-2 (Level 1)

    Deterministic equal-weight allocation engine.

    This engine intentionally performs no score weighting,
    market regime adaptation, or optimization. It establishes
    the canonical interface that later phases will extend.
    """

    def build_equal_weight_plan(
        self,
        strategy_ids: Iterable[str],
        *,
        total_capital: float,
        market_regime: str = "UNKNOWN",
        risk_profile: str = "BALANCED",
    ) -> PortfolioAllocationPlan:
        ids = [str(s).strip() for s in strategy_ids if str(s).strip()]

        plan = PortfolioAllocationPlan(
            generated_at=datetime.now(UTC).isoformat(),
            market_regime=market_regime,
            risk_profile=risk_profile,
            total_capital=total_capital,
        )

        if not ids:
            return plan

        pct = round(100.0 / len(ids), 4)

        allocated = 0.0
        for i, sid in enumerate(ids):
            if i == len(ids) - 1:
                allocation_percent = round(100.0 - allocated, 4)
            else:
                allocation_percent = pct
                allocated += pct

            amount = round(total_capital * allocation_percent / 100.0, 2)

            plan.allocations.append(
                StrategyAllocation(
                    strategy_id=sid,
                    allocation_percent=allocation_percent,
                    allocation_amount=amount,
                    confidence=1.0,
                    expected_risk=0.0,
                    rationale="Equal-weight deterministic allocation",
                )
            )

        return plan
