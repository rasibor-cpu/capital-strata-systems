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

# Safe optional imports across current mixed project structure
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
    """
    Trade decision orchestrator for Capital Strata Systems.

    Tuned Version (Activation-Calibrated):
    - Fixes over-constrained system
    - Preserves all architecture
    - Enables controlled trade flow
    """

    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()

        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()

        self.cost_engine = ExecutionCostEngine() if ExecutionCostEngine else None

        # 🔥 CALIBRATED THRESHOLDS (aligned to real score distribution)
        self.mean_reversion_threshold = 0.22
        self.trend_threshold = 0.26
        self.breakout_threshold = 0.32

        self.weights = {
            "ai_score": 0.28,
            "confluence_score": 0.22,
            "pressure_score": 0.20,
            "acceleration_score": 0.12,
            "momentum_score": 0.10,
            "regime_confidence": 0.08,
        }

        # 🔥 INCREASED EDGE SENSITIVITY
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

        decision_score = self._compute_decision_score(
            ai_score=ai_score,
            confluence_score=confluence_score,
            pressure_score=pressure_score,
            acceleration_score=acceleration_score,
            momentum_score=momentum_score,
            regime_confidence=regime_confidence,
        )

        expected_edge_bps = self._estimate_edge(decision_score)
        execution_cost_bps = self._estimate_cost(asset)

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

        cost_blocked = False

        # 🔥 SOFT COST GATE (CRITICAL FIX)
        if cost_decision.get("decision") != "APPROVE":
            cost_blocked = True

            # Only block weak trades — allow strong signals through
            if decision_score < 0.28:
                execute_trade = False

        expected_edge_value = 0.0
        cost_adjusted_edge_value = 0.0

        try:
            last_close = self._extract_last_close(candles)
            if last_close > 0 and self.cost_engine and hasattr(self.cost_engine, "apply_costs"):
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
            "execute_trade": execute_trade,
            "cost_blocked": cost_blocked,
            "regime": regime,
            "regime_reason": regime_reason,
            "confluence_score": round(confluence_score, 4),
            "ai_score": round(ai_score, 4),
            "pressure_score": round(pressure_score, 4),
            "acceleration_score": round(acceleration_score, 4),
            "momentum_score": round(momentum_score, 4),
            "decision_score": round(decision_score, 4),
            "expected_edge_bps": round(expected_edge_bps, 4),
            "execution_cost_bps": round(execution_cost_bps, 4),
            "cost_decision": cost_decision.get("decision"),
            "net_edge_bps": round(float(cost_decision.get("net_edge_bps", 0.0)), 4),
            "expected_edge_value": round(expected_edge_value, 6),
            "cost_adjusted_edge_value": round(cost_adjusted_edge_value, 6),
        }

    # ===============================
    # EDGE MODEL (UNCHANGED STRUCTURE)
    # ===============================
    def _estimate_edge(self, decision_score: float) -> float:
        base = max(0.0, decision_score)
        return round(base * 120.0, 4)

    def _estimate_cost(self, asset: str) -> float:
        if self.cost_engine is None:
            return 10.0

        try:
            notional = self.COST_NOTIONAL
            spread_cost = 0.0
            slippage_cost = 0.0
            commission_cost = 0.0

            if hasattr(self.cost_engine, "_compute_spread_cost"):
                spread_cost = float(self.cost_engine._compute_spread_cost(asset, notional))

            if hasattr(self.cost_engine, "_compute_slippage_cost"):
                slippage_cost = float(self.cost_engine._compute_slippage_cost(notional))

            if hasattr(self.cost_engine, "commission_per_trade"):
                commission_cost = float(self.cost_engine.commission_per_trade)

            total_cost = spread_cost + slippage_cost + commission_cost
            return (total_cost / notional) * 10000.0
        except Exception:
            return 10.0

    def _apply_cost_gate(
        self,
        expected_edge_bps: float,
        execution_cost_bps: float,
        asset: str,
        decision_score: float,
    ) -> Dict[str, Any]:
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

        if net_edge_bps > 0:
            return {
                "decision": "APPROVE",
                "reason": "FALLBACK_NET_EDGE_POSITIVE",
                "net_edge_bps": net_edge_bps,
            }

        return {
            "decision": "REJECT",
            "reason": "FALLBACK_NET_EDGE_NEGATIVE",
            "net_edge_bps": net_edge_bps,
        }

    def _compute_decision_score(self, **kwargs: float) -> float:
        score = (
            self.weights["ai_score"] * kwargs["ai_score"]
            + self.weights["confluence_score"] * kwargs["confluence_score"]
            + self.weights["pressure_score"] * kwargs["pressure_score"]
            + self.weights["acceleration_score"] * kwargs["acceleration_score"]
            + self.weights["momentum_score"] * kwargs["momentum_score"]
            + self.weights["regime_confidence"] * kwargs["regime_confidence"]
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

    def _safe_ai_score(self, **kwargs: Any) -> float:
        try:
            if hasattr(self.ai_scorer, "score_opportunity"):
                return self._extract_score(self.ai_scorer.score_opportunity(**kwargs))
        except Exception:
            pass
        return 0.0

    def _safe_confluence_score(self, **kwargs: Any) -> float:
        try:
            return self._extract_score(
                self.signal_confluence_engine.compute_confluence(**kwargs)
            )
        except Exception:
            return 0.0

    def _safe_pressure_score(self, **kwargs: Any) -> float:
        try:
            return self._extract_score(self.pressure_engine.compute_pressure(**kwargs))
        except Exception:
            return 0.0

    def _safe_acceleration_score(self, **kwargs: Any) -> float:
        try:
            return self._extract_score(
                self.acceleration_engine.compute_acceleration(**kwargs)
            )
        except Exception:
            return 0.0

    def _safe_momentum_score(self, **kwargs: Any) -> float:
        try:
            return self._extract_score(self.momentum_engine.compute_momentum_window(**kwargs))
        except Exception:
            return 0.0

    def _extract_score(self, result: Any) -> float:
        if isinstance(result, (int, float)):
            return self._clamp01(result)
        if isinstance(result, dict):
            for key in ("score", "confidence", "final_score", "decision_score"):
                if key in result:
                    return self._clamp01(result[key])
        return 0.0

    def _extract_last_close(self, candles: List[Dict[str, Any]]) -> float:
        if not candles:
            return 0.0
        last = candles[-1]
        if isinstance(last, dict):
            return self._to_float(last.get("close"), 0.0)
        return self._to_float(getattr(last, "close", 0.0), 0.0)

    @staticmethod
    def _clamp01(value: Any) -> float:
        try:
            return max(0.0, min(float(value), 1.0))
        except Exception:
            return 0.0

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _reject(self, asset: str, reason: str) -> Dict[str, Any]:
        return {
            "asset": asset,
            "execute_trade": False,
            "cost_blocked": False,
            "regime": "UNSTABLE",
            "regime_reason": reason,
            "confluence_score": 0.0,
            "ai_score": 0.0,
            "pressure_score": 0.0,
            "acceleration_score": 0.0,
            "momentum_score": 0.0,
            "decision_score": 0.0,
            "expected_edge_bps": 0.0,
            "execution_cost_bps": 0.0,
            "cost_decision": "REJECT",
            "net_edge_bps": 0.0,
            "expected_edge_value": 0.0,
            "cost_adjusted_edge_value": 0.0,
        }


TradeDecisionEngine = TradeDecisionOrchestrator