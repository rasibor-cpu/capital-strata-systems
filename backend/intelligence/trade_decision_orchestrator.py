from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.market_regime_detector import MarketRegimeDetector
from backend.intelligence.opportunity_momentum_window_engine import OpportunityMomentumWindowEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.probability_prediction_engine import ProbabilityPredictionEngine
from backend.intelligence.profitability_guard import ProfitabilityGuard
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.intelligence.adaptive_exit_engine import AdaptiveExitEngine

from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate


class TradeDecisionOrchestrator:

    def __init__(self, total_capital: float = 10000.0) -> None:
        self.regime_detector = MarketRegimeDetector()
        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()
        self.capital_allocator = CapitalAllocator(total_capital=total_capital)
        self.exit_engine = AdaptiveExitEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()
        self.probability_engine = ProbabilityPredictionEngine()
        self.profitability_guard = ProfitabilityGuard()
        self.trade_gate = CSSUnifiedTradeGate()

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _normalize_asset_class(self, asset_class: Any) -> str:
        asset = str(asset_class or "").strip().lower()
        aliases = {
            "forex": "fx",
            "currency": "fx",
            "currencies": "fx",
            "future": "futures",
            "option": "options",
        }
        return aliases.get(asset, asset)

    def _dictify(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if is_dataclass(value):
            return asdict(value)
        return {}

    def _detect_regime(self, market_data: Dict[str, Any]) -> str:
        explicit = market_data.get("regime")
        if explicit:
            return str(explicit).upper()

        candles = market_data.get("candles")
        if isinstance(candles, list) and hasattr(self.regime_detector, "detect_regime"):
            result = self.regime_detector.detect_regime(candles)
            return str(result.get("regime", "UNSTABLE")).upper()

        return "UNSTABLE"

    def _evaluate_confluence(self, market_data: Dict[str, Any]) -> float:
        candles = market_data.get("candles")
        if isinstance(candles, list):
            result = self.signal_confluence_engine.evaluate(candles)
            return self._safe_float(self._dictify(result).get("confluence_score"), 0.0)
        return self._safe_float(market_data.get("confluence_score"), 0.0)

    def _evaluate_pressure(self, market_data: Dict[str, Any]) -> float:
        if hasattr(self.pressure_engine, "compute_pressure"):
            result = self.pressure_engine.compute_pressure(market_data)
            return self._safe_float(result.get("pressure"), 0.0)
        return self._safe_float(market_data.get("pressure_score"), 0.0)

    def _evaluate_acceleration(self, market_data: Dict[str, Any]) -> float:
        if hasattr(self.acceleration_engine, "enrich_rows"):
            rows = self.acceleration_engine.enrich_rows([market_data])
            if rows:
                row = rows[0]
                return self._safe_float(
                    row.get("acceleration_score", row.get("pressure_acceleration")),
                    0.0,
                )
        return self._safe_float(market_data.get("acceleration_score"), 0.0)

    def _evaluate_momentum(self, market_data: Dict[str, Any]) -> float:
        if hasattr(self.momentum_engine, "enrich"):
            rows = self.momentum_engine.enrich([market_data])
            if rows:
                return self._safe_float(rows[0].get("momentum_score"), 0.0)
        return self._safe_float(market_data.get("momentum"), 0.0)

    def _predict_probability(
        self,
        market_data: Dict[str, Any],
        *,
        ai_score: float,
        confluence: float,
        pressure: float,
        acceleration: float,
        momentum: float,
        regime: str,
    ) -> Dict[str, Any]:
        explicit_probability = market_data.get("probability")
        if explicit_probability is not None:
            win_probability = max(0.0, min(self._safe_float(explicit_probability), 1.0))
            return {
                "win_probability": win_probability,
                "approve_trade": win_probability >= 0.50,
            }

        return self.probability_engine.evaluate_trade_probability(
            ai_score=ai_score,
            confluence=confluence,
            pressure=pressure,
            momentum=momentum,
            elasticity=acceleration,
            regime_confidence=1.0 if regime not in {"UNSTABLE", "NEUTRAL"} else 0.3,
            liquidity_sweep=max(
                0.0,
                min(self._safe_float(market_data.get("liquidity_score"), 0.0) / 100.0, 1.0),
            ),
            tier_history=self._safe_float(market_data.get("tier_history"), 0.0),
            symbol=str(market_data.get("symbol", "")),
            side=str(market_data.get("side", "")),
        )

    def _governance_decision(
        self,
        market_data: Dict[str, Any],
        *,
        probability: float,
    ):
        candidate = {
            "symbol": market_data.get("symbol"),
            "asset_class": self._normalize_asset_class(market_data.get("asset_class")),
            "expected_value": self._safe_float(
                market_data.get("expected_value"),
                abs(self._safe_float(market_data.get("vwap_edge"), 0.0)),
            ),
            "cost": self._safe_float(
                market_data.get("cost"),
                abs(self._safe_float(market_data.get("spread_pct"), 0.0)),
            ),
            "probability": probability,
        }

        session = market_data.get("session")
        if not isinstance(session, dict):
            session = {}

        portfolio_state = market_data.get("portfolio_state")
        if not isinstance(portfolio_state, dict):
            portfolio_state = {}

        engine_mode = str(market_data.get("engine_mode", "SAFE")).upper()

        return self.trade_gate.approve_trade(
            candidate=candidate,
            session=session,
            portfolio_state=portfolio_state,
            engine_mode=engine_mode,
        )

    def _allocate_decision(
        self,
        decision: Dict[str, Any],
        *,
        asset_class: str,
        confidence: float,
    ) -> Dict[str, Any]:
        symbol = str(decision.get("symbol") or "").upper()
        if not symbol:
            return {}

        candidate = {
            "symbol": symbol,
            "asset_class": asset_class,
            "score": confidence,
            "trade_score": confidence,
            "spread_bps": decision.get("spread_bps", 0.0),
            "price": decision.get("price", 0.0),
            "vwap": decision.get("vwap", 0.0),
        }

        allocations = self.capital_allocator.allocate(
            ai_results=[candidate],
            market_rows=[candidate],
        )
        if not allocations:
            return {}
        return allocations[0]

    def _build_exit_plan(
        self,
        *,
        asset_class: str,
        regime: str,
        confidence: float,
    ) -> Dict[str, Any]:
        get_exit_plan = getattr(self.exit_engine, "get_exit_plan", None)
        if callable(get_exit_plan):
            return get_exit_plan(
                asset_class=asset_class,
                regime=regime,
                confidence=confidence,
            )

        return {
            "max_cycles": 3,
            "type": "adaptive",
        }

    # =========================================================
    # CORE SINGLE-ASSET EVALUATION (UNCHANGED LOGIC)
    # =========================================================
    def evaluate_trade(self, market_data: Dict[str, Any]) -> Dict[str, Any]:

        regime = self._detect_regime(market_data)

        ai_score = self.ai_scorer.score(market_data)
        confluence = self._evaluate_confluence(market_data)
        pressure = self._evaluate_pressure(market_data)
        acceleration = self._evaluate_acceleration(market_data)
        momentum = self._evaluate_momentum(market_data)

        raw_score = (
            ai_score
            + confluence
            + pressure
            + acceleration
            + momentum
        )

        probability_output = self._predict_probability(
            market_data,
            regime=regime,
            ai_score=ai_score,
            confluence=confluence,
            pressure=pressure,
            acceleration=acceleration,
            momentum=momentum,
        )

        win_probability = probability_output.get("win_probability", 0.0)
        approve_trade = probability_output.get("approve_trade", False)

        if not isinstance(win_probability, (int, float)):
            win_probability = 0.0
        win_probability = max(0.0, min(float(win_probability), 1.0))

        vwap_edge = market_data.get("vwap_edge", 0.0)
        volume = market_data.get("volume", 0.0)

        css_quality_pass = (
            abs(vwap_edge) >= 10
            and volume > 0
            and raw_score > 1.2
            and win_probability >= 0.35
        )

        if not isinstance(raw_score, (int, float)):
            raw_score = 0.0

        gate_decision = self._governance_decision(
            market_data,
            probability=float(win_probability),
        )

        if not hasattr(gate_decision, "approved"):
            governance_approved = False
            governance_error = True
        else:
            governance_approved = bool(gate_decision.approved)
            governance_error = False

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

        execute_trade = (
            css_quality_pass
            and approve_trade
            and governance_approved
            and profitability_approved
        )

        decision_score = max(0.0, min(raw_score / 5.0, 1.0))

        return {
            "symbol": market_data.get("symbol"),
            "execute_trade": execute_trade,
            "decision_score": decision_score,
            "raw_score": raw_score,
            "win_probability": win_probability,
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
                "governance_reason": getattr(gate_decision, "reason", "unavailable"),
            },
        }

    # =========================================================
    # NEW — BATCH / CYCLE ENGINE (THIS IS THE BIG WIN)
    # =========================================================
    def evaluate_market_batch(self, market_dataset: List[Dict[str, Any]]) -> Dict[str, Any]:

        results = []
        executed = []

        for data in market_dataset:
            decision = self.evaluate_trade(data)

            if decision["execute_trade"]:
                decision = self.enrich_decision(
                    decision,
                    asset_class=data.get("asset_class", "unknown"),
                    confidence=decision["decision_score"],
                    regime=decision["regime"],
                )
                executed.append(decision)

            results.append(decision)

        return {
            "total_scanned": len(results),
            "executed_trades": executed,
            "all_decisions": results,
        }

    # =========================================================
    # ENRICHMENT (UNCHANGED)
    # =========================================================
    def enrich_decision(self, decision: dict, asset_class: str, confidence: float, regime: str):
        try:
            allocation = self._allocate_decision(
                decision,
                asset_class=asset_class,
                confidence=confidence,
            )

            exit_plan = self._build_exit_plan(
                asset_class=asset_class,
                regime=regime,
                confidence=confidence
            )

            decision.update({
                "capital_allocation": allocation,
                "position_size": allocation.get("size", allocation.get("capital", 0)),
                "max_hold_cycles": exit_plan.get("max_cycles", 3),
                "exit_type": exit_plan.get("type", "adaptive")
            })

        except Exception as e:
            decision["enrichment_error"] = str(e)

        return decision
