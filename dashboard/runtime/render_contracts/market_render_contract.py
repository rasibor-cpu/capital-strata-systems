from __future__ import annotations

from dataclasses import dataclass

from dashboard.runtime.dashboard_state import MarketStatePayload


@dataclass(frozen=True)
class MarketRenderContract:
    """
    PCNRASS-safe immutable render contract for market intelligence display.

    Rules:
    - Renderer consumes this contract only.
    - Renderer performs no market calculations.
    - Market values must come from normalized market state.
    """

    trend_state: str
    volatility_state: str
    liquidity_state: str
    mean_reversion_state: str
    probability_state: str
    velocity_state: str

    vwap_state: str
    vwap_distance: float
    vwap_elasticity: float

    momentum_state: str
    pressure_state: str
    acceleration_state: str

    regime_state: str
    spread_state: str
    execution_cost_state: str
    signal_confluence_state: str

    @classmethod
    def from_market_state(
        cls,
        market_state: MarketStatePayload,
    ) -> "MarketRenderContract":
        return cls(
            trend_state=str(market_state.trend_state),
            volatility_state=str(market_state.volatility_state),
            liquidity_state=str(market_state.liquidity_state),
            mean_reversion_state=str(market_state.mean_reversion_state),
            probability_state=str(market_state.probability_state),
            velocity_state=str(market_state.velocity_state),
            vwap_state=str(market_state.vwap_state),
            vwap_distance=float(market_state.vwap_distance),
            vwap_elasticity=float(market_state.vwap_elasticity),
            momentum_state=str(market_state.momentum_state),
            pressure_state=str(market_state.pressure_state),
            acceleration_state=str(market_state.acceleration_state),
            regime_state=str(market_state.regime_state),
            spread_state=str(market_state.spread_state),
            execution_cost_state=str(market_state.execution_cost_state),
            signal_confluence_state=str(market_state.signal_confluence_state),
        )
