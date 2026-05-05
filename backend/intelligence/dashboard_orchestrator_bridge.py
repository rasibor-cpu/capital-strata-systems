from __future__ import annotations

from typing import Any, Dict, List

from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator


def run_dashboard_orchestration(market_dataset: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    """
    PCNRASS bridge:
    Keeps dashboard display-focused while routing decision work to TradeDecisionOrchestrator.
    """
    orchestrator = TradeDecisionOrchestrator()
    dataset = market_dataset or []

    return orchestrator.evaluate_market_batch(dataset)