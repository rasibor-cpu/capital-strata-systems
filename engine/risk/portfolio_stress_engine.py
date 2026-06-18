"""
Capital Strata Systems
Phase 92B

Portfolio Stress Engine

Purpose
-------
Applies canonical stress scenarios to simplified portfolio exposures.

This is a deterministic, broker-free institutional risk engine.

No broker calls.
No trade execution.
No portfolio mutation.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from engine.risk.stress_scenarios import (
    CANONICAL_STRESS_SCENARIOS,
    StressScenario,
)


@dataclass(frozen=True)
class PortfolioExposure:
    symbol: str
    asset_class: str
    market_value: float = 0.0
    delta_exposure: float = 0.0
    gamma_exposure: float = 0.0
    vega_exposure: float = 0.0
    rate_exposure: float = 0.0
    fx_exposure: float = 0.0


@dataclass(frozen=True)
class StressResult:
    scenario: str
    estimated_pnl: float
    equity_impact: float
    gamma_impact: float
    volatility_impact: float
    rate_impact: float
    fx_impact: float


class PortfolioStressEngine:
    """
    Deterministic portfolio stress engine.

    Uses first-order and simple second-order approximations:

    - equity impact: delta exposure * equity shock
    - gamma impact: 0.5 * gamma exposure * shock^2
    - volatility impact: vega exposure * volatility shock
    - rate impact: rate exposure * rate shock
    - fx impact: fx exposure * fx shock
    """

    def __init__(
        self,
        scenarios: Optional[Dict[str, StressScenario]] = None,
    ) -> None:
        self.scenarios = scenarios or CANONICAL_STRESS_SCENARIOS

    def stress_one(
        self,
        exposures: Iterable[PortfolioExposure],
        scenario_name: str,
    ) -> StressResult:
        if scenario_name not in self.scenarios:
            raise ValueError(f"Unknown stress scenario: {scenario_name}")

        scenario = self.scenarios[scenario_name]

        equity_shock = scenario.equity_move_pct / 100.0
        volatility_shock = scenario.volatility_move_pct / 100.0
        rate_shock = scenario.rate_move_pct / 100.0
        fx_shock = scenario.fx_move_pct / 100.0

        equity_impact = 0.0
        gamma_impact = 0.0
        volatility_impact = 0.0
        rate_impact = 0.0
        fx_impact = 0.0

        for exposure in exposures:
            equity_impact += exposure.delta_exposure * equity_shock
            gamma_impact += 0.5 * exposure.gamma_exposure * (equity_shock ** 2)
            volatility_impact += exposure.vega_exposure * volatility_shock
            rate_impact += exposure.rate_exposure * rate_shock
            fx_impact += exposure.fx_exposure * fx_shock

        estimated_pnl = (
            equity_impact
            + gamma_impact
            + volatility_impact
            + rate_impact
            + fx_impact
        )

        return StressResult(
            scenario=scenario.name,
            estimated_pnl=round(estimated_pnl, 2),
            equity_impact=round(equity_impact, 2),
            gamma_impact=round(gamma_impact, 2),
            volatility_impact=round(volatility_impact, 2),
            rate_impact=round(rate_impact, 2),
            fx_impact=round(fx_impact, 2),
        )

    def stress_all(
        self,
        exposures: Iterable[PortfolioExposure],
    ) -> List[StressResult]:
        exposure_list = list(exposures)
        return [
            self.stress_one(exposure_list, scenario_name)
            for scenario_name in self.scenarios
        ]