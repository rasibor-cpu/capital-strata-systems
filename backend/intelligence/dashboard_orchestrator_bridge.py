from __future__ import annotations
from typing import Any, Dict, List
from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator
from backend.intelligence.global_intelligence.dashboard_intelligence_adapter import build_dashboard_intelligence_payload
from backend.intelligence.global_intelligence.intelligence_state_manager import IntelligenceStateManager


def run_dashboard_orchestration(
    symbols: List[str] | None = None,
    *,
    canonical_decision: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Bridge between dashboard and orchestrator
    Converts simple symbol list → orchestrator dataset
    """

    orchestrator = TradeDecisionOrchestrator()

    dataset: List[Dict[str, Any]] = []

    if symbols:
        for sym in symbols:
            dataset.append({
                "symbol": sym,
                "asset_class": "CRYPTO",  # default for now (we expand later)
                "price": 0.0,
                "volume": 0.0,
                "volatility": 0.0,
                "spread_pct": 0.0,
                "liquidity_score": 0.0,
                "vwap": 0.0,
            })

    result = orchestrator.evaluate_market_batch(dataset)
    result["dashboard_intelligence"] = build_dashboard_intelligence_payload(
        IntelligenceStateManager(),
        canonical_decision=canonical_decision,
    )
    return result