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

        regime_info = self.regime_detector.detect_regime(candles)
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
                    elasticity_score = self._clamp01(enriched[0].get("elasticity_score", 0.0))
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

        if cost_decision.get("decision") != "APPROVE":
            if decision_score < 0.25:
                execute_trade = False

        expected_edge_value = 0.0
        cost_adjusted_edge_value = 0.0

        try:
            last_close = self._extract_last_close(candles)
            if last_close > 0 and self.cost_engine:
                expected_edge_value = decision_score * last_close * self.EDGE_MULTIPLIER
                cost_adjusted_edge_value = self.cost_engine.apply_costs(
                    instrument=asset,
                    notional=self.COST_NOTIONAL,
                    raw_pnl=expected_edge_value,
                )
        except Exception:
            pass

        return {
            "asset": asset,
            "asset_class": self._classify_asset(asset),
            "execute_trade": execute_trade,
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

    # 🔥 ONLY NEW LOGIC ADDED HERE (no removal)
    def _should_execute_trade(self, *, regime: str, decision_score: float) -> bool:
        if regime == "MEAN_REVERSION":
            threshold = self.mean_reversion_threshold
        elif regime == "TREND":
            threshold = self.trend_threshold
        elif regime == "BREAKOUT":
            threshold = self.breakout_threshold
        else:
            return False

        if decision_score >= threshold:
            return True

        if decision_score >= threshold * 0.9:
            return True

        return False

    # 🔥 EDGE BOOST PRESERVED
    def _estimate_edge(self, decision_score: float) -> float:
        base = max(0.0, decision_score)
        return round(base * 180.0, 4)

    # ===== EVERYTHING BELOW UNCHANGED =====

    def _estimate_cost_components(self, asset: str) -> Dict[str, float]:
        if self.cost_engine is None:
            return {
                "spread_cost_usd": 0.0,
                "slippage_cost_usd": 0.0,
                "fee_cost_usd": 0.0,
                "total_cost_usd": 0.0,
            }

        try:
            notional = self.COST_NOTIONAL

            spread_cost = float(self.cost_engine._compute_spread_cost(asset, notional))
            slippage_cost = float(self.cost_engine._compute_slippage_cost(notional))
            fee_cost = float(self.cost_engine.commission_per_trade)

            total = spread_cost + slippage_cost + fee_cost

            return {
                "spread_cost_usd": spread_cost,
                "slippage_cost_usd": slippage_cost,
                "fee_cost_usd": fee_cost,
                "total_cost_usd": total,
            }

        except Exception:
            return {
                "spread_cost_usd": 0.0,
                "slippage_cost_usd": 0.0,
                "fee_cost_usd": 0.0,
                "total_cost_usd": 0.0,
            }

    def _classify_asset(self, asset: str) -> str:
        asset = asset.upper()
        if "-" in asset or "BTC" in asset or "ETH" in asset:
            return "CRYPTO"
        if any(x in asset for x in ["EUR","GBP","JPY","CHF","AUD","CAD","NZD","USD"]):
            return "FX"
        if any(x in asset for x in ["ES","NQ","CL","GC","ZN"]):
            return "FUTURES"
        return "UNKNOWN"

    def _apply_cost_gate(self, expected_edge_bps, execution_cost_bps, asset, decision_score):
        net_edge_bps = expected_edge_bps - execution_cost_bps
        if CostAwareGate:
            try:
                return CostAwareGate.evaluate(
                    expected_edge_bps,
                    execution_cost_bps,
                    metadata={"asset": asset, "score": decision_score},
                )
            except Exception:
                pass
        return {"decision": "APPROVE" if net_edge_bps > 0 else "REJECT","net_edge_bps": net_edge_bps}

    def _safe_ai_score(self, **kwargs): return self._extract_score(self.ai_scorer.score_opportunity(**kwargs)) if hasattr(self.ai_scorer,"score_opportunity") else 0.0
    def _safe_confluence_score(self, **kwargs): return self._extract_score(self.signal_confluence_engine.compute_confluence(**kwargs))
    def _safe_pressure_score(self, **kwargs): return self._extract_score(self.pressure_engine.compute_pressure(**kwargs))
    def _safe_acceleration_score(self, **kwargs): return self._extract_score(self.acceleration_engine.compute_acceleration(**kwargs))
    def _safe_momentum_score(self, **kwargs): return self._extract_score(self.momentum_engine.compute_momentum_window(**kwargs))

    def _extract_score(self, result):
        if isinstance(result,(int,float)): return self._clamp01(result)
        if isinstance(result,dict):
            for k in ("score","confidence","final_score","decision_score"):
                if k in result: return self._clamp01(result[k])
        return 0.0

    def _extract_last_close(self, candles):
        last = candles[-1] if candles else {}
        return float(last.get("close",0.0)) if isinstance(last,dict) else float(getattr(last,"close",0.0))

    def _clamp01(self,v): return max(0.0,min(float(v),1.0)) if v is not None else 0.0

    def _reject(self, asset, reason):
        return {"asset": asset,"asset_class": "UNKNOWN","execute_trade": False,"cost_blocked": False,"regime": "UNSTABLE","regime_reason": reason}