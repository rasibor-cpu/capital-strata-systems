# === FULL SAFE UPGRADE: TRADE DECISION ORCHESTRATOR ===

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
    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()

        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()

        # ORIGINAL THRESHOLDS PRESERVED
        self.mean_reversion_threshold = 0.20
        self.trend_threshold = 0.24
        self.breakout_threshold = 0.28

        self.weights = {
            "ai_score": 0.30,
            "confluence_score": 0.25,
            "pressure_fusion": 0.25,
            "momentum_score": 0.10,
            "regime_confidence": 0.10,
        }

    # =========================
    # MAIN EVALUATION
    # =========================

    def evaluate_trade(self, asset: str, candles: List[Dict[str, Any]]) -> Dict[str, Any]:

        if not candles or len(candles) < 20:
            return self._reject(asset, "INSUFFICIENT_DATA")

        regime_info = self.regime_detector.detect_regime(candles)
        regime = str(regime_info.get("regime", "NEUTRAL")).upper()
        regime_conf = float(regime_info.get("confidence", 0.0))

        row = {"symbol": asset, "candles": candles}

        # --- SIGNAL ENRICHMENT ---
        pressure_row = self.pressure_engine.enrich_rows([row])[0]
        accel_row = self.acceleration_engine.enrich_rows([pressure_row])[0]
        conf_row = self.signal_confluence_engine.enrich_rows([accel_row])[0]

        pressure = float(conf_row.get("pressure_score", 0.0))
        accel = float(conf_row.get("pressure_acceleration", 0.0))
        confluence = float(conf_row.get("confluence_score", 0.0))

        momentum = self._estimate_momentum(candles)

        # --- AI SCORE ---
        ai_score = self.ai_scorer.score_opportunity(conf_row)

        # --- FUSED SCORE ---
        pressure_fusion = (pressure * 0.6) + (abs(accel) * 0.4)

        decision_score = (
            ai_score * self.weights["ai_score"]
            + confluence * self.weights["confluence_score"]
            + pressure_fusion * self.weights["pressure_fusion"]
            + momentum * self.weights["momentum_score"]
            + regime_conf * self.weights["regime_confidence"]
        )

        decision_score = self._clamp01(decision_score)

        # =========================
        # 🔥 EXECUTION LOGIC (UPGRADED)
        # =========================

        # Base rule (original)
        execute_trade = self._should_execute_trade(regime, decision_score)

        # --- NEW SMART EXECUTION ---
        pressure_ok = pressure >= 0.24
        confluence_ok = confluence >= 0.13
        momentum_ok = (accel > 0) or (pressure > 0.30)

        if pressure_ok and confluence_ok and momentum_ok:
            execute_trade = True

        # High conviction override
        if decision_score >= 0.32:
            execute_trade = True

        return {
            "asset": asset,
            "execute_trade": execute_trade,
            "regime": regime,
            "pressure_score": round(pressure, 4),
            "acceleration_score": round(accel, 4),
            "confluence_score": round(confluence, 4),
            "momentum_score": round(momentum, 4),
            "ai_score": round(ai_score, 4),
            "decision_score": round(decision_score, 4),
        }

    # =========================
    # HELPERS
    # =========================

    def _should_execute_trade(self, regime: str, score: float) -> bool:
        if regime == "MEAN_REVERSION":
            return score >= self.mean_reversion_threshold
        if regime == "TREND":
            return score >= self.trend_threshold
        if regime == "BREAKOUT":
            return score >= self.breakout_threshold
        return score >= 0.26

    def _estimate_momentum(self, candles):
        closes = [c.get("close", 0) for c in candles[-5:]]
        if len(closes) < 2:
            return 0.0
        return self._clamp01(abs((closes[-1] - closes[0]) / (closes[0] + 1e-9)) * 50)

    def _clamp01(self, v):
        return max(0.0, min(1.0, float(v)))

    def _reject(self, asset, reason):
        return {
            "asset": asset,
            "execute_trade": False,
            "reason": reason,
            "decision_score": 0.0,
        }