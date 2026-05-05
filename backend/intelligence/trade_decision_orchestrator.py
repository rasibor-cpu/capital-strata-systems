from __future__ import annotations

from typing import Any, Dict

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.market_regime_detector import MarketRegimeDetector
from backend.intelligence.opportunity_momentum_window_engine import OpportunityMomentumWindowEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.probability_prediction_engine import ProbabilityPredictionEngine
from backend.intelligence.profitability_guard import ProfitabilityGuard
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine

from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate


class TradeDecisionOrchestrator:

    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()
        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()
        self.probability_engine = ProbabilityPredictionEngine()
        self.profitability_guard = ProfitabilityGuard()

        self.trade_gate = CSSUnifiedTradeGate()

    def evaluate_trade(self, market_data: Dict[str, Any]) -> Dict[str, Any]:

        # --------------------------------------------------
        # 1. REGIME DETECTION
        # --------------------------------------------------
        regime = self.regime_detector.detect(market_data)

        # --------------------------------------------------
        # 2. SIGNAL COMPONENTS
        # --------------------------------------------------
        ai_score = self.ai_scorer.score(market_data, regime)
        confluence = self.signal_confluence_engine.evaluate(market_data)
        pressure = self.pressure_engine.evaluate(market_data)
        acceleration = self.acceleration_engine.evaluate(market_data)
        momentum = self.momentum_engine.evaluate(market_data)

        # --------------------------------------------------
        # 3. RAW SCORE (NO COMPRESSION)
        # --------------------------------------------------
        raw_score = (
            ai_score
            + confluence
            + pressure
            + acceleration
            + momentum
        )

        # --------------------------------------------------
        # 4. PROBABILITY ENGINE
        # --------------------------------------------------
        probability_output = self.probability_engine.predict(
            market_data,
            regime=regime,
            raw_score=raw_score,
        )

        win_probability = probability_output.get("win_probability", 0.0)
        approve_trade = probability_output.get("approve_trade", False)

        # ✅ FIX A1 — enforce bounds
        if not isinstance(win_probability, (int, float)):
            win_probability = 0.0
        win_probability = max(0.0, min(float(win_probability), 1.0))

        # --------------------------------------------------
        # 5. CSS QUALITY FILTER
        # --------------------------------------------------
        vwap_edge = market_data.get("vwap_edge", 0.0)
        volume = market_data.get("volume", 0.0)

        css_quality_pass = (
            abs(vwap_edge) >= 10
            and volume > 0
            and raw_score > 1.2
            and win_probability >= 0.35   # ✅ FIX A3
        )

        # --------------------------------------------------
        # 6. GOVERNANCE GATE
        # --------------------------------------------------
        # ✅ FIX A2 — validate inputs
        if not isinstance(raw_score, (int, float)):
            raw_score = 0.0

        gate_decision = self.trade_gate.evaluate(
            market_data=market_data,
            regime=regime,
            score=float(raw_score),
            probability=float(win_probability),
        )

        # ✅ FIX A4 — explicit handling
        if not hasattr(gate_decision, "approved"):
            governance_approved = False
            governance_error = True
        else:
            governance_approved = bool(gate_decision.approved)
            governance_error = False

        # --------------------------------------------------
        # 6B. PROFITABILITY GUARD (PCNRASS SAFE)
        # --------------------------------------------------
        profit_signal = {
            "score": raw_score,
            "probability": win_probability,
            "vwap_edge": vwap_edge,
            "regime": regime,
            "liquidity_score": market_data.get("liquidity_score", 100),
            "spread_pct": market_data.get("spread_pct", 0.0),
            "volatility": market_data.get("volatility", 0.01),
            "acceleration": acceleration,
            "pressure_score": pressure,
        }

        profitability_approved, profit_reason = self.profitability_guard.evaluate(
            profit_signal
        )

        # --------------------------------------------------
        # 7. FINAL EXECUTION DECISION
        # --------------------------------------------------
        execute_trade = (
            css_quality_pass
            and approve_trade
            and governance_approved
            and profitability_approved
        )

        # --------------------------------------------------
        # 8. NORMALIZED SCORE (DISPLAY ONLY)
        # --------------------------------------------------
        decision_score = max(0.0, min(raw_score / 5.0, 1.0))

        # --------------------------------------------------
        # 9. RETURN PACKAGE
        # --------------------------------------------------
        return {
            "execute_trade": execute_trade,
            "decision_score": decision_score,
            "raw_score": raw_score,
            "win_probability": win_probability,
            "approve_trade": approve_trade,
            "regime": regime,
            "components": {
                "ai_score": ai_score,
                "confluence": confluence,
                "pressure": pressure,
                "acceleration": acceleration,
                "momentum": momentum,
            },
            "filters": {
                "css_quality_pass": css_quality_pass,
                "governance_approved": governance_approved,
                "governance_error": governance_error,
                "profitability_approved": profitability_approved,
                "profitability_reason": profit_reason,
            },
        }
