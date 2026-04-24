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
        self.high_probability_threshold = 0.60

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

        if portfolio_state is None:
            portfolio_state = {}

        asset_class = self._classify_asset(asset)

        regime_info = self.regime_detector.detect_regime(candles)
        regime = str(regime_info.get("regime", "NEUTRAL")).upper()
        regime_conf = float(regime_info.get("confidence", 0.0))

        vwap = self._calculate_vwap(candles)

        row = {
            "symbol": asset,
            "candles": candles,
            "asset_class": asset_class,
            "vwap": vwap,
        }

        pressure_row = self.pressure_engine.enrich_rows([row])[0]
        accel_row = self.acceleration_engine.enrich_rows([pressure_row])[0]
        conf_row = self.signal_confluence_engine.enrich_rows([accel_row])[0]
        elastic_row = self.vwap_elasticity_engine.enrich_row(conf_row)

        pressure = float(elastic_row.get("pressure_score", 0.0))
        accel = float(elastic_row.get("pressure_acceleration", 0.0))
        confluence = float(elastic_row.get("confluence_score", 0.0))
        momentum = self._estimate_momentum(candles)
        elasticity = float(elastic_row.get("elasticity_score", 0.0))

        ai_score = self._score_ai(elastic_row)
        pressure_fusion = (pressure * 0.6) + (abs(accel) * 0.4)
        trade_side = self._infer_side(accel, momentum, regime)

        probability_result = self.probability_engine.evaluate_trade_probability(
            ai_score=ai_score,
            confluence=confluence,
            pressure=pressure,
            momentum=momentum,
            elasticity=elasticity,
            regime_confidence=regime_conf,
            liquidity_sweep=self._estimate_liquidity_sweep(elastic_row),
            tier_history=self._tier_history_score(regime, ai_score),
            symbol=asset,
            side=trade_side,
        )

        win_probability = float(probability_result.get("win_probability", 0.0))
        approve_trade = bool(probability_result.get("approve_trade", False))

        decision_score = self._clamp01(
            ai_score * 0.25
            + confluence * 0.20
            + pressure_fusion * 0.20
            + momentum * 0.10
            + regime_conf * 0.10
            + win_probability * 0.15
        )

        asset_threshold = self.asset_class_thresholds.get(asset_class, 0.60)
        asset_weight = self.asset_class_weights.get(asset_class, 1.00)
        adjusted_score = self._clamp01(decision_score * asset_weight)
        threshold_ok = decision_score >= asset_threshold

        execute_trade = approve_trade and win_probability >= self.min_probability_threshold and threshold_ok

        gate_candidate = {
            "symbol": asset,
            "asset_class": asset_class.lower(),
            "probability": win_probability,
            "expected_value": decision_score,
            "cost": max(0.01, 0.05 * (1 - win_probability)),
            "vwap_elasticity": elasticity,
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
        lock_state = get_session_lock_state()

        if session_locked:
            execute_trade = False

        return {
            "asset": asset,
            "symbol": asset,
            "asset_class": asset_class,
            "asset_limit": self.asset_class_limits.get(asset_class, 0),
            "asset_threshold": round(asset_threshold, 4),
            "asset_weight": round(asset_weight, 4),
            "threshold_ok": threshold_ok,
            "adjusted_score": round(adjusted_score, 4),
            "execute_trade": execute_trade,
            "decision_score": round(decision_score, 4),
            "win_probability": round(win_probability, 4),
            "trade_side": trade_side,
            "vwap": round(vwap, 6),
            "vwap_elasticity": round(float(elastic_row.get("vwap_elasticity", 0.0)), 6),
            "elasticity_score": round(elasticity, 6),
            "gate_approved": gate_decision.approved,
            "gate_reason": gate_decision.reason,
            "session_locked": session_locked,
            "session_lock_reason": str(lock_state.get("reason", "")),
            "session_lock_time": lock_state.get("lock_time"),
            "defensive_mode_active": session_locked,
        }

    def _calculate_vwap(self, candles: List[Dict[str, Any]]) -> float:
        pv = 0.0
        vol = 0.0
        for c in candles:
            high = float(c.get("high", c.get("h", c.get("close", 0.0))))
            low = float(c.get("low", c.get("l", c.get("close", 0.0))))
            close = float(c.get("close", c.get("c", 0.0)))
            volume = float(c.get("volume", c.get("v", 1.0)) or 1.0)
            typical = (high + low + close) / 3.0
            pv += typical * volume
            vol += volume
        return pv / vol if vol > 0 else 0.0

    def _score_ai(self, row: Dict[str, Any]) -> float:
        if hasattr(self.ai_scorer, "score_opportunity"):
            return float(self.ai_scorer.score_opportunity(row))
        if hasattr(self.ai_scorer, "score"):
            return float(self.ai_scorer.score(row))
        return 0.0

    def _classify_asset(self, asset: str) -> str:
        symbol = str(asset or "").upper().strip()
        if symbol.endswith(("-USD", "-USDT", "/USD", "/USDT")):
            return "CRYPTO"
        if symbol in {"EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CHF", "USD_CAD", "NZD_USD", "EUR_GBP", "EUR_JPY", "GBP_JPY"}:
            return "FX"
        if symbol.startswith(("ES", "NQ", "CL", "GC", "ZN", "MES", "MNQ", "MCL", "MGC")):
            return "FUTURES"
        if symbol in {"SPY", "QQQ", "AAPL"} or symbol.endswith(("_CALL", "_PUT")):
            return "OPTIONS"
        return "UNKNOWN"

    def _estimate_momentum(self, candles):
        closes = [float(c.get("close", c.get("c", 0.0))) for c in candles[-5:] if isinstance(c, dict)]
        if len(closes) < 2 or closes[0] == 0:
            return 0.0
        return self._clamp01(abs((closes[-1] - closes[0]) / (closes[0] + 1e-9)) * 50)

    def _estimate_liquidity_sweep(self, row):
        return self._clamp01(abs(float(row.get("pressure_acceleration", 0.0))))

    def _tier_history_score(self, regime, ai_score):
        return self._clamp01(0.55 + (0.15 if ai_score >= 0.60 else 0.0))

    def _infer_side(self, accel, momentum, regime):
        if accel < 0 and momentum > 0.10 and regime == "MEAN_REVERSION":
            return "CALL"
        return "CALL" if accel >= 0 else "PUT"

    def _clamp01(self, v):
        return max(0.0, min(1.0, float(v)))

    def _reject(self, asset, reason):
        return {"asset": asset, "execute_trade": False, "reason": reason}