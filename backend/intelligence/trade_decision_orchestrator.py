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

    def __init__(self):
        self.regime_detector = MarketRegimeDetector()
        self.ai_scorer = AIOpportunityScorer()
        self.pressure_engine = OpportunityPressureEngine()
        self.accel_engine = PressureAccelerationEngine()
        self.confluence_engine = SignalConfluenceEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()

        # ---- BALANCED THRESHOLDS ----
        self.ELITE_THRESHOLD = 0.55
        self.STRONG_THRESHOLD = 0.42
        self.ACTIVE_THRESHOLD = 0.32  # tightened

    # ---------------------------------------------------------

    def evaluate_trade(self, asset: str, candles: List[Dict[str, Any]]) -> Dict[str, Any]:

        if not candles or len(candles) < 20:
            return self._empty(asset)

        candles = [self._normalize(c) for c in candles]

        regime = self._get_regime(candles)

        base = self._safe_ai(candles)
        pressure = self._safe_pressure(candles)
        accel = self._safe_accel(candles)
        confluence = self._safe_confluence(candles)
        momentum = self._safe_momentum(candles)

        decision = self._clamp(
            0.35 * base
            + 0.20 * pressure
            + 0.15 * accel
            + 0.20 * confluence
            + 0.10 * momentum
        )

        elasticity = self._elasticity(candles)

        # ---- TIER ----
        if decision >= self.ELITE_THRESHOLD:
            tier = "ELITE"
        elif decision >= self.STRONG_THRESHOLD:
            tier = "STRONG"
        elif decision >= self.ACTIVE_THRESHOLD:
            tier = "ACTIVE"
        else:
            tier = "WATCH"

        # ---- EXECUTION ----
        execute = False

        if tier == "ELITE":
            execute = True

        elif tier == "STRONG":
            if regime not in {"CHAOTIC"} and elasticity > 0.0015:
                execute = True

        elif tier == "ACTIVE":
            if (
                decision >= 0.32
                and elasticity > 0.0020
                and regime not in {"CHAOTIC", "UNSTABLE"}
            ):
                execute = True

        return {
            "asset": asset,
            "execute_trade": execute,
            "signal_tier": tier,
            "decision_score": round(decision, 4),
            "elasticity_score": round(elasticity, 4),
            "regime": regime,
        }

    # ---------------------------------------------------------
    # SAFE FALLBACKS (same core logic)
    # ---------------------------------------------------------

    def _safe_ai(self, candles):
        closes = [self._f(c.get("close")) for c in candles]
        mean = sum(closes[-20:]) / 20
        return self._clamp(abs(closes[-1] - mean) / mean * 8)

    def _safe_pressure(self, candles):
        closes = [self._f(c.get("close")) for c in candles]
        mean = sum(closes[-20:]) / 20
        return self._clamp(abs(closes[-1] - mean) / mean * 10)

    def _safe_accel(self, candles):
        closes = [self._f(c.get("close")) for c in candles]
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        return self._clamp(sum(abs(x) for x in deltas[-3:]) / 3)

    def _safe_confluence(self, candles):
        closes = [self._f(c.get("close")) for c in candles]
        m5 = sum(closes[-5:]) / 5
        m20 = sum(closes[-20:]) / 20
        return self._clamp(abs(m5 - m20) / m20 * 10)

    def _safe_momentum(self, candles):
        closes = [self._f(c.get("close")) for c in candles]
        return self._clamp(abs(closes[-1] - closes[-5]) / closes[-5] * 8)

    def _elasticity(self, candles):
        closes = [self._f(c.get("close")) for c in candles[-10:]]
        avg = sum(closes) / len(closes)
        return self._clamp(abs(closes[-1] - avg) / closes[-1])

    def _get_regime(self, candles):
        try:
            r = self.regime_detector.detect_regime(candles)
            return str(r.get("regime", "NEUTRAL")).upper()
        except:
            return "NEUTRAL"

    def _normalize(self, c):
        if isinstance(c, dict):
            return c
        return {
            "open": getattr(c, "open", 0),
            "high": getattr(c, "high", 0),
            "low": getattr(c, "low", 0),
            "close": getattr(c, "close", 0),
        }

    def _f(self, v):
        try:
            return float(v)
        except:
            return 0.0

    def _clamp(self, v):
        return max(0.0, min(float(v), 1.0))

    def _empty(self, asset):
        return {
            "asset": asset,
            "execute_trade": False,
            "signal_tier": "NONE",
            "decision_score": 0.0,
            "elasticity_score": 0.0,
            "regime": "UNKNOWN",
        }