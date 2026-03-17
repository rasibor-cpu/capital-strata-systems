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
    Balanced Phase 2 orchestrator.

    Goals:
    - preserve controlled activation
    - improve entry quality
    - reduce weak ACTIVE executions
    - keep future room for later aggressive Mode B
    """

    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()
        self.ai_scorer = AIOpportunityScorer()
        self.pressure_engine = OpportunityPressureEngine()
        self.accel_engine = PressureAccelerationEngine()
        self.confluence_engine = SignalConfluenceEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()

        # Balanced thresholds now, with room for later B-mode loosening/tuning
        self.ELITE_THRESHOLD = 0.55
        self.STRONG_THRESHOLD = 0.42
        self.ACTIVE_THRESHOLD = 0.32

        self.STRONG_ELASTICITY_MIN = 0.0015
        self.ACTIVE_ELASTICITY_MIN = 0.0020

    def evaluate_trade(
        self,
        asset: str,
        candles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not candles or len(candles) < 20:
            return self._empty(asset)

        candles = [self._normalize_candle(c) for c in candles]

        regime_info = self._safe_regime(asset=asset, candles=candles)
        regime = str(regime_info.get("regime", "NEUTRAL")).upper()

        base_score = self._safe_ai_score(asset=asset, candles=candles)
        pressure = self._safe_pressure_score(asset=asset, candles=candles)
        accel = self._safe_accel_score(asset=asset, candles=candles)
        confluence = self._safe_confluence_score(
            asset=asset,
            candles=candles,
            regime=regime,
        )
        momentum = self._safe_momentum_score(asset=asset, candles=candles)

        decision_score = self._clamp01(
            0.35 * base_score
            + 0.20 * pressure
            + 0.15 * accel
            + 0.20 * confluence
            + 0.10 * momentum
        )

        elasticity = self._compute_elasticity_proxy(candles)

        if decision_score >= self.ELITE_THRESHOLD:
            tier = "ELITE"
        elif decision_score >= self.STRONG_THRESHOLD:
            tier = "STRONG"
        elif decision_score >= self.ACTIVE_THRESHOLD:
            tier = "ACTIVE"
        else:
            tier = "WATCH"

        execute = False

        if tier == "ELITE":
            execute = True

        elif tier == "STRONG":
            if regime not in {"CHAOTIC", "UNSTABLE"} and elasticity > self.STRONG_ELASTICITY_MIN:
                execute = True

        elif tier == "ACTIVE":
            if (
                decision_score >= self.ACTIVE_THRESHOLD
                and elasticity > self.ACTIVE_ELASTICITY_MIN
                and regime not in {"CHAOTIC", "UNSTABLE"}
            ):
                execute = True

        return {
            "asset": asset,
            "execute_trade": execute,
            "signal_tier": tier,
            "decision_score": round(decision_score, 4),
            "elasticity_score": round(elasticity, 4),
            "regime": regime,
            "ai_score": round(base_score, 4),
            "pressure_score": round(pressure, 4),
            "acceleration_score": round(accel, 4),
            "confluence_score": round(confluence, 4),
            "momentum_score": round(momentum, 4),
        }

    def _safe_regime(self, *, asset: str, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            if hasattr(self.regime_detector, "detect_regime"):
                result = self.regime_detector.detect_regime(candles)
                if isinstance(result, dict):
                    return result
            if hasattr(self.regime_detector, "detect"):
                result = self.regime_detector.detect(candles)
                if isinstance(result, dict):
                    return result
        except Exception:
            pass

        return {"regime": "NEUTRAL"}

    def _safe_ai_score(self, *, asset: str, candles: List[Dict[str, Any]]) -> float:
        try:
            if hasattr(self.ai_scorer, "score_opportunity"):
                return self._extract_score(
                    self.ai_scorer.score_opportunity(asset=asset, candles=candles)
                )
            if hasattr(self.ai_scorer, "score_asset"):
                return self._extract_score(
                    self.ai_scorer.score_asset(asset=asset, candles=candles)
                )
            if hasattr(self.ai_scorer, "rank_opportunities"):
                ranked = self.ai_scorer.rank_opportunities(
                    [{"symbol": asset, "candles": candles}]
                )
                if isinstance(ranked, list) and ranked:
                    return self._extract_score(ranked[0])
        except Exception:
            pass

        return self._fallback_ai_score(candles)

    def _safe_pressure_score(self, *, asset: str, candles: List[Dict[str, Any]]) -> float:
        try:
            if hasattr(self.pressure_engine, "compute_pressure"):
                return self._extract_score(
                    self.pressure_engine.compute_pressure(asset=asset, candles=candles)
                )
            if hasattr(self.pressure_engine, "compute"):
                return self._extract_score(self.pressure_engine.compute(candles))
            if hasattr(self.pressure_engine, "evaluate"):
                return self._extract_score(
                    self.pressure_engine.evaluate(asset=asset, candles=candles)
                )
        except Exception:
            pass

        return self._fallback_pressure_score(candles)

    def _safe_accel_score(self, *, asset: str, candles: List[Dict[str, Any]]) -> float:
        try:
            if hasattr(self.accel_engine, "compute_acceleration"):
                return self._extract_score(
                    self.accel_engine.compute_acceleration(asset=asset, candles=candles)
                )
            if hasattr(self.accel_engine, "compute"):
                return self._extract_score(self.accel_engine.compute(candles))
            if hasattr(self.accel_engine, "evaluate"):
                return self._extract_score(
                    self.accel_engine.evaluate(asset=asset, candles=candles)
                )
        except Exception:
            pass

        return self._fallback_accel_score(candles)

    def _safe_confluence_score(
        self,
        *,
        asset: str,
        candles: List[Dict[str, Any]],
        regime: str,
    ) -> float:
        try:
            if hasattr(self.confluence_engine, "compute_confluence"):
                return self._extract_score(
                    self.confluence_engine.compute_confluence(
                        asset=asset,
                        candles=candles,
                        regime=regime,
                    )
                )
            if hasattr(self.confluence_engine, "compute"):
                return self._extract_score(self.confluence_engine.compute(candles))
            if hasattr(self.confluence_engine, "evaluate"):
                return self._extract_score(
                    self.confluence_engine.evaluate(
                        asset=asset,
                        candles=candles,
                        regime=regime,
                    )
                )
        except Exception:
            pass

        return self._fallback_confluence_score(candles)

    def _safe_momentum_score(self, *, asset: str, candles: List[Dict[str, Any]]) -> float:
        try:
            if hasattr(self.momentum_engine, "compute_momentum_window"):
                return self._extract_score(
                    self.momentum_engine.compute_momentum_window(
                        asset=asset,
                        candles=candles,
                    )
                )
            if hasattr(self.momentum_engine, "compute"):
                return self._extract_score(self.momentum_engine.compute(candles))
            if hasattr(self.momentum_engine, "evaluate"):
                return self._extract_score(
                    self.momentum_engine.evaluate(asset=asset, candles=candles)
                )
        except Exception:
            pass

        return self._fallback_momentum_score(candles)

    def _fallback_ai_score(self, candles: List[Dict[str, Any]]) -> float:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles]
        if len(closes) < 20:
            return 0.0

        last = closes[-1]
        mean_20 = sum(closes[-20:]) / 20.0
        if mean_20 <= 0:
            return 0.0

        deviation = abs(last - mean_20) / mean_20
        return self._clamp01(min(deviation * 8.0, 0.85))

    def _fallback_pressure_score(self, candles: List[Dict[str, Any]]) -> float:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles]
        if len(closes) < 20:
            return 0.0

        mean_20 = sum(closes[-20:]) / 20.0
        if mean_20 <= 0:
            return 0.0

        stretch = abs(closes[-1] - mean_20) / mean_20
        return self._clamp01(min(stretch * 10.0, 0.90))

    def _fallback_accel_score(self, candles: List[Dict[str, Any]]) -> float:
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

    def _fallback_confluence_score(self, candles: List[Dict[str, Any]]) -> float:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles]
        highs = [self._to_float(c.get("high"), 0.0) for c in candles]
        lows = [self._to_float(c.get("low"), 0.0) for c in candles]

        if len(closes) < 20:
            return 0.0

        mean_5 = sum(closes[-5:]) / 5.0
        mean_20 = sum(closes[-20:]) / 20.0

        momentum_component = 0.0
        if mean_20 > 0:
            slope = abs(mean_5 - mean_20) / mean_20
            momentum_component = min(slope * 10.0, 0.40)

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
            else:
                range_component = 0.06

        return self._clamp01(momentum_component + range_component)

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

    def _compute_elasticity_proxy(self, candles: List[Dict[str, Any]]) -> float:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles[-10:]]
        if len(closes) < 2:
            return 0.0

        mean_close = sum(closes) / len(closes)
        last = closes[-1]
        if last <= 0:
            return 0.0

        return self._clamp01(abs(last - mean_close) / last)

    def _normalize_candle(self, candle: Any) -> Dict[str, Any]:
        if isinstance(candle, dict):
            return {
                "open": candle.get("open"),
                "high": candle.get("high"),
                "low": candle.get("low"),
                "close": candle.get("close"),
                "volume": candle.get("volume"),
            }

        return {
            "open": getattr(candle, "open", None),
            "high": getattr(candle, "high", None),
            "low": getattr(candle, "low", None),
            "close": getattr(candle, "close", None),
            "volume": getattr(candle, "volume", None),
        }

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
                "ai_score",
            ):
                if key in result:
                    return self._clamp01(result.get(key, 0.0))

        return 0.0

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

    def _empty(self, asset: str) -> Dict[str, Any]:
        return {
            "asset": asset,
            "execute_trade": False,
            "signal_tier": "NONE",
            "decision_score": 0.0,
            "elasticity_score": 0.0,
            "regime": "UNKNOWN",
            "ai_score": 0.0,
            "pressure_score": 0.0,
            "acceleration_score": 0.0,
            "confluence_score": 0.0,
            "momentum_score": 0.0,
        }


TradeDecisionEngine = TradeDecisionOrchestrator