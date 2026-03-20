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

# NEW (SAFE IMPORTS)
try:
    from backend.execution.cost_aware_gate import CostAwareGate
except Exception:
    CostAwareGate = None

try:
    from backend.execution.execution_cost_engine import ExecutionCostEngine
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

        self.mean_reversion_threshold = 0.46
        self.trend_threshold = 0.58
        self.breakout_threshold = 0.66

        self.weights = {
            "ai_score": 0.28,
            "confluence_score": 0.22,
            "pressure_score": 0.20,
            "acceleration_score": 0.12,
            "momentum_score": 0.10,
            "regime_confidence": 0.08,
        }

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

        # ===============================
        # NEW: EDGE + COST LAYER
        # ===============================
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

        # FINAL GOVERNANCE: cost gate overrides execution
        if cost_decision.get("decision") != "APPROVE":
            execute_trade = False

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
            # NEW OUTPUTS (NON-BREAKING ADDITION)
            "expected_edge_bps": expected_edge_bps,
            "execution_cost_bps": execution_cost_bps,
            "cost_decision": cost_decision.get("decision"),
            "net_edge_bps": cost_decision.get("net_edge_bps", 0.0),
        }

    # ===============================
    # EDGE MODEL
    # ===============================
    def _estimate_edge(self, decision_score: float) -> float:
        base = max(0.0, decision_score - 0.5)
        return round(base * 200, 4)

    # ===============================
    # COST MODEL
    # ===============================
    def _estimate_cost(self, asset: str) -> float:
        if ExecutionCostEngine:
            try:
                result = ExecutionCostEngine.estimate(asset)
                return float(result.get("total_cost_bps", 10.0))
            except Exception:
                pass
        return 10.0

    # ===============================
    # COST GATE
    # ===============================
    def _apply_cost_gate(
        self,
        expected_edge_bps: float,
        execution_cost_bps: float,
        asset: str,
        decision_score: float,
    ) -> Dict[str, Any]:

        if CostAwareGate:
            return CostAwareGate.evaluate(
                expected_edge_bps,
                execution_cost_bps,
                metadata={"asset": asset, "score": decision_score},
            )

        return {
            "decision": "REJECT",
            "reason": "COST_GATE_UNAVAILABLE",
            "net_edge_bps": expected_edge_bps - execution_cost_bps,
        }

    # ===============================
    # ORIGINAL METHODS (UNCHANGED)
    # ===============================
    def _compute_decision_score(self, **kwargs) -> float:
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

    def _safe_ai_score(self, **kwargs) -> float:
        try:
            if hasattr(self.ai_scorer, "score_opportunity"):
                return self._extract_score(self.ai_scorer.score_opportunity(**kwargs))
        except Exception:
            pass
        return 0.0

    def _safe_confluence_score(self, **kwargs) -> float:
        try:
            return self._extract_score(self.signal_confluence_engine.compute_confluence(**kwargs))
        except Exception:
            return 0.0

    def _safe_pressure_score(self, **kwargs) -> float:
        try:
            return self._extract_score(self.pressure_engine.compute_pressure(**kwargs))
        except Exception:
            return 0.0

    def _safe_acceleration_score(self, **kwargs) -> float:
        try:
            return self._extract_score(self.acceleration_engine.compute_acceleration(**kwargs))
        except Exception:
            return 0.0

    def _safe_momentum_score(self, **kwargs) -> float:
        try:
            return self._extract_score(self.momentum_engine.compute_momentum_window(**kwargs))
        except Exception:
            return 0.0

    def _extract_score(self, result: Any) -> float:
        if isinstance(result, (int, float)):
            return self._clamp01(result)
        if isinstance(result, dict):
            for k in ("score", "confidence"):
                if k in result:
                    return self._clamp01(result[k])
        return 0.0

    @staticmethod
    def _clamp01(value: Any) -> float:
        try:
            return max(0.0, min(float(value), 1.0))
        except Exception:
            return 0.0

    def _reject(self, asset: str, reason: str) -> Dict[str, Any]:
        return {
            "execute_trade": False,
            "regime": "UNSTABLE",
            "regime_reason": reason,
        }


TradeDecisionEngine = TradeDecisionOrchestrator