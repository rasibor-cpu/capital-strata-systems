from __future__ import annotations
from typing import Any, Dict, List
from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator


def run_dashboard_orchestration(symbols: List[str] | None = None) -> Dict[str, Any]:
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

    return orchestrator.evaluate_market_batch(dataset)