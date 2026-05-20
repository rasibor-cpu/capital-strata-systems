from typing import Any, Dict, List

from backend.app.persistence.repositories.session_repository import SessionRepository
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate


class TradeDecisionOrchestrator:
    def __init__(self, total_capital: float = 10000.0) -> None:
        self.total_capital = total_capital
        self.trade_gate = CSSUnifiedTradeGate()

        # Safe persistence injection only.
        # No persistence writes are performed at this stage.
        self.session_repository = SessionRepository()

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def evaluate_trade(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": market_data.get("symbol"),
            "execute_trade": False,
            "decision_score": 0.0,
            "raw_score": 0.0,
            "regime": "SAFE",
            "components": {},
            "filters": {
                "governance_approved": False,
                "persistence_enabled": True,
            },
        }

    def evaluate_market_batch(
        self,
        market_dataset: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        results = []

        for data in market_dataset:
            decision = self.evaluate_trade(data)
            results.append(decision)

        return {
            "total_scanned": len(results),
            "executed_trades": [],
            "all_decisions": results,
        }