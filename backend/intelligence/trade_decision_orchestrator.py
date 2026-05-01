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

        self.mean_reversion_threshold = 0.20
        self.trend_threshold = 0.24
        self.breakout_threshold = 0.28

        self.min_probability_threshold = 0.28
        self.high_probability_threshold = 0.60

        self.weights = {
            "ai_score": 0.25,
            "confluence_score": 0.20,
            "pressure_fusion": 0.20,
            "momentum_score": 0.10,
            "regime_confidence": 0.10,
            "probability_score": 0.15,
        }

        self.asset_class_limits: Dict[str, int] = {
            "CRYPTO": 2,
            "FX": 3,
            "FUTURES": 3,
            "OPTIONS": 2,
        }

        self.asset_class_thresholds: Dict[str, float] = {
            "CRYPTO": 0.62,
            "FX": 0.55,
            "FUTURES": 0.60,
            "OPTIONS": 0.65,
            "UNKNOWN": 0.60,
        }

        self.asset_class_weights: Dict[str, float] = {
            "CRYPTO": 0.90,
            "FX": 1.00,
            "FUTURES": 1.20,
            "OPTIONS": 0.80,
            "UNKNOWN": 1.00,
        }

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

        portfolio_state = portfolio_state or {}
        asset_class = self._classify_asset(asset)

        regime_info = self.regime_detector.detect_regime(candles)
        regime = str(regime_info.get("regime", "NEUTRAL")).upper()
        regime_conf = float(regime_info.get("confidence", 0.0))

        row = {"symbol": asset, "candles": candles, "asset_class": asset_class}

        pressure_row = self.pressure_engine.enrich_rows([row])[0]
        accel_row = self.acceleration_engine.enrich_rows([pressure_row])[0]
        conf_row = self.signal_confluence_engine.enrich_rows([accel_row])[0]

        pressure = float(conf_row.get("pressure_score", 0.0))
        accel = float(conf_row.get("pressure_acceleration", 0.0))
        confluence = float(conf_row.get("confluence_score", 0.0))
        momentum = self._estimate_momentum(candles)

        ai_score = self._score_ai(conf_row)
        pressure_fusion = (pressure * 0.6) + (abs(accel) * 0.4)

        trade_side = self._infer_side(accel, momentum, regime)

        probability_result = self.probability_engine.evaluate_trade_probability(
            ai_score=ai_score,
            confluence=confluence,
            pressure=pressure,
            momentum=momentum,
            elasticity=self._estimate_elasticity(candles),
            regime_confidence=regime_conf,
            liquidity_sweep=self._estimate_liquidity_sweep(conf_row),
            tier_history=self._tier_history_score(regime, ai_score),
            symbol=asset,
            side=trade_side,
        )

        win_probability = float(probability_result.get("win_probability", 0.0))
        approve_trade = bool(probability_result.get("approve_trade", False))

        decision_score = (
            ai_score * self.weights["ai_score"]
            + confluence * self.weights["confluence_score"]
            + pressure_fusion * self.weights["pressure_fusion"]
            + momentum * self.weights["momentum_score"]
            + regime_conf * self.weights["regime_confidence"]
            + win_probability * self.weights["probability_score"]
        )

        decision_score = self._clamp01(decision_score)

        execute_trade = self._should_execute_trade(regime, decision_score)

        if not approve_trade:
            execute_trade = False

        # GOVERNANCE GATE
        gate_decision = self.trade_gate.approve_trade(
            candidate={"symbol": asset, "probability": win_probability},
            session=session or {"role": "ADMIN"},
            engine_mode=engine_mode,
            portfolio_state=portfolio_state,
        )

        if not gate_decision.approved:
            execute_trade = False

        # ===== CSS OBSERVER LAYER =====
        normalized = normalize_css_inputs(
            vwap_edge=confluence,
            momentum=momentum,
            pressure=pressure,
            liquidity=self._estimate_liquidity_sweep(conf_row),
            regime_alignment=regime_conf,
        )

        css_score = compute_css_decision_score(**normalized)

        css_gate = css_trade_gate(
            score=css_score,
            mode=engine_mode,
            vwap_edge=normalized["vwap_edge"],
            momentum=normalized["momentum"],
            pressure=normalized["pressure"],
        )

        return {
            "asset": asset,
            "execute_trade": execute_trade,
            "decision_score": decision_score,
            "css_score": css_score,
            "css_gate": css_gate,
        }

    def _score_ai(self, row):
        return float(self.ai_scorer.score(row)) if hasattr(self.ai_scorer, "score") else 0.0

    def _should_execute_trade(self, regime, score):
        return score >= 0.26

    def _estimate_momentum(self, candles):
        closes = [c["close"] for c in candles[-5:]]
        return self._clamp01(abs(closes[-1] - closes[0]) * 10)

    def _estimate_elasticity(self, candles):
        return 0.5

    def _estimate_liquidity_sweep(self, row):
        return 0.5

    def _tier_history_score(self, regime, ai_score):
        return 0.5

    def _infer_side(self, accel, momentum, regime):
        return "CALL" if accel >= 0 else "PUT"

    def _clamp01(self, v):
        return max(0.0, min(1.0, float(v)))

    def _classify_asset(self, asset):
        return "CRYPTO"

    def _reject(self, asset, reason):
        return {"asset": asset, "execute_trade": False}


# ===== CSS HELPERS =====

def compute_css_decision_score(vwap_edge, momentum, pressure, liquidity, regime_alignment):
    return (vwap_edge*0.3 + momentum*0.25 + pressure*0.2 + liquidity*0.1 + regime_alignment*0.15)


def css_trade_gate(score, mode, vwap_edge, momentum, pressure):
    if score < 60:
        return False
    return True


def normalize_css_inputs(vwap_edge, momentum, pressure, liquidity, regime_alignment):
    return {
        "vwap_edge": vwap_edge*100,
        "momentum": momentum*100,
        "pressure": pressure*100,
        "liquidity": liquidity*100,
        "regime_alignment": regime_alignment*100,
    }
