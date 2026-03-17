from __future__ import annotations

from typing import Any, Dict, List

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.market_regime_detector import MarketRegimeDetector
from backend.intelligence.opportunity_momentum_window_engine import (
    OpportunityMomentumWindowEngine,
)
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import (
    PressureAccelerationEngine,
)
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine


class TradeDecisionOrchestrator:
    """
    Controlled activation orchestrator (Phase 1 unlock)

    Goals:
    - enable controlled trade flow
    - preserve governance discipline
    - avoid over-filtering (current problem)
    """

    def __init__(self):

        self.regime_detector = MarketRegimeDetector()
        self.ai = AIOpportunityScorer()
        self.pressure_engine = OpportunityPressureEngine()
        self.accel_engine = PressureAccelerationEngine()
        self.confluence_engine = SignalConfluenceEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()

        # ---- NEW CONTROL THRESHOLDS ----

        self.ELITE_THRESHOLD = 0.55
        self.STRONG_THRESHOLD = 0.40
        self.ACTIVATION_THRESHOLD = 0.30  # key unlock

    # ---------------------------------------------------------
    # MAIN ENTRY
    # ---------------------------------------------------------

    def evaluate_trade(
        self,
        asset: str,
        candles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        if not candles or len(candles) < 20:
            return self._empty(asset)

        # ---------------- REGIME ----------------

        regime_info = self.regime_detector.detect_regime(candles)
        regime = regime_info.get("regime", "NEUTRAL")

        # ---------------- FEATURE FLOW ----------------

        base_score = self.ai.score(candles)
        pressure = self.pressure_engine.compute(candles)
        accel = self.accel_engine.compute(candles)
        confluence = self.confluence_engine.compute(candles)
        momentum = self.momentum_engine.compute(candles)

        # ---------------- SCORE BUILD ----------------

        decision_score = (
            0.35 * base_score
            + 0.20 * pressure
            + 0.15 * accel
            + 0.20 * confluence
            + 0.10 * momentum
        )

        # ---------------- ELASTICITY PROXY ----------------
        # lightweight proxy (since elasticity engine is upstream)

        closes = [float(c.get("close", 0)) for c in candles[-10:]]
        if len(closes) >= 2:
            elasticity = abs(closes[-1] - sum(closes) / len(closes)) / max(1e-6, closes[-1])
        else:
            elasticity = 0.0

        # ---------------- TIERING ----------------

        if decision_score >= self.ELITE_THRESHOLD:
            tier = "ELITE"
        elif decision_score >= self.STRONG_THRESHOLD:
            tier = "STRONG"
        elif decision_score >= self.ACTIVATION_THRESHOLD:
            tier = "ACTIVE"
        else:
            tier = "WATCH"

        # ---------------- EXECUTION LOGIC ----------------

        execute = False

        # ELITE always executes
        if tier == "ELITE":
            execute = True

        # STRONG executes if market not hostile
        elif tier == "STRONG":
            if regime != "CHAOTIC":
                execute = True

        # ACTIVE (NEW UNLOCK ZONE)
        elif tier == "ACTIVE":
            # require some movement (avoid dead markets)
            if elasticity > 0.0015:
                execute = True

        # WATCH never executes

        # ---------------- RETURN ----------------

        return {
            "asset": asset,
            "execute_trade": execute,
            "signal_tier": tier,
            "decision_score": decision_score,
            "elasticity_score": elasticity,
            "regime": regime,
        }

    # ---------------------------------------------------------

    def _empty(self, asset: str) -> Dict[str, Any]:
        return {
            "asset": asset,
            "execute_trade": False,
            "signal_tier": "NONE",
            "decision_score": 0.0,
            "elasticity_score": 0.0,
            "regime": "UNKNOWN",
        }