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
    CSS Trade Decision Orchestrator (Activation-Calibrated)

    - No functionality removed
    - Decision scaling fixed
    - All engines preserved
    """

    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()

        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()

        self.cost_engine = ExecutionCostEngine() if ExecutionCostEngine else None

        # Activation-calibrated thresholds
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

        self.EDGE_MULTIPLIER = 0.025
        self.COST_NOTIONAL = 1000.0

    # ------------------------------------------------

    def evaluate_trade(self, asset: str, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not candles or len(candles) < 20:
            return self._reject(asset, "INSUFFICIENT_DATA")

        regime_info = self.regime_detector.detect_regime(candles)
        regime = str(regime_info.get("regime", "UNSTABLE")).upper()
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

        if cost_decision.get("decision") != "APPROVE":
            cost_blocked = True
            if decision_score < 0.28:
                execute_trade = False

        return {
            "asset": asset,
            "execute_trade": execute_trade,
            "cost_blocked": cost_blocked,
            "decision_score": round(decision_score, 4),
            "expected_edge_bps": round(expected_edge_bps, 4),
            "execution_cost_bps": round(execution_cost_bps, 4),
            "confluence_score": round(confluence_score, 4),
            "ai_score": round(ai_score, 4),
            "pressure_score": round(pressure_score, 4),
            "acceleration_score": round(acceleration_score, 4),
            "momentum_score": round(momentum_score, 4),
            "regime": regime,
        }

    # ------------------------------------------------
    # 🔥 FIXED DECISION SCORING (FINAL UNLOCK)
    # ------------------------------------------------

    def _compute_decision_score(self, **kwargs: float) -> float:
        components = [
            ("ai_score", kwargs["ai_score"]),
            ("confluence_score", kwargs["confluence_score"]),
            ("pressure_score", kwargs["pressure_score"]),
            ("acceleration_score", kwargs["acceleration_score"]),
            ("momentum_score", kwargs["momentum_score"]),
            ("regime_confidence", kwargs["regime_confidence"]),
        ]

        active = [(name, val) for name, val in components if val > 0.01]

        if not active:
            return 0.0

        total_weight = sum(self.weights[name] for name, _ in active)

        score = 0.0
        for name, val in active:
            normalized_weight = self.weights[name] / total_weight
            score += normalized_weight * val

        # 🔥 CRITICAL FIX: SCALE INTO EXECUTION RANGE
        scaled_score = score * 4.5

        return self._clamp01(scaled_score)

    # ------------------------------------------------

    def _estimate_edge(self, decision_score: float) -> float:
        return round(max(0.0, decision_score) * 120.0, 4)

    def _estimate_cost(self, asset: str) -> float:
        if self.cost_engine is None:
            return 10.0
        try:
            notional = self.COST_NOTIONAL
            spread_cost = float(self.cost_engine._compute_spread_cost(asset, notional))
            slippage_cost = float(self.cost_engine._compute_slippage_cost(notional))
            commission_cost = float(getattr(self.cost_engine, "commission_per_trade", 0))
            total_cost = spread_cost + slippage_cost + commission_cost
            return (total_cost / notional) * 10000.0
        except Exception:
            return 10.0

    def _apply_cost_gate(self, expected_edge_bps, execution_cost_bps, asset, decision_score):
        net_edge_bps = expected_edge_bps - execution_cost_bps
        if net_edge_bps > 0:
            return {"decision": "APPROVE", "net_edge_bps": net_edge_bps}
        return {"decision": "REJECT", "net_edge_bps": net_edge_bps}

    def _should_execute_trade(self, *, regime: str, decision_score: float) -> bool:
        if regime == "MEAN_REVERSION":
            return decision_score >= self.mean_reversion_threshold
        if regime == "TREND":
            return decision_score >= self.trend_threshold
        if regime == "BREAKOUT":
            return decision_score >= self.breakout_threshold
        return False

    # ------------------------------------------------

    def _safe_ai_score(self, **kwargs: Any) -> float:
        try:
            return float(self.ai_scorer.score_opportunity(**kwargs))
        except Exception:
            return 0.0

    def _safe_confluence_score(self, **kwargs: Any) -> float:
        try:
            return float(self.signal_confluence_engine.compute_confluence(**kwargs).get("score", 0.0))
        except Exception:
            return 0.0

    def _safe_pressure_score(self, **kwargs: Any) -> float:
        try:
            return float(self.pressure_engine.compute_pressure(kwargs).get("pressure", 0.0))
        except Exception:
            return 0.0

    def _safe_acceleration_score(self, **kwargs: Any) -> float:
        try:
            return float(self.acceleration_engine.compute_acceleration(**kwargs).get("score", 0.0))
        except Exception:
            return 0.0

    def _safe_momentum_score(self, **kwargs: Any) -> float:
        try:
            return float(self.momentum_engine.compute_momentum_window(**kwargs))
        except Exception:
            return 0.0

    # ------------------------------------------------

    def _reject(self, asset: str, reason: str) -> Dict[str, Any]:
        return {
            "asset": asset,
            "execute_trade": False,
            "decision_score": 0.0,
            "reason": reason,
        }

    @staticmethod
    def _clamp01(value: Any) -> float:
        try:
            return max(0.0, min(float(value), 1.0))
        except Exception:
            return 0.0


TradeDecisionEngine = TradeDecisionOrchestrator