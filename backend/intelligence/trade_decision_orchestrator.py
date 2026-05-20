from typing import Any, Dict, List
from backend.app.persistence.repositories.session_repository import SessionRepository
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.services.session_runtime_service import SessionRuntimeService
from backend.app.persistence.services.trade_runtime_service import TradeRuntimeService
from backend.app.persistence.services.pnl_runtime_service import PnlRuntimeService
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate


class TradeDecisionOrchestrator:

    def __init__(self, total_capital: float = 10000.0) -> None:
        self.total_capital = total_capital
        self.trade_gate = CSSUnifiedTradeGate()

        self.session_repository = SessionRepository()
        self.persistence_service = PersistenceService()
        self.session_runtime_service = SessionRuntimeService()
        self.trade_runtime_service = TradeRuntimeService()
        self.pnl_runtime_service = PnlRuntimeService()

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _build_decision_payload(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
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
            "runtime": {
                "persistence_ready": True,
                "session_tracking": True,
                "trade_tracking": True,
                "pnl_tracking": True,
            },
        }

    def evaluate_trade(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._build_decision_payload(market_data)

    def evaluate_market_batch(self, market_dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []

        for data in market_dataset:
            decision = self.evaluate_trade(data)
            results.append(decision)

        return {
            "total_scanned": len(results),
            "executed_trades": [],
            "all_decisions": results,
        }
