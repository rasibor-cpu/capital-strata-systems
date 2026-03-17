from __future__ import annotations

from typing import Dict


class TradeDecisionOrchestrator:
    """
    Central decision engine for Capital Strata Systems.

    This module coordinates multiple intelligence engines and produces
    the final trading decision used by the CSS execution layer.

    The orchestrator evaluates:

    - Market regime
    - Liquidity sweeps
    - VWAP elasticity
    - Pressure acceleration
    - Signal confluence
    - AI opportunity score

    Output:
        {
            "signal_class": "ELITE | STRONG | WEAK | NONE",
            "confidence": float,
            "direction": "LONG | SHORT | NONE",
            "reason": str
        }
    """

    def __init__(
        self,
        regime_engine,
        liquidity_detector,
        pressure_engine,
        confluence_engine,
        opportunity_scorer,
    ):

        self.regime_engine = regime_engine
        self.liquidity_detector = liquidity_detector
        self.pressure_engine = pressure_engine
        self.confluence_engine = confluence_engine
        self.opportunity_scorer = opportunity_scorer

    def evaluate(self, market_features: Dict) -> Dict:

        regime = self.regime_engine.detect(market_features)

        liquidity_event = self.liquidity_detector.detect(market_features)

        pressure = self.pressure_engine.evaluate(market_features)

        confluence = self.confluence_engine.evaluate(market_features)

        opportunity = self.opportunity_scorer.score(market_features)

        confidence = (
            0.30 * regime.get("confidence", 0)
            + 0.25 * confluence
            + 0.20 * liquidity_event.get("strength", 0)
            + 0.15 * pressure
            + 0.10 * opportunity
        )

        if confidence > 0.65:
            signal_class = "ELITE"
        elif confidence > 0.50:
            signal_class = "STRONG"
        elif confidence > 0.40:
            signal_class = "WEAK"
        else:
            signal_class = "NONE"

        direction = regime.get("direction", "NONE")

        return {
            "signal_class": signal_class,
            "confidence": round(confidence, 4),
            "direction": direction,
            "reason": regime.get("reason", "multi-engine evaluation"),
        }
