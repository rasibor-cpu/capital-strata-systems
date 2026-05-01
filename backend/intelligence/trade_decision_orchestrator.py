from __future__ import annotations

from typing import Any, Dict

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.market_regime_detector import MarketRegimeDetector
from backend.intelligence.opportunity_momentum_window_engine import OpportunityMomentumWindowEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.probability_prediction_engine import ProbabilityPredictionEngine
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
        # 4. PROBABILITY ENGINE (PRIMARY INTELLIGENCE FILTER)
        # --------------------------------------------------
        probability_output = self.probability_engine.predict(
            market_data,
            regime=regime,
            raw_score=raw_score
        )

        win_probability = probability_output.get("win_probability", 0.0)
        approve_trade = probability_output.get("approve_trade", False)

        # --------------------------------------------------
        # 5. CSS QUALITY FILTER (STRICTER)
        # --------------------------------------------------
        vwap_edge = market_data.get("vwap_edge", 0.0)
        volume = market_data.get("volume", 0.0)

        css_quality_pass = (
            abs(vwap_edge) >= 10      # tightened from 5 → 10
            and volume > 0
            and raw_score > 1.2       # NEW: prevents weak signals
        )

        # --------------------------------------------------
        # 6. GOVERNANCE GATE (FINAL AUTHORITY)
        # --------------------------------------------------
        gate_decision = self.trade_gate.evaluate(
            market_data=market_data,
            regime=regime,
            score=raw_score,
            probability=win_probability
        )

        governance_approved = getattr(gate_decision, "approved", False)

        # --------------------------------------------------
        # 7. FINAL EXECUTION DECISION (FIXED LOGIC)
        # --------------------------------------------------
        execute_trade = (
            css_quality_pass
            and approve_trade              # FIX: use probability engine
            and governance_approved        # FIX: HARD VETO ENFORCED
        )

        # --------------------------------------------------
        # 8. NORMALIZED SCORE (FOR DISPLAY ONLY)
        # --------------------------------------------------
        decision_score = max(0.0, min(raw_score / 5.0, 1.0))

        # --------------------------------------------------
        # 9. RETURN DECISION PACKAGE
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
            },
        }
