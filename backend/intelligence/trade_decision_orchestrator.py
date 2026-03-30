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

try:
    from backend.intelligence.vwap_deviation_engine import VWAPDeviationEngine
except Exception:
    VWAPDeviationEngine = None

try:
    from backend.intelligence.vwap_elasticity_engine import VWAPElasticityEngine
except Exception:
    VWAPElasticityEngine = None

try:
    from backend.execution.cost_aware_gate import CostAwareGate
except Exception:
    CostAwareGate = None

try:
    from backend.execution.execution_cost_engine import ExecutionCostEngine
except Exception:
    try:
        from engine.execution.execution_cost_engine import ExecutionCostEngine
    except Exception:
        ExecutionCostEngine = None


class TradeDecisionOrchestrator:
    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()

        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()

        self.vwap_engine = VWAPDeviationEngine() if VWAPDeviationEngine else None
        self.elasticity_engine = VWAPElasticityEngine() if VWAPElasticityEngine else None

        self.cost_gate = CostAwareGate() if CostAwareGate else None
        self.cost_engine = ExecutionCostEngine() if ExecutionCostEngine else None

        self.mean_reversion_threshold = 0.20
        self.trend_threshold = 0.24
        self.breakout_threshold = 0.28

        self.weights = {
            "ai_score": 0.24,
            "confluence_score": 0.20,
            "pressure_fusion": 0.20,
            "momentum_score": 0.10,
            "vwap_score": 0.12,
            "elasticity_score": 0.08,
            "regime_confidence": 0.06,
        }

        self.EDGE_MULTIPLIER = 0.025
        self.COST_NOTIONAL = 1000.0

    def evaluate_trade(self, asset: str, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not candles or len(candles) < 20:
            return self._reject(asset, "INSUFFICIENT_DATA")

        regime_info = self._safe_detect_regime(candles)
        regime = str(regime_info.get("regime", "UNSTABLE")).upper()
        regime_confidence = self._clamp01(regime_info.get("confidence", 0.0))
        regime_reason = str(regime_info.get("reason", "unknown"))

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

        pressure_fusion = self._clamp01((pressure_score * 0.6) + (acceleration_score * 0.4))

        vwap_score = 0.0
        vwap_dev = 0.0
        if self.vwap_engine:
            try:
                vwap_data = self.vwap_engine.compute(candles)
                if isinstance(vwap_data, dict):
                    vwap_dev = abs(float(vwap_data.get("vwap_dev_abs", 0.0)))

                if 0.002 <= vwap_dev <= 0.015:
                    vwap_score = 1.0
                elif 0.015 < vwap_dev <= 0.025:
                    vwap_score = 0.7
                elif vwap_dev < 0.002:
                    vwap_score = 0.2
                else:
                    vwap_score = 0.4
            except Exception:
                pass

        elasticity_score = 0.0
        if self.elasticity_engine:
            try:
                enriched = self.elasticity_engine.enrich_rows(
                    [{"vwap_dev_abs": vwap_dev, "momentum": momentum_score}]
                )
                if enriched:
                    elasticity_score = self._clamp01(
                        self._safe_get(enriched[0], "elasticity_score", 0.0)
                    )
            except Exception:
                pass

        decision_score = self._clamp01(
            ai_score * self.weights["ai_score"]
            + confluence_score * self.weights["confluence_score"]
            + pressure_fusion * self.weights["pressure_fusion"]
            + momentum_score * self.weights["momentum_score"]
            + vwap_score * self.weights["vwap_score"]
            + elasticity_score * self.weights["elasticity_score"]
            + regime_confidence * self.weights["regime_confidence"]
        )

        if pressure_fusion < 0.15 or elasticity_score < 0.15:
            decision_score *= 0.75

        decision_score = self._clamp01(decision_score)

        expected_edge_bps = self._estimate_edge(decision_score)

        cost_components = self._estimate_cost_components(asset)
        execution_cost_bps = (
            (cost_components["total_cost_usd"] / self.COST_NOTIONAL) * 10000.0
        )

        cost_decision = self._apply_cost_gate(
            expected_edge_bps,
            execution_cost_bps,
            asset,
            decision_score,
        )

        execute_trade = self._should_execute_trade(
            regime=regime,
            decision_score=decision_score,
        )

        if decision_score >= 0.38:
            execute_trade = True

        if cost_decision.get("decision") != "APPROVE":
            if decision_score < 0.25:
                execute_trade = False

        expected_edge_value = 0.0
        cost_adjusted_edge_value = 0.0

        try:
            last_close = self._extract_last_close(candles)
            if last_close > 0 and self.cost_engine:
                expected_edge_value = decision_score * last_close * self.EDGE_MULTIPLIER

                if hasattr(self.cost_engine, "apply_costs"):
                    cost_adjusted_edge_value = self.cost_engine.apply_costs(
                        instrument=asset,
                        notional=self.COST_NOTIONAL,
                        raw_pnl=expected_edge_value,
                    )
                else:
                    cost_adjusted_edge_value = expected_edge_value
        except Exception:
            pass

        return {
            "asset": asset,
            "asset_class": self._classify_asset(asset),
            "execute_trade": execute_trade,
            "execute_flag": execute_trade,
            "cost_blocked": cost_decision.get("decision") != "APPROVE",
            "regime": regime,
            "regime_reason": regime_reason,
            "confluence_score": round(confluence_score, 4),
            "ai_score": round(ai_score, 4),
            "pressure_score": round(pressure_score, 4),
            "acceleration_score": round(acceleration_score, 4),
            "momentum_score": round(momentum_score, 4),
            "pressure_fusion": round(pressure_fusion, 4),
            "vwap_score": round(vwap_score, 4),
            "vwap_dev_abs": round(vwap_dev, 6),
            "elasticity_score": round(elasticity_score, 4),
            "decision_score": round(decision_score, 4),
            "expected_edge_bps": round(expected_edge_bps, 4),
            "execution_cost_bps": round(execution_cost_bps, 4),
            "cost_decision": cost_decision.get("decision"),
            "net_edge_bps": round(float(cost_decision.get("net_edge_bps", 0.0)), 4),
            "expected_edge_value": round(expected_edge_value, 6),
            "cost_adjusted_edge_value": round(cost_adjusted_edge_value, 6),
            "entry_costs": cost_components,
        }

    def _estimate_edge(self, decision_score: float) -> float:
        base = max(0.0, decision_score)
        return round(base * 260.0, 4)

    def _apply_cost_gate(
        self,
        expected_edge_bps: float,
        execution_cost_bps: float,
        asset: str,
        decision_score: float,
    ) -> Dict[str, Any]:
        net_edge_bps = expected_edge_bps - execution_cost_bps

        if self.cost_gate and hasattr(self.cost_gate, "evaluate"):
            try:
                result = self.cost_gate.evaluate(
                    instrument=asset,
                    expected_edge_bps=expected_edge_bps,
                    execution_cost_bps=execution_cost_bps,
                    decision_score=decision_score,
                )
                if isinstance(result, dict):
                    return {
                        "decision": result.get("decision", "APPROVE"),
                        "reason": result.get("reason", "COST_GATE"),
                        "net_edge_bps": float(result.get("net_edge_bps", net_edge_bps)),
                    }
            except Exception:
                pass

        if decision_score >= 0.35:
            return {
                "decision": "APPROVE",
                "reason": "HIGH_CONVICTION_OVERRIDE",
                "net_edge_bps": net_edge_bps,
            }

        if net_edge_bps > -10:
            return {
                "decision": "APPROVE",
                "reason": "TOLERANCE_BUFFER",
                "net_edge_bps": net_edge_bps,
            }

        return {
            "decision": "REJECT",
            "reason": "NET_EDGE_NEGATIVE",
            "net_edge_bps": net_edge_bps,
        }

    def _safe_detect_regime(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            if hasattr(self.regime_detector, "detect_regime"):
                result = self.regime_detector.detect_regime(candles)
                if isinstance(result, dict):
                    return result
        except Exception:
            pass

        return {
            "regime": "UNSTABLE",
            "confidence": 0.0,
            "reason": "fallback",
        }

    def _safe_ai_score(self, asset: str, candles: List[Dict[str, Any]]) -> float:
        row = self._build_row_from_candles(asset, candles)

        try:
            if hasattr(self.ai_scorer, "score_opportunity"):
                result = self.ai_scorer.score_opportunity(row)
                if isinstance(result, dict):
                    return self._clamp01(
                        result.get("opportunity_score", result.get("score", 0.0))
                    )
                return self._clamp01(result)

            if hasattr(self.ai_scorer, "score"):
                result = self.ai_scorer.score(row)
                if isinstance(result, dict):
                    return self._clamp01(
                        result.get("opportunity_score", result.get("score", 0.0))
                    )
                return self._clamp01(result)

            if hasattr(self.ai_scorer, "rank_opportunities"):
                ranked = self.ai_scorer.rank_opportunities([row])
                if ranked and isinstance(ranked, list):
                    top = ranked[0]
                    return self._clamp01(
                        self._safe_get(top, "opportunity_score", self._safe_get(top, "score", 0.0))
                    )
        except Exception:
            pass

        return 0.0

    def _safe_confluence_score(
        self,
        asset: str,
        candles: List[Dict[str, Any]],
        regime: str,
        regime_confidence: float,
    ) -> float:
        row = self._build_row_from_candles(asset, candles)
        row["regime"] = regime
        row["regime_confidence"] = regime_confidence

        try:
            if hasattr(self.signal_confluence_engine, "enrich_rows"):
                enriched = self.signal_confluence_engine.enrich_rows([row])
                if enriched:
                    return self._clamp01(
                        self._safe_get(
                            enriched[0],
                            "confluence_score",
                            self._safe_get(enriched[0], "score", 0.0),
                        )
                    )

            if hasattr(self.signal_confluence_engine, "compute"):
                result = self.signal_confluence_engine.compute(row)
                if isinstance(result, dict):
                    return self._clamp01(
                        result.get("confluence_score", result.get("score", 0.0))
                    )
                return self._clamp01(result)
        except Exception:
            pass

        return 0.0

    def _safe_pressure_score(self, asset: str, candles: List[Dict[str, Any]]) -> float:
        row = self._build_row_from_candles(asset, candles)

        try:
            if hasattr(self.pressure_engine, "enrich_rows"):
                enriched = self.pressure_engine.enrich_rows([row])
                if enriched:
                    return self._clamp01(
                        self._safe_get(
                            enriched[0],
                            "pressure_score",
                            self._safe_get(enriched[0], "buy_pressure", 0.0),
                        )
                    )

            if hasattr(self.pressure_engine, "compute"):
                result = self.pressure_engine.compute(row)
                if isinstance(result, dict):
                    return self._clamp01(
                        result.get("pressure_score", result.get("buy_pressure", 0.0))
                    )
                return self._clamp01(result)
        except Exception:
            pass

        return 0.0

    def _safe_acceleration_score(self, asset: str, candles: List[Dict[str, Any]]) -> float:
        row = self._build_row_from_candles(asset, candles)

        try:
            if hasattr(self.acceleration_engine, "enrich_rows"):
                enriched = self.acceleration_engine.enrich_rows([row])
                if enriched:
                    raw = self._safe_get(
                        enriched[0],
                        "acceleration_score",
                        self._safe_get(enriched[0], "pressure_acceleration", 0.0),
                    )
                    return self._clamp01(abs(float(raw)))

            if hasattr(self.acceleration_engine, "compute"):
                result = self.acceleration_engine.compute(row)
                if isinstance(result, dict):
                    raw = result.get(
                        "acceleration_score",
                        result.get("pressure_acceleration", 0.0),
                    )
                    return self._clamp01(abs(float(raw)))
                return self._clamp01(abs(float(result)))
        except Exception:
            pass

        return 0.0

    def _safe_momentum_score(self, asset: str, candles: List[Dict[str, Any]]) -> float:
        row = self._build_row_from_candles(asset, candles)

        try:
            if hasattr(self.momentum_engine, "enrich_rows"):
                enriched = self.momentum_engine.enrich_rows([row])
                if enriched:
                    return self._clamp01(
                        self._safe_get(
                            enriched[0],
                            "momentum_score",
                            self._safe_get(enriched[0], "trend_efficiency", 0.0),
                        )
                    )

            if hasattr(self.momentum_engine, "compute"):
                result = self.momentum_engine.compute(row)
                if isinstance(result, dict):
                    return self._clamp01(
                        result.get("momentum_score", result.get("trend_efficiency", 0.0))
                    )
                return self._clamp01(result)
        except Exception:
            pass

        closes = [self._candle_close(c) for c in candles[-5:]]
        closes = [c for c in closes if c > 0]
        if len(closes) < 2:
            return 0.0

        move = (closes[-1] - closes[0]) / (closes[0] + 1e-9)
        return self._clamp01(abs(move) * 50.0)

    def _estimate_cost_components(self, asset: str) -> Dict[str, float]:
        if self.cost_engine:
            try:
                if hasattr(self.cost_engine, "estimate_total_cost"):
                    result = self.cost_engine.estimate_total_cost(
                        instrument=asset,
                        notional=self.COST_NOTIONAL,
                    )
                    if isinstance(result, dict):
                        total = float(result.get("total_cost_usd", 0.0))
                        spread = float(result.get("spread_cost_usd", 0.0))
                        slippage = float(result.get("slippage_cost_usd", 0.0))
                        fees = float(result.get("fees_usd", 0.0))
                        return {
                            "spread_cost_usd": spread,
                            "slippage_cost_usd": slippage,
                            "fees_usd": fees,
                            "total_cost_usd": total if total > 0 else (spread + slippage + fees),
                        }

                if hasattr(self.cost_engine, "estimate_costs"):
                    result = self.cost_engine.estimate_costs(
                        instrument=asset,
                        notional=self.COST_NOTIONAL,
                    )
                    if isinstance(result, dict):
                        total = float(result.get("total_cost_usd", result.get("total", 0.0)))
                        spread = float(result.get("spread_cost_usd", result.get("spread", 0.0)))
                        slippage = float(
                            result.get("slippage_cost_usd", result.get("slippage", 0.0))
                        )
                        fees = float(result.get("fees_usd", result.get("fees", 0.0)))
                        if total <= 0:
                            total = spread + slippage + fees
                        return {
                            "spread_cost_usd": spread,
                            "slippage_cost_usd": slippage,
                            "fees_usd": fees,
                            "total_cost_usd": total,
                        }
            except Exception:
                pass

        asset_class = self._classify_asset(asset)
        if asset_class == "FX":
            spread = 0.60
            slippage = 0.35
            fees = 0.00
        elif asset_class == "CRYPTO":
            spread = 1.20
            slippage = 0.65
            fees = 0.40
        elif asset_class == "FUTURES":
            spread = 0.90
            slippage = 0.50
            fees = 0.60
        else:
            spread = 1.00
            slippage = 0.50
            fees = 0.25

        total = spread + slippage + fees
        return {
            "spread_cost_usd": spread,
            "slippage_cost_usd": slippage,
            "fees_usd": fees,
            "total_cost_usd": total,
        }

    def _should_execute_trade(self, regime: str, decision_score: float) -> bool:
        regime = str(regime).upper()

        if regime == "MEAN_REVERSION":
            return decision_score >= self.mean_reversion_threshold

        if regime == "TREND":
            return decision_score >= self.trend_threshold

        if regime == "BREAKOUT":
            return decision_score >= self.breakout_threshold

        if regime in {"VOLATILE", "RANGE", "NEUTRAL"}:
            return decision_score >= 0.26

        return decision_score >= 0.30

    def _build_row_from_candles(
        self,
        asset: str,
        candles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        closes = [self._candle_close(c) for c in candles if self._candle_close(c) > 0]
        highs = [self._candle_high(c) for c in candles if self._candle_high(c) > 0]
        lows = [self._candle_low(c) for c in candles if self._candle_low(c) > 0]
        volumes = [self._candle_volume(c) for c in candles if self._candle_volume(c) >= 0]

        last_close = closes[-1] if closes else 0.0
        prev_close = closes[-2] if len(closes) >= 2 else last_close

        momentum = 0.0
        if prev_close > 0:
            momentum = (last_close - prev_close) / (prev_close + 1e-9)

        recent_high = max(highs[-20:], default=last_close)
        recent_low = min(lows[-20:], default=last_close)

        total_range = max(highs[-20:], default=last_close) - min(lows[-20:], default=last_close)
        price_compression = 0.0
        if last_close > 0:
            norm_range = total_range / (last_close + 1e-9)
            price_compression = self._clamp01(1.0 - min(norm_range / 0.08, 1.0))

        volume = volumes[-1] if volumes else 0.0
        avg_volume = sum(volumes[-20:]) / max(len(volumes[-20:]), 1)

        vwap = self._estimate_vwap(candles, last_close)
        vwap_dev = 0.0
        if vwap > 0:
            vwap_dev = (last_close - vwap) / (vwap + 1e-9)

        return {
            "symbol": asset,
            "asset": asset,
            "candles": candles,
            "price": last_close,
            "current_price": last_close,
            "vwap": vwap,
            "vwap_dev": vwap_dev,
            "vwap_distance": vwap_dev,
            "volume": volume,
            "avg_volume": avg_volume,
            "avg_volume_24h": avg_volume,
            "volume_24h": max(volume, avg_volume),
            "momentum": momentum,
            "velocity": momentum,
            "buy_pressure": max(momentum, 0.0),
            "sell_pressure": max(-momentum, 0.0),
            "recent_high": recent_high,
            "recent_low": recent_low,
            "price_compression": price_compression,
            "compression": price_compression,
            "trend_efficiency": self._clamp01(abs(momentum) * 20.0),
            "mean_reversion_score": self._clamp01(abs(vwap_dev) * 20.0),
            "spread_bps": 2.0,
            "slippage_bps": 3.0,
            "top_of_book_depth": 100000.0,
            "order_flow_delta": 0.0,
            "rejection_strength": 0.0,
            "wick_reversal_strength": 0.0,
            "liquidity_sweep_flag": False,
        }

    def _estimate_vwap(self, candles: List[Dict[str, Any]], fallback_price: float) -> float:
        total_pv = 0.0
        total_vol = 0.0

        for candle in candles[-50:]:
            high = self._candle_high(candle)
            low = self._candle_low(candle)
            close = self._candle_close(candle)
            volume = self._candle_volume(candle)

            typical = close
            if high > 0 and low > 0 and close > 0:
                typical = (high + low + close) / 3.0

            if volume > 0 and typical > 0:
                total_pv += typical * volume
                total_vol += volume

        if total_vol > 0:
            return total_pv / total_vol

        return fallback_price

    def _extract_last_close(self, candles: List[Dict[str, Any]]) -> float:
        if not candles:
            return 0.0
        return self._candle_close(candles[-1])

    def _classify_asset(self, asset: str) -> str:
        symbol = str(asset).upper()

        if "_" in symbol:
            return "FX"
        if "-" in symbol:
            return "CRYPTO"
        if any(x in symbol for x in ["ES", "NQ", "CL", "GC", "ZN", "YM", "RTY"]):
            return "FUTURES"
        return "OTHER"

    def _candle_open(self, candle: Dict[str, Any]) -> float:
        return self._to_float(self._safe_get(candle, "open", 0.0))

    def _candle_high(self, candle: Dict[str, Any]) -> float:
        return self._to_float(self._safe_get(candle, "high", 0.0))

    def _candle_low(self, candle: Dict[str, Any]) -> float:
        return self._to_float(self._safe_get(candle, "low", 0.0))

    def _candle_close(self, candle: Dict[str, Any]) -> float:
        return self._to_float(self._safe_get(candle, "close", 0.0))

    def _candle_volume(self, candle: Dict[str, Any]) -> float:
        return self._to_float(self._safe_get(candle, "volume", 0.0))

    def _safe_get(self, obj: Any, key: str, default: Any = None) -> Any:
        try:
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)
        except Exception:
            return default

    def _to_float(self, v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except Exception:
            return default

    def _clamp01(self, v: float) -> float:
        try:
            v = float(v)
        except Exception:
            return 0.0

        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v

    def _reject(self, asset: str, reason: str) -> Dict[str, Any]:
        return {
            "asset": asset,
            "asset_class": self._classify_asset(asset),
            "execute_trade": False,
            "execute_flag": False,
            "cost_blocked": True,
            "regime": "UNSTABLE",
            "regime_reason": reason,
            "confluence_score": 0.0,
            "ai_score": 0.0,
            "pressure_score": 0.0,
            "acceleration_score": 0.0,
            "momentum_score": 0.0,
            "pressure_fusion": 0.0,
            "vwap_score": 0.0,
            "vwap_dev_abs": 0.0,
            "elasticity_score": 0.0,
            "decision_score": 0.0,
            "expected_edge_bps": 0.0,
            "execution_cost_bps": 0.0,
            "cost_decision": reason,
            "net_edge_bps": 0.0,
            "expected_edge_value": 0.0,
            "cost_adjusted_edge_value": 0.0,
            "entry_costs": {
                "spread_cost_usd": 0.0,
                "slippage_cost_usd": 0.0,
                "fees_usd": 0.0,
                "total_cost_usd": 0.0,
            },
        }