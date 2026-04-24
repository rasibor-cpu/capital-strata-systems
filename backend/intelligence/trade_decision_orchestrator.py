from __future__ import annotations

from typing import Any, Dict, List

from backend.core.session_state import get_session_lock_state, is_session_locked
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.market_regime_detector import MarketRegimeDetector
from backend.intelligence.opportunity_momentum_window_engine import OpportunityMomentumWindowEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.probability_prediction_engine import ProbabilityPredictionEngine
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine
from backend.intelligence.vwap_elasticity_engine import VWAPElasticityEngine


class TradeDecisionOrchestrator:
    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()
        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()
        self.probability_engine = ProbabilityPredictionEngine()
        self.vwap_elasticity_engine = VWAPElasticityEngine()
        self.trade_gate = CSSUnifiedTradeGate()

        self.min_probability_threshold = 0.28

    def evaluate_trade(
        self,
        asset: str,
        candles: List[Dict[str, Any]],
        session: Dict[str, Any] | None = None,
        engine_mode: str = "BALANCED",
        portfolio_state: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:

        if not candles or len(candles) < 20:
            return self._reject(asset, "INSUFFICIENT_DATA")

        if portfolio_state is None:
            portfolio_state = {}

        asset_class = self._classify_asset(asset)

        regime_info = self.regime_detector.detect_regime(candles)
        regime_conf = float(regime_info.get("confidence", 0.0))

        vwap = self._calculate_vwap(candles)

        row = {
            "symbol": asset,
            "candles": candles,
            "asset_class": asset_class,
            "vwap": vwap,
        }

        # PIPELINE
        pressure_row = self.pressure_engine.enrich_rows([row])[0]
        accel_row = self.acceleration_engine.enrich_rows([pressure_row])[0]
        conf_row = self.signal_confluence_engine.enrich_rows([accel_row])[0]
        elastic_row = self.vwap_elasticity_engine.enrich_row(conf_row)

        pressure = float(elastic_row.get("pressure_score", 0.0))
        accel = float(elastic_row.get("pressure_acceleration", 0.0))
        confluence = float(elastic_row.get("confluence_score", 0.0))
        momentum = self._estimate_momentum(candles)

        elasticity = float(elastic_row.get("elasticity_score", 0.0))
        opportunity_score = float(elastic_row.get("opportunity_score", 0.0))

        ai_score = self._score_ai(elastic_row)

        trade_side = "CALL" if accel >= 0 else "PUT"

        probability_result = self.probability_engine.evaluate_trade_probability(
            ai_score=ai_score,
            confluence=confluence,
            pressure=pressure,
            momentum=momentum,
            elasticity=elasticity,
            regime_confidence=regime_conf,
            liquidity_sweep=abs(accel),
            tier_history=0.6,
            symbol=asset,
            side=trade_side,
        )

        win_probability = float(probability_result.get("win_probability", 0.0))
        approve_trade = bool(probability_result.get("approve_trade", False))

        decision_score = (
            ai_score * 0.25
            + confluence * 0.20
            + pressure * 0.20
            + momentum * 0.10
            + regime_conf * 0.10
            + win_probability * 0.15
        )

        execute_trade = (
            approve_trade
            and win_probability >= self.min_probability_threshold
        )

        # 🔥 CRITICAL: PASS OPPORTUNITY INTO GATE
        gate_candidate = {
            "symbol": asset,
            "asset_class": asset_class.lower(),
            "probability": win_probability,
            "expected_value": decision_score,
            "cost": max(0.01, 0.05 * (1 - win_probability)),
            "vwap_elasticity": elasticity,
            "opportunity_score": opportunity_score,
        }

        gate_decision = self.trade_gate.approve_trade(
            candidate=gate_candidate,
            session=session or {"created": 0, "role": "ADMIN"},
            engine_mode=engine_mode,
            portfolio_state=portfolio_state,
        )

        if not gate_decision.approved:
            execute_trade = False

        session_locked = is_session_locked()
        if session_locked:
            execute_trade = False

        return {
            "asset": asset,
            "execute_trade": execute_trade,
            "decision_score": round(decision_score, 4),
            "win_probability": round(win_probability, 4),
            "vwap": round(vwap, 6),
            "elasticity_score": round(elasticity, 6),
            "opportunity_score": round(opportunity_score, 6),
            "pressure_score": round(pressure, 6),
            "gate_approved": gate_decision.approved,
            "gate_reason": gate_decision.reason,
            "session_locked": session_locked,
        }

    def _calculate_vwap(self, candles):
        pv, vol = 0.0, 0.0
        for c in candles:
            high = float(c.get("high", 0))
            low = float(c.get("low", 0))
            close = float(c.get("close", 0))
            volume = float(c.get("volume", 1))
            typical = (high + low + close) / 3.0
            pv += typical * volume
            vol += volume
        return pv / vol if vol else 0.0

    def _score_ai(self, row):
        return float(self.ai_scorer.score_opportunity(row))

    def _classify_asset(self, asset):
        return "CRYPTO" if "-USD" in asset else "FX"

    def _estimate_momentum(self, candles):
        return 0.5

    def _reject(self, asset, reason):
        return {"asset": asset, "execute_trade": False, "reason": reason}