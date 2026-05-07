from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime.dashboard_state import (
    DashboardState,
    MarketStatePayload,
)


class MarketStateBuilder:
    """
    Build MarketStatePayload for DashboardState.

    PURPOSE
    -------
    Normalize market intelligence outputs into structured
    dashboard-safe market state payloads.

    RULES
    -----
    - builder must not generate trading signals
    - builder must not override intelligence truth
    - builder must not execute trades
    """

    def build(
        self,
        *,
        market_payload: Dict[str, Any],
        state: DashboardState,
    ) -> DashboardState:

        market_state = MarketStatePayload(

            trend_state=str(
                market_payload.get(
                    "trend_state",
                    "UNKNOWN",
                )
            ),

            volatility_state=str(
                market_payload.get(
                    "volatility_state",
                    "UNKNOWN",
                )
            ),

            liquidity_state=str(
                market_payload.get(
                    "liquidity_state",
                    "UNKNOWN",
                )
            ),

            mean_reversion_state=str(
                market_payload.get(
                    "mean_reversion_state",
                    "UNKNOWN",
                )
            ),

            probability_state=str(
                market_payload.get(
                    "probability_state",
                    "UNKNOWN",
                )
            ),

            velocity_state=str(
                market_payload.get(
                    "velocity_state",
                    "UNKNOWN",
                )
            ),

            vwap_state=str(
                market_payload.get(
                    "vwap_state",
                    "UNKNOWN",
                )
            ),

            vwap_distance=float(
                market_payload.get(
                    "vwap_distance",
                    0.0,
                )
            ),

            vwap_elasticity=float(
                market_payload.get(
                    "vwap_elasticity",
                    0.0,
                )
            ),

            momentum_state=str(
                market_payload.get(
                    "momentum_state",
                    "UNKNOWN",
                )
            ),

            pressure_state=str(
                market_payload.get(
                    "pressure_state",
                    "UNKNOWN",
                )
            ),

            acceleration_state=str(
                market_payload.get(
                    "acceleration_state",
                    "UNKNOWN",
                )
            ),

            regime_state=str(
                market_payload.get(
                    "regime_state",
                    "UNKNOWN",
                )
            ),

            spread_state=str(
                market_payload.get(
                    "spread_state",
                    "UNKNOWN",
                )
            ),

            execution_cost_state=str(
                market_payload.get(
                    "execution_cost_state",
                    "UNKNOWN",
                )
            ),

            signal_confluence_state=str(
                market_payload.get(
                    "signal_confluence_state",
                    "UNKNOWN",
                )
            ),
        )

        state.global_market_state = market_state

        return state