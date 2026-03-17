from __future__ import annotations

from typing import Any, Dict, List

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.elite_signal_classifier import EliteSignalClassifier
from backend.intelligence.market_regime_detector import MarketRegimeDetector
from backend.intelligence.opportunity_momentum_window_engine import (
    OpportunityMomentumWindowEngine,
)
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import (
    PressureAccelerationEngine,
)
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine
from backend.intelligence.vwap_deviation_engine import VWAPDeviationEngine
from backend.intelligence.vwap_elasticity_engine import VWAPElasticityEngine


class TradeDecisionOrchestrator:
    """
    Central trade decision orchestrator for Capital Strata Systems.

    Purpose:
    - apply final intelligence and confluence checks before trade execution
    - enforce VWAP deviation + elasticity + elite classification
    - preserve backward-compatible output for the live dashboard
    - expose richer scoring for tuning, diagnostics, and auditability

    The orchestrator fuses:
    - market regime
    - AI opportunity score
    - signal confluence
    - opportunity pressure
    - pressure acceleration
    - momentum window analysis

    Output contract:
    {
        "execute_trade": bool,
        "regime": str,
        "regime_reason": str,
        "confluence_score": float,
        "ai_score": float,
        "pressure_score": float,
        "acceleration_score": float,
        "momentum_score": float,
        "decision_score": float,
        "vwap_dev_abs": float,
        "vwap_dev_score": float,
        "elasticity_score": float,
        "signal_tier": str,
    }
    """

    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()

        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()

        self.vwap_deviation_engine = VWAPDeviationEngine()
        self.vwap_elasticity_engine = VWAPElasticityEngine()
        self.elite_signal_classifier = EliteSignalClassifier()

        self.mean_reversion_threshold = 0.46
        self.trend_threshold = 0.58
        self.breakout_threshold = 0.66

        self.weights = {
            "ai_score": 0.22,
            "confluence_score": 0.18,
            "pressure_score": 0.16,
            "acceleration_score": 0.10,
            "momentum_score": 0.08,
            "regime_confidence": 0.06,
            "vwap_dev_score": 0.10,
            "elasticity_score": 0.10,
        }

    def evaluate_trade(
        self,
        asset: str,
        candles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not candles or len(candles) < 20:
            return self._reject_payload(reason="insufficient candle history")

        regime_info = self.regime_detector.detect_regime(candles)
        regime = str(regime_info.get("regime", "UNSTABLE")).upper()
        regime_reason = str(regime_info.get("reason", "unknown"))
        regime_confidence = self._clamp01(regime_info.get("confidence", 0.0))

        ai_score = self._safe_ai_score(asset=asset, candles=candles)
        confluence_score = self._safe_confluence_score(
            asset=asset,
            candles=candles,
            regime=regime,
            regime_confidence=regime_confidence,
        )
        pressure_score = self._safe_pressure_score(asset=asset, candles=candles)
        acceleration_score = self._safe_acceleration_score(asset=asset, candles=candles)
        momentum_score = self._safe_momentum_score(asset=asset, candles=candles)

        vwap_dev_abs, vwap_dev_score = self._safe_vwap_deviation(
            asset=asset,
            candles=candles,
        )
        elasticity_score = self._safe_vwap_elasticity(
            asset=asset,
            candles=candles,
        )

        decision_score = self._compute_decision_score(
            ai_score=ai_score,
            confluence_score=confluence_score,
            pressure_score=pressure_score,
            acceleration_score=acceleration_score,
            momentum_score=momentum_score,
            regime_confidence=regime_confidence,
            vwap_dev_score=vwap_dev_score,
            elasticity_score=elasticity_score,
        )

        signal_tier = self._classify_signal(
            confluence_score=confluence_score,
            pressure_score=pressure_score,
            acceleration_score=acceleration_score,
            vwap_dev_abs=vwap_dev_abs,
            decision_score=decision_score,
        )

        threshold_pass = self._should_execute_trade(
            regime=regime,
            decision_score=decision_score,
        )

        execute_trade = threshold_pass and signal_tier == "ELITE"

        return {
            "execute_trade": execute_trade,
            "regime": regime,
            "regime_reason": regime_reason,
            "confluence_score": round(confluence_score, 4),
            "ai_score": round(ai_score, 4),
            "pressure_score": round(pressure_score, 4),
            "acceleration_score": round(acceleration_score, 4),
            "momentum_score": round(momentum_score, 4),
            "decision_score": round(decision_score, 4),
            "vwap_dev_abs": round(vwap_dev_abs, 6),
            "vwap_dev_score": round(vwap_dev_score, 4),
            "elasticity_score": round(elasticity_score, 4),
            "signal_tier": signal_tier,
        }

    def _reject_payload(self, *, reason: str) -> Dict[str, Any]:
        return {
            "execute_trade": False,
            "regime": "UNSTABLE",
            "regime_reason": reason,
            "confluence_score": 0.0,
            "ai_score": 0.0,
            "pressure_score": 0.0,
            "acceleration_score": 0.0,
            "momentum_score": 0.0,
            "decision_score": 0.0,
            "vwap_dev_abs": 0.0,
            "vwap_dev_score": 0.0,
            "elasticity_score": 0.0,
            "signal_tier": "WATCH",
        }

    def evaluate(self, market_features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compatibility wrapper for orchestration-style callers that pass a single feature dict.
        Expected keys:
        - asset or symbol
        - candles
        """
        asset = str(market_features.get("asset") or market_features.get("symbol") or "UNKNOWN")
        candles = market_features.get("candles", []) or []

        result = self.evaluate_trade(asset=asset, candles=candles)

        direction = "NONE"
        regime = result.get("regime", "UNSTABLE")

        if regime in ("TREND", "BREAKOUT"):
            direction = "LONG"
        elif regime == "MEAN_REVERSION":
            direction = "NONE"

        decision_score = float(result.get("decision_score", 0.0))

        if decision_score >= 0.66:
            signal_class = "ELITE"
        elif decision_score >= 0.50:
            signal_class = "STRONG"
        elif decision_score >= 0.40:
            signal_class = "WEAK"
        else:
            signal_class = "NONE"

        return {
            "signal_class": signal_class,
            "confidence": round(decision_score, 4),
            "direction": direction,
            "reason": result.get("regime_reason", "multi-engine evaluation"),
            "execute_trade": result.get("execute_trade", False),
            "regime": regime,
        }

    def _compute_decision_score(
        self,
        *,
        ai_score: float,
        confluence_score: float,
        pressure_score: float,
        acceleration_score: float,
        momentum_score: float,
        regime_confidence: float,
        vwap_dev_score: float,
        elasticity_score: float,
    ) -> float:
        score = (
            self.weights["ai_score"] * ai_score
            + self.weights["confluence_score"] * confluence_score
            + self.weights["pressure_score"] * pressure_score
            + self.weights["acceleration_score"] * acceleration_score
            + self.weights["momentum_score"] * momentum_score
            + self.weights["regime_confidence"] * regime_confidence
            + self.weights["vwap_dev_score"] * vwap_dev_score
            + self.weights["elasticity_score"] * elasticity_score
        )
        return self._clamp01(score)

    def _should_execute_trade(self, *, regime: str, decision_score: float) -> bool:
        if regime == "MEAN_REVERSION":
            return decision_score >= self.mean_reversion_threshold
        if regime == "TREND":
            return decision_score >= self.trend_threshold
        if regime == "BREAKOUT":
            return decision_score >= self.breakout_threshold
        return False

    def _classify_signal(
        self,
        *,
        confluence_score: float,
        pressure_score: float,
        acceleration_score: float,
        vwap_dev_abs: float,
        decision_score: float,
    ) -> str:
        rows = [
            {
                "confluence_score": confluence_score,
                "pressure_score": pressure_score,
                "pressure_acceleration": acceleration_score,
                "vwap_dev_abs": vwap_dev_abs,
                "trade_score": decision_score,
            }
        ]

        try:
            classified = self.elite_signal_classifier.classify(rows)
            if classified and isinstance(classified[0], dict):
                return str(classified[0].get("signal_tier", "WATCH")).upper()
        except Exception:
            pass

        return "WATCH"

    def _safe_ai_score(self, *, asset: str, candles: List[Dict[str, Any]]) -> float:
        try:
            if hasattr(self.ai_scorer, "score_opportunity"):
                result = self.ai_scorer.score_opportunity(asset=asset, candles=candles)
                return self._extract_score(result)

            if hasattr(self.ai_scorer, "score_asset"):
                result = self.ai_scorer.score_asset(asset=asset, candles=candles)
                return self._extract_score(result)
        except Exception:
            pass

        return self._fallback_ai_score(candles)

    def _safe_confluence_score(
        self,
        *,
        asset: str,
        candles: List[Dict[str, Any]],
        regime: str,
        regime_confidence: float,
    ) -> float:
        try:
            if hasattr(self.signal_confluence_engine, "compute_confluence"):
                result = self.signal_confluence_engine.compute_confluence(
                    asset=asset,
                    candles=candles,
                    regime=regime,
                )
                return self._extract_score(result)

            if hasattr(self.signal_confluence_engine, "evaluate"):
                result = self.signal_confluence_engine.evaluate(
                    asset=asset,
                    candles=candles,
                    regime=regime,
                )
                return self._extract_score(result)
        except Exception:
            pass

        return self._fallback_confluence_score(candles, regime_confidence)

    def _safe_pressure_score(
        self,
        *,
        asset: str,
        candles: List[Dict[str, Any]],
    ) -> float:
        try:
            if hasattr(self.pressure_engine, "compute_pressure"):
                result = self.pressure_engine.compute_pressure(
                    asset=asset,
                    candles=candles,
                )
                return self._extract_score(result)

            if hasattr(self.pressure_engine, "evaluate"):
                result = self.pressure_engine.evaluate(
                    asset=asset,
                    candles=candles,
                )
                return self._extract_score(result)
        except Exception:
            pass

        return self._fallback_pressure_score(candles)

    def _safe_acceleration_score(
        self,
        *,
        asset: str,
        candles: List[Dict[str, Any]],
    ) -> float:
        try:
            if hasattr(self.acceleration_engine, "compute_acceleration"):
                result = self.acceleration_engine.compute_acceleration(
                    asset=asset,
                    candles=candles,
                )
                return self._extract_score(result)

            if hasattr(self.acceleration_engine, "evaluate"):
                result = self.acceleration_engine.evaluate(
                    asset=asset,
                    candles=candles,
                )
                return self._extract_score(result)
        except Exception:
            pass

        return self._fallback_acceleration_score(candles)

    def _safe_momentum_score(
        self,
        *,
        asset: str,
        candles: List[Dict[str, Any]],
    ) -> float:
        try:
            if hasattr(self.momentum_engine, "compute_momentum_window"):
                result = self.momentum_engine.compute_momentum_window(
                    asset=asset,
                    candles=candles,
                )
                return self._extract_score(result)

            if hasattr(self.momentum_engine, "evaluate"):
                result = self.momentum_engine.evaluate(
                    asset=asset,
                    candles=candles,
                )
                return self._extract_score(result)
        except Exception:
            pass

        return self._fallback_momentum_score(candles)

    def _safe_vwap_deviation(
        self,
        *,
        asset: str,
        candles: List[Dict[str, Any]],
    ) -> tuple[float, float]:
        try:
            if hasattr(self.vwap_deviation_engine, "evaluate"):
                result = self.vwap_deviation_engine.evaluate(
                    asset=asset,
                    candles=candles,
                )
                return self._extract_vwap_metrics(result)

            if hasattr(self.vwap_deviation_engine, "compute"):
                result = self.vwap_deviation_engine.compute(
                    asset=asset,
                    candles=candles,
                )
                return self._extract_vwap_metrics(result)
        except Exception:
            pass

        return self._fallback_vwap_deviation(candles)

    def _safe_vwap_elasticity(
        self,
        *,
        asset: str,
        candles: List[Dict[str, Any]],
    ) -> float:
        try:
            if hasattr(self.vwap_elasticity_engine, "evaluate"):
                result = self.vwap_elasticity_engine.evaluate(
                    asset=asset,
                    candles=candles,
                )
                return self._extract_score(result)

            if hasattr(self.vwap_elasticity_engine, "compute"):
                result = self.vwap_elasticity_engine.compute(
                    asset=asset,
                    candles=candles,
                )
                return self._extract_score(result)
        except Exception:
            pass

        return self._fallback_vwap_elasticity(candles)

    def _fallback_ai_score(self, candles: List[Dict[str, Any]]) -> float:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles if c]
        if len(closes) < 20:
            return 0.0

        last = closes[-1]
        mean_20 = sum(closes[-20:]) / 20.0
        if mean_20 <= 0:
            return 0.0

        deviation = abs(last - mean_20) / mean_20
        return self._clamp01(min(deviation * 10.0, 0.85))

    def _fallback_confluence_score(
        self,
        candles: List[Dict[str, Any]],
        regime_confidence: float,
    ) -> float:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles]
        highs = [self._to_float(c.get("high"), 0.0) for c in candles]
        lows = [self._to_float(c.get("low"), 0.0) for c in candles]

        if len(closes) < 20:
            return 0.0

        last = closes[-1]
        mean_5 = sum(closes[-5:]) / 5.0
        mean_20 = sum(closes[-20:]) / 20.0

        mean_reversion_component = 0.0
        if mean_20 > 0:
            deviation = abs(last - mean_20) / mean_20
            mean_reversion_component = min(deviation * 8.0, 0.35)

        momentum_component = 0.0
        if mean_5 > 0 and mean_20 > 0:
            slope = abs(mean_5 - mean_20) / mean_20
            momentum_component = min(slope * 10.0, 0.20)

        range_component = 0.0
        recent_ranges = []
        for h, l, c in zip(highs[-10:], lows[-10:], closes[-10:]):
            if c > 0:
                recent_ranges.append(abs(h - l) / c)

        if recent_ranges:
            avg_range = sum(recent_ranges) / len(recent_ranges)
            if avg_range <= 0.01:
                range_component = 0.20
            elif avg_range <= 0.02:
                range_component = 0.12
            elif avg_range <= 0.03:
                range_component = 0.06

        confidence_component = regime_confidence * 0.25

        score = (
            mean_reversion_component
            + momentum_component
            + range_component
            + confidence_component
        )
        return self._clamp01(score)

    def _fallback_pressure_score(self, candles: List[Dict[str, Any]]) -> float:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles]
        if len(closes) < 20:
            return 0.0

        last = closes[-1]
        mean_20 = sum(closes[-20:]) / 20.0
        if mean_20 <= 0:
            return 0.0

        stretch = abs(last - mean_20) / mean_20
        return self._clamp01(min(stretch * 12.0, 0.90))

    def _fallback_acceleration_score(self, candles: List[Dict[str, Any]]) -> float:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles]
        if len(closes) < 6:
            return 0.0

        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        if len(deltas) < 5:
            return 0.0

        recent = deltas[-3:]
        prior = deltas[-5:-2]

        recent_avg = sum(abs(x) for x in recent) / max(len(recent), 1)
        prior_avg = sum(abs(x) for x in prior) / max(len(prior), 1)

        if prior_avg <= 0:
            return 0.0

        accel = max(0.0, (recent_avg - prior_avg) / prior_avg)
        return self._clamp01(min(accel, 0.80))

    def _fallback_momentum_score(self, candles: List[Dict[str, Any]]) -> float:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles]
        if len(closes) < 10:
            return 0.0

        mean_5 = sum(closes[-5:]) / 5.0
        mean_10 = sum(closes[-10:]) / 10.0
        if mean_10 <= 0:
            return 0.0

        momentum = abs(mean_5 - mean_10) / mean_10
        return self._clamp01(min(momentum * 10.0, 0.75))

    def _fallback_vwap_deviation(self, candles: List[Dict[str, Any]]) -> tuple[float, float]:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles]
        volumes = [self._to_float(c.get("volume"), 0.0) for c in candles]

        if len(closes) < 20 or len(volumes) < 20:
            return 0.0, 0.0

        total_pv = 0.0
        total_volume = 0.0
        for close, volume in zip(closes[-20:], volumes[-20:]):
            total_pv += close * volume
            total_volume += volume

        if total_volume <= 0:
            return 0.0, 0.0

        vwap = total_pv / total_volume
        if vwap <= 0:
            return 0.0, 0.0

        dev_abs = abs(closes[-1] - vwap) / vwap
        dev_score = self._clamp01(min(dev_abs * 20.0, 1.0))
        return dev_abs, dev_score

    def _fallback_vwap_elasticity(self, candles: List[Dict[str, Any]]) -> float:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles]
        if len(closes) < 20:
            return 0.0

        mean_20 = sum(closes[-20:]) / 20.0
        if mean_20 <= 0:
            return 0.0

        abs_moves = [
            abs(closes[i] - closes[i - 1]) / mean_20
            for i in range(1, len(closes[-20:]))
        ]
        if not abs_moves:
            return 0.0

        avg_move = sum(abs_moves) / len(abs_moves)
        return self._clamp01(min(avg_move * 30.0, 1.0))

    def _extract_score(self, result: Any) -> float:
        if isinstance(result, (int, float)):
            return self._clamp01(result)

        if isinstance(result, dict):
            for key in (
                "score",
                "final_score",
                "decision_score",
                "confluence_score",
                "pressure_score",
                "acceleration_score",
                "momentum_score",
                "probability",
                "confidence",
                "elasticity_score",
                "vwap_dev_score",
            ):
                if key in result:
                    return self._clamp01(result.get(key, 0.0))

        return 0.0

    def _extract_vwap_metrics(self, result: Any) -> tuple[float, float]:
        if isinstance(result, dict):
            dev_abs = self._to_float(
                result.get("vwap_dev_abs", result.get("deviation_abs", 0.0)),
                0.0,
            )
            dev_score = self._clamp01(
                result.get("vwap_dev_score", result.get("score", 0.0))
            )
            return dev_abs, dev_score

        if isinstance(result, (int, float)):
            return 0.0, self._clamp01(result)

        return 0.0, 0.0

    @staticmethod
    def _clamp01(value: Any) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(numeric, 1.0))

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default


TradeDecisionEngine = TradeDecisionOrchestrator