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

# ✅ NEW IMPORT (Unified Governance Gate)
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate


class TradeDecisionOrchestrator:
    """
    CSS Trade Decision Orchestrator (Phase 14 - Governed)

    Enhancements
    ------------
    - Integrated Unified Trade Gate (final authority)
    - Preserves ALL existing scoring logic (NO REGRESSION)
    - Adds governance-based approval layer AFTER scoring
    """

    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()
        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()
        self.probability_engine = ProbabilityPredictionEngine()

        # ✅ NEW: Unified Gate
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

        if portfolio_state is None:
            portfolio_state = {}

        asset_class = self._classify_asset(asset)

        regime_info = self.regime_detector.detect_regime(candles)
        regime = str(regime_info.get("regime", "NEUTRAL")).upper()
        regime_conf = float(regime_info.get("confidence", 0.0))

        row: Dict[str, Any] = {"symbol": asset, "candles": candles, "asset_class": asset_class}

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
        loss_probability = float(probability_result.get("loss_probability", 0.0))
        confidence_label = str(probability_result.get("confidence_label", "LOW"))
        expected_edge_label = str(probability_result.get("expected_edge", "WEAK"))
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

        asset_threshold = self.asset_class_thresholds.get(
            asset_class, self.asset_class_thresholds["UNKNOWN"]
        )
        asset_weight = self.asset_class_weights.get(
            asset_class, self.asset_class_weights["UNKNOWN"]
        )

        adjusted_score = self._clamp01(decision_score * asset_weight)

        # --------------------------------
        # BASE EXECUTION LOGIC (UNCHANGED)
        # --------------------------------

        execute_trade = self._should_execute_trade(regime, decision_score)

        pressure_ok = pressure >= 0.18
        confluence_ok = confluence >= 0.10
        momentum_ok = (accel > -0.02) or (pressure > 0.22)
        probability_ok = win_probability >= self.min_probability_threshold
        threshold_ok = decision_score >= asset_threshold

        if pressure_ok and confluence_ok and momentum_ok and probability_ok and threshold_ok:
            execute_trade = True

        if decision_score >= 0.20 and probability_ok and threshold_ok:
            execute_trade = True

        if (
            decision_score >= 0.18
            and pressure >= 0.15
            and win_probability >= 0.30
            and threshold_ok
        ):
            execute_trade = True

        if not approve_trade:
            execute_trade = False

        if win_probability < self.min_probability_threshold:
            execute_trade = False

        if not threshold_ok:
            execute_trade = False

        # --------------------------------
        # ✅ NEW: GOVERNANCE GATE
        # --------------------------------

        gate_candidate = {
            "symbol": asset,
            "asset_class": asset_class.lower(),
            "probability": win_probability,
            "expected_value": decision_score,  # proxy for EV for now
            "cost": max(0.01, 0.05 * (1 - win_probability)),  # simple cost model
        }

        gate_decision = self.trade_gate.approve_trade(
            candidate=gate_candidate,
            session=session or {"created": 0, "role": "ADMIN"},
            engine_mode=engine_mode,
            portfolio_state=portfolio_state,
        )

        # Gate overrides execution if blocked
        if not gate_decision.approved:
            execute_trade = False

        # --------------------------------
        # RETURN
        # --------------------------------

        return {
            "asset": asset,
            "symbol": asset,
            "asset_class": asset_class,
            "execute_trade": execute_trade,
            "adjusted_score": round(adjusted_score, 4),
            "decision_score": round(decision_score, 4),
            "win_probability": round(win_probability, 4),
            "loss_probability": round(loss_probability, 4),
            "probability_confidence": confidence_label,
            "expected_edge": expected_edge_label,
            "probability_approved": approve_trade,
            "high_probability_setup": win_probability >= self.high_probability_threshold,
            "trade_side": trade_side,

            # ✅ NEW: Gate visibility
            "gate_approved": gate_decision.approved,
           
            "gate_reason": gate_decision.reason,
        }
        def get_allocation_policy(self) -> Dict[str, Dict[str, float]]:
        return {
            "limits": dict(self.asset_class_limits),
            "thresholds": dict(self.asset_class_thresholds),
            "weights": dict(self.asset_class_weights),
        }

    def rank_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        eligible = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if not bool(candidate.get("execute_trade", False)):
                continue
            eligible.append(candidate)

        eligible.sort(
            key=lambda x: (
                float(x.get("adjusted_score", 0.0)),
                float(x.get("decision_score", 0.0)),
                float(x.get("win_probability", 0.0)),
            ),
            reverse=True,
        )
        return eligible

    def select_candidates_for_cycle(
        self,
        candidates: List[Dict[str, Any]],
        max_trades: int = 10,
    ) -> List[Dict[str, Any]]:

        ranked = self.rank_candidates(candidates)
        selected: List[Dict[str, Any]] = []
        counts: Dict[str, int] = {k: 0 for k in self.asset_class_limits.keys()}

        for candidate in ranked:
            if len(selected) >= max_trades:
                break

            asset_class = str(candidate.get("asset_class", "UNKNOWN")).upper()
            asset_limit = self.asset_class_limits.get(asset_class, 0)

            if asset_limit <= 0:
                continue

            current_count = counts.get(asset_class, 0)
            if current_count >= asset_limit:
                continue

            selected.append(candidate)
            counts[asset_class] = current_count + 1

        return selected

    # ==============================
    # INTERNAL HELPERS (UNCHANGED)
    # ==============================

    def _score_ai(self, row: Dict[str, Any]) -> float:
        if hasattr(self.ai_scorer, "score_opportunity"):
            return float(self.ai_scorer.score_opportunity(row))
        if hasattr(self.ai_scorer, "score"):
            return float(self.ai_scorer.score(row))
        return 0.0

    def _should_execute_trade(self, regime: str, score: float) -> bool:
        if regime == "MEAN_REVERSION":
            return score >= self.mean_reversion_threshold
        if regime == "TREND":
            return score >= self.trend_threshold
        if regime == "BREAKOUT":
            return score >= self.breakout_threshold
        return score >= 0.26

    def _classify_asset(self, asset: str) -> str:
        symbol = str(asset or "").upper().strip()

        option_names = {"SPY", "QQQ", "AAPL"}
        futures_prefixes = ("ES", "NQ", "CL", "GC", "ZN", "MES", "MNQ", "MCL", "MGC")
        crypto_suffixes = ("-USD", "-USDT", "/USD", "/USDT")
        fx_names = {
            "EUR_USD",
            "GBP_USD",
            "USD_JPY",
            "AUD_USD",
            "USD_CHF",
            "USD_CAD",
            "NZD_USD",
            "EUR_GBP",
            "EUR_JPY",
            "GBP_JPY",
        }

        if symbol in option_names or symbol.endswith("_CALL") or symbol.endswith("_PUT"):
            return "OPTIONS"

        if symbol.startswith(futures_prefixes):
            return "FUTURES"

        if symbol in fx_names or ("_" in symbol and len(symbol) == 7):
            return "FX"

        if any(symbol.endswith(sfx) for sfx in crypto_suffixes):
            return "CRYPTO"

        if any(token in symbol for token in ("BTC", "ETH", "SOL", "XRP", "ADA", "DOGE")):
            return "CRYPTO"

        return "UNKNOWN"

    def _estimate_momentum(self, candles: List[Dict[str, Any]]) -> float:
        closes = [float(c.get("close", 0.0)) for c in candles[-5:] if isinstance(c, dict)]
        if len(closes) < 2 or closes[0] == 0:
            return 0.0
        return self._clamp01(abs((closes[-1] - closes[0]) / (closes[0] + 1e-9)) * 50)

    def _estimate_elasticity(self, candles: List[Dict[str, Any]]) -> float:
        closes = [float(c.get("close", 0.0)) for c in candles[-8:] if isinstance(c, dict)]
        if len(closes) < 3:
            return 0.0

        changes = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            curr = closes[i]
            if prev == 0:
                continue
            changes.append(abs((curr - prev) / prev))

        if not changes:
            return 0.0

        avg_change = sum(changes) / len(changes)
        return self._clamp01(avg_change * 40)

    def _estimate_liquidity_sweep(self, row: Dict[str, Any]) -> float:
        candidates = [
            row.get("liquidity_sweep_score"),
            row.get("sweep_score"),
            row.get("liquidity_score"),
            row.get("pressure_acceleration"),
        ]

        for value in candidates:
            try:
                if value is not None:
                    return self._clamp01(abs(float(value)))
            except Exception:
                pass

        return 0.5

    def _tier_history_score(self, regime: str, ai_score: float) -> float:
        regime = str(regime or "").upper()

        if regime == "MEAN_REVERSION":
            base = 0.72
        elif regime == "TREND":
            base = 0.68
        elif regime == "BREAKOUT":
            base = 0.64
        else:
            base = 0.55

        if ai_score >= 0.80:
            base += 0.10
        elif ai_score >= 0.60:
            base += 0.06
        elif ai_score >= 0.40:
            base += 0.03

        return self._clamp01(base)

    def _infer_side(self, accel: float, momentum: float, regime: str) -> str:
        if accel < 0 and momentum > 0.10 and regime == "MEAN_REVERSION":
            return "CALL"
        if accel >= 0:
            return "CALL"
        return "PUT"

    def _clamp01(self, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    def _reject(self, asset: str, reason: str) -> Dict[str, Any]:
        asset_class = self._classify_asset(asset)

        return {
            "asset": asset,
            "symbol": asset,
            "asset_class": asset_class,
            "execute_trade": False,
            "reason": reason,
            "decision_score": 0.0,
            "win_probability": 0.0,
            "loss_probability": 1.0,
            "probability_confidence": "LOW",
            "expected_edge": "WEAK",
            "probability_approved": False,
            "high_probability_setup": False,
            "trade_side": "CALL",
        }
