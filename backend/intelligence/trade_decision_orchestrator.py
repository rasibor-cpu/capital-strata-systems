from __future__ import annotations

from typing import Any, Dict, List

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

        portfolio_state = portfolio_state or {}

        regime_info = self.regime_detector.detect_regime(candles)
        regime_conf = float(regime_info.get("confidence", 0.0))

        row = {"symbol": asset, "candles": candles}

        pressure_row = self.pressure_engine.enrich_rows([row])[0]
        accel_row = self.acceleration_engine.enrich_rows([pressure_row])[0]
        conf_row = self.signal_confluence_engine.enrich_rows([accel_row])[0]

        pressure = float(conf_row.get("pressure_score", 0.0))
        confluence = float(conf_row.get("confluence_score", 0.0))
        momentum = self._estimate_momentum(candles)

        ai_score = self._score_ai(conf_row)

        probability_result = self.probability_engine.evaluate_trade_probability(
            ai_score=ai_score,
            confluence=confluence,
            pressure=pressure,
            momentum=momentum,
            regime_confidence=regime_conf,
            symbol=asset,
            side="CALL",
        )

        win_probability = float(probability_result.get("win_probability", 0.0))
        approve_trade = bool(probability_result.get("approve_trade", False))

        decision_score = self._clamp01(ai_score + confluence + pressure + momentum)

        execute_trade = decision_score > 0.25 and approve_trade

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
            liquidity=0.5,
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

        css_diag = css_diagnostics(
            score=css_score,
            mode=engine_mode,
            vwap_edge=normalized["vwap_edge"],
            momentum=normalized["momentum"],
            pressure=normalized["pressure"],
        )

        # ===== PARTIAL CSS ACTIVATION (SAFE) =====
        css_high_confidence = (
            css_score >= 70
            and css_gate
            and win_probability >= 0.35
        )

        if css_high_confidence:
            execute_trade = True

        return {
            "asset": asset,
            "execute_trade": execute_trade,
            "decision_score": decision_score,
            "css_score": css_score,
            "css_gate": css_gate,
            "css_diagnostics": css_diag,
        }

    def rank_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        eligible = [c for c in candidates if c.get("execute_trade")]

        eligible.sort(
            key=lambda x: (
                float(x.get("css_score", 0.0)),
                float(x.get("decision_score", 0.0)),
            ),
            reverse=True,
        )

        return eligible

    def _score_ai(self, row):
        return float(self.ai_scorer.score(row)) if hasattr(self.ai_scorer, "score") else 0.0

    def _estimate_momentum(self, candles):
        closes = [float(c.get("close", 0)) for c in candles[-5:]]
        if len(closes) < 2:
            return 0.0
        return self._clamp01(abs(closes[-1] - closes[0]) * 10)

    def _clamp01(self, v):
        return max(0.0, min(1.0, float(v)))

    def _reject(self, asset, reason):
        return {
            "asset": asset,
            "execute_trade": False,
            "reason": reason,
        }


# ================================
# CSS HELPERS
# ================================

def compute_css_decision_score(vwap_edge, momentum, pressure, liquidity, regime_alignment):
    return (
        vwap_edge * 0.30
        + momentum * 0.25
        + pressure * 0.20
        + liquidity * 0.10
        + regime_alignment * 0.15
    )


def get_css_mode_threshold(mode: str) -> float:
    return {
        "SAFE": 80,
        "CONSERVATIVE": 70,
        "BALANCED": 60,
        "AGGRESSIVE": 50,
        "EXPANSION": 45,
    }.get(mode, 60)


def css_trade_gate(score, mode, vwap_edge, momentum, pressure):
    threshold = get_css_mode_threshold(mode)

    return (
        score >= threshold
        and abs(vwap_edge) >= 5
        and abs(momentum) >= 5
        and abs(pressure) >= 5
    )


def css_diagnostics(score, mode, vwap_edge, momentum, pressure):
    threshold = get_css_mode_threshold(mode)

    return {
        "score_ok": score >= threshold,
        "vwap_ok": abs(vwap_edge) >= 5,
        "momentum_ok": abs(momentum) >= 5,
        "pressure_ok": abs(pressure) >= 5,
        "threshold": threshold,
    }


def normalize_css_inputs(vwap_edge, momentum, pressure, liquidity, regime_alignment):
    return {
        "vwap_edge": vwap_edge * 100,
        "momentum": momentum * 100,
        "pressure": pressure * 100,
        "liquidity": liquidity * 100,
        "regime_alignment": regime_alignment * 100,
    }
