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

    def evaluate_trade(self, asset: str, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not candles or len(candles) < 20:
            return self._reject(asset, "INSUFFICIENT_DATA")

        regime_info = self.regime_detector.detect_regime(candles)
        regime = str(regime_info.get("regime", "NEUTRAL")).upper()
        regime_conf = float(regime_info.get("confidence", 0.0))

        row: Dict[str, Any] = {"symbol": asset, "candles": candles}

        pressure_row = self.pressure_engine.enrich_rows([row])[0]
        accel_row = self.acceleration_engine.enrich_rows([pressure_row])[0]
        conf_row = self.signal_confluence_engine.enrich_rows([accel_row])[0]

        pressure = float(conf_row.get("pressure_score", 0.0))
        accel = float(conf_row.get("pressure_acceleration", 0.0))
        confluence = float(conf_row.get("confluence_score", 0.0))
        momentum = self._estimate_momentum(candles)

        ai_score = self._score_ai(conf_row)
        pressure_fusion = (pressure * 0.6) + (abs(accel) * 0.4)

        decision_score = (
            ai_score * self.weights["ai_score"]
            + confluence * self.weights["confluence_score"]
            + pressure_fusion * self.weights["pressure_fusion"]
            + momentum * self.weights["momentum_score"]
            + regime_conf * self.weights["regime_confidence"]
        )
        decision_score = self._clamp01(decision_score)

        execute_trade = self._should_execute_trade(regime, decision_score)

        pressure_ok = pressure >= 0.18
        confluence_ok = confluence >= 0.10
        momentum_ok = (accel > -0.02) or (pressure > 0.22)

        if pressure_ok and confluence_ok and momentum_ok:
            execute_trade = True

        if decision_score >= 0.26:
            execute_trade = True

        if decision_score >= 0.22 and pressure >= 0.15:
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

    def _score_ai(self, row: Dict[str, Any]) -> float:
        if hasattr(self.ai_scorer, "score_opportunity"):
            return float(self.ai_scorer.score_opportunity(row))
        if hasattr(self.ai_scorer, "score"):
            return float(self.ai_scorer.score(row))
        return 0.0

    def _should_execute_trade(self, regime: str, score: float) -> bool:
        if regime == "MEAN_REVERSION":
            return score >= self.mean_reversion_threshold
        if regime == "TREND":
            return score >= self.trend_threshold
        if regime == "BREAKOUT":
            return score >= self.breakout_threshold
        return score >= 0.26

    def _estimate_momentum(self, candles: List[Dict[str, Any]]) -> float:
        closes = [float(c.get("close", 0.0)) for c in candles[-5:] if isinstance(c, dict)]
        if len(closes) < 2 or closes[0] == 0:
            return 0.0
        return self._clamp01(abs((closes[-1] - closes[0]) / (closes[0] + 1e-9)) * 50)

    def _clamp01(self, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    def _reject(self, asset: str, reason: str) -> Dict[str, Any]:
        return {
            "asset": asset,
            "execute_trade": False,
            "reason": reason,
            "decision_score": 0.0,
        }