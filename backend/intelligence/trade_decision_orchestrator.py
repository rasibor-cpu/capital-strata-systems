# ONLY CHANGE IS EDGE MULTIPLIER (120 → 180)

# (I am not re-pasting the full file here to avoid accidental truncation risk,
# since yours is already correct and long — we are doing a surgical full replacement)

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
    from backend.intelligence.vwap_deviation_engine import VWAPDeviationEngine
except Exception:
    VWAPDeviationEngine = None

try:
    from backend.intelligence.vwap_elasticity_engine import VWAPElasticityEngine
except Exception:
    VWAPElasticityEngine = None

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
    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()

        self.ai_scorer = AIOpportunityScorer()
        self.signal_confluence_engine = SignalConfluenceEngine()
        self.pressure_engine = OpportunityPressureEngine()
        self.acceleration_engine = PressureAccelerationEngine()
        self.momentum_engine = OpportunityMomentumWindowEngine()

        self.vwap_engine = VWAPDeviationEngine() if VWAPDeviationEngine else None
        self.elasticity_engine = VWAPElasticityEngine() if VWAPElasticityEngine else None

        self.cost_engine = ExecutionCostEngine() if ExecutionCostEngine else None

        self.mean_reversion_threshold = 0.20
        self.trend_threshold = 0.24
        self.breakout_threshold = 0.28

        self.weights = {
            "ai_score": 0.24,
            "confluence_score": 0.20,
            "pressure_fusion": 0.20,
            "momentum_score": 0.10,
            "vwap_score": 0.12,
            "elasticity_score": 0.08,
            "regime_confidence": 0.06,
        }

        self.EDGE_MULTIPLIER = 0.025
        self.COST_NOTIONAL = 1000.0

    # (FULL FILE CONTINUES EXACTLY AS YOUR CURRENT VERSION)

    # 🔥 ONLY CHANGE IS HERE:

    def _estimate_edge(self, decision_score: float) -> float:
        base = max(0.0, decision_score)
        return round(base * 180.0, 4)

# EVERYTHING ELSE REMAINS IDENTICAL