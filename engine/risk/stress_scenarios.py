"""
Capital Strata Systems
Phase 92A

Institutional Portfolio Stress Scenario Registry

Purpose
-------
Provides canonical stress scenario definitions that can be
consumed by portfolio risk engines, options analytics,
futures analytics, FX analytics and dashboard reporting.

This file contains definitions only.

No execution logic.
No broker integration.
No portfolio mutation.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class StressScenario:
    name: str
    equity_move_pct: float = 0.0
    volatility_move_pct: float = 0.0
    rate_move_pct: float = 0.0
    fx_move_pct: float = 0.0


SPY_DOWN_5 = StressScenario(
    name="SPY_DOWN_5",
    equity_move_pct=-5.0,
)

SPY_DOWN_10 = StressScenario(
    name="SPY_DOWN_10",
    equity_move_pct=-10.0,
)

SPY_UP_5 = StressScenario(
    name="SPY_UP_5",
    equity_move_pct=5.0,
)

SPY_UP_10 = StressScenario(
    name="SPY_UP_10",
    equity_move_pct=10.0,
)

VOL_PLUS_20 = StressScenario(
    name="VOL_PLUS_20",
    volatility_move_pct=20.0,
)

VOL_MINUS_20 = StressScenario(
    name="VOL_MINUS_20",
    volatility_move_pct=-20.0,
)

RATE_PLUS_1 = StressScenario(
    name="RATE_PLUS_1",
    rate_move_pct=1.0,
)

RATE_MINUS_1 = StressScenario(
    name="RATE_MINUS_1",
    rate_move_pct=-1.0,
)

FX_USD_PLUS_10 = StressScenario(
    name="FX_USD_PLUS_10",
    fx_move_pct=10.0,
)

FX_USD_MINUS_10 = StressScenario(
    name="FX_USD_MINUS_10",
    fx_move_pct=-10.0,
)

CANONICAL_STRESS_SCENARIOS: Dict[str, StressScenario] = {
    scenario.name: scenario
    for scenario in [
        SPY_DOWN_5,
        SPY_DOWN_10,
        SPY_UP_5,
        SPY_UP_10,
        VOL_PLUS_20,
        VOL_MINUS_20,
        RATE_PLUS_1,
        RATE_MINUS_1,
        FX_USD_PLUS_10,
        FX_USD_MINUS_10,
    ]
}