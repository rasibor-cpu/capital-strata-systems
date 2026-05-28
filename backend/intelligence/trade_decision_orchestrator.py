from __future__ import annotations

import os
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
from backend.intelligence.edge_validation.edge_snapshot import (
    build_edge_snapshot,
)

from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate


class TradeDecisionOrchestrator:

    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()
        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()

        total_capital_raw = os.getenv(
            "CSS_TOTAL_CAPITAL",
            os.getenv(
                "ACCOUNT_EQUITY",
                "100000.0",
            ),
        )

        try:
            total_capital = float(
                total_capital_raw
            )
        except Exception:
            total_capital = 100000.0

        if total_capital <= 0:
            total_capital = 100000.0

        self.capital_allocator = CapitalAllocator(
            total_capital=total_capital
        )
        self.exit_engine = AdaptiveExitEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()
        self.probability_engine = ProbabilityPredictionEngine()
        self.profitability_guard = ProfitabilityGuard()
        self.trade_gate = CSSUnifiedTradeGate()

    # =========================================================
    # CORE SINGLE-ASSET EVALUATION (UNCHANGED LOGIC)
    # =========================================================
    def evaluate_trade(
        self,
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        regime = self.regime_detector.detect(
            market_data
        )

        ai_score = self.ai_scorer.score(
            market_data,
            regime,
        )
        confluence = (
            self.signal_confluence_engine.evaluate(
                market_data
            )
        )
        pressure = self.pressure_engine.evaluate(
            market_data
        )
        acceleration = (
            self.acceleration_engine.evaluate(
                market_data
            )
        )
        momentum = self.momentum_engine.evaluate(
            market_data
        )

        raw_score = (
            ai_score
            + confluence
            + pressure
            + acceleration
            + momentum
        )

        probability_output = (
            self.probability_engine.predict(
                market_data,
                regime=regime,
                raw_score=raw_score,
            )
        )

        win_probability = (
            probability_output.get(
                "win_probability",
                0.0,
            )
        )
        approve_trade = (
            probability_output.get(
                "approve_trade",
                False,
            )
        )

        if not isinstance(
            win_probability,
            (
                int,
                float,
            ),
        ):
            win_probability = 0.0

        win_probability = max(
            0.0,
            min(
                float(win_probability),
                1.0,
            ),
        )

        vwap_edge = market_data.get(
            "vwap_edge",
            0.0,
        )
        volume = market_data.get(
            "volume",
            0.0,
        )

        css_quality_pass = (
            abs(vwap_edge) >= 10
            and volume > 0
            and raw_score > 1.2
            and win_probability >= 0.35
        )

        if not isinstance(
            raw_score,
            (
                int,
                float,
            ),
        ):
            raw_score = 0.0

        gate_decision = self.trade_gate.evaluate(
            market_data=market_data,
            regime=regime,
            score=float(raw_score),
            probability=float(win_probability),
        )

        if not hasattr(
            gate_decision,
            "approved",
        ):
            governance_approved = False
            governance_error = True
        else:
            governance_approved = bool(
                gate_decision.approved
            )
            governance_error = False

        profit_signal = {
            "score": raw_score,
            "probability": win_probability,
            "vwap_edge": vwap_edge,
            "regime": regime,
            "liquidity_score": market_data.get(
                "liquidity_score",
                100,
            ),
            "spread_pct": market_data.get(
                "spread_pct",
                0.0,
            ),
            "volatility": market_data.get(
                "volatility",
                0.01,
            ),
            "acceleration": acceleration,
            "pressure_score": pressure,
        }

        (
            profitability_approved,
            profit_reason,
        ) = self.profitability_guard.evaluate(
            profit_signal
        )

        execute_trade = (
            css_quality_pass
            and approve_trade
            and governance_approved
            and profitability_approved
        )

        decision_score = max(
            0.0,
            min(
                raw_score / 5.0,
                1.0,
            ),
        )

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
            },
        }

    # =========================================================
    # BATCH / CYCLE ENGINE
    # Phase 66C:
    # Additive edge snapshot exposure only.
    # No execution logic, gating, broker, or dashboard mutation.
    # =========================================================
    def evaluate_market_batch(
        self,
        market_dataset: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        results = []
        executed = []

        for data in market_dataset:
            decision = self.evaluate_trade(
                data
            )

            if decision["execute_trade"]:
                decision = self.enrich_decision(
                    decision,
                    asset_class=data.get(
                        "asset_class",
                        "unknown",
                    ),
                    confidence=decision[
                        "decision_score"
                    ],
                    regime=decision[
                        "regime"
                    ],
                )
                executed.append(
                    decision
                )

            results.append(
                decision
            )

        edge_snapshot = build_edge_snapshot(
            [
                {
                    "gross_pnl": (
                        decision.get(
                            "decision_score",
                            0.0,
                        )
                        * 100.0
                    ),
                    "costs": 5.0,
                }
                for decision in executed
            ]
        )

        return {
            "total_scanned": len(results),
            "executed_trades": executed,
            "all_decisions": results,
            "edge_snapshot": edge_snapshot,
        }

    # =========================================================
    # ENRICHMENT (UNCHANGED)
    # =========================================================
    def enrich_decision(
        self,
        decision: dict,
        asset_class: str,
        confidence: float,
        regime: str,
    ):

        try:
            allocation = (
                self.capital_allocator.allocate(
                    asset_class=asset_class,
                    confidence=confidence,
                    regime=regime,
                )
            )

            exit_plan = (
                self.exit_engine.get_exit_plan(
                    asset_class=asset_class,
                    regime=regime,
                    confidence=confidence,
                )
            )

            decision.update(
                {
                    "capital_allocation": allocation,
                    "position_size": allocation.get(
                        "size",
                        0,
                    ),
                    "max_hold_cycles": exit_plan.get(
                        "max_cycles",
                        3,
                    ),
                    "exit_type": exit_plan.get(
                        "type",
                        "adaptive",
                    ),
                }
            )

        except Exception as e:
            decision[
                "enrichment_error"
            ] = str(e)

        return decision