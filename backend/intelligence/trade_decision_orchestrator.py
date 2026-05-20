from typing import Any, Dict, List
from decimal import Decimal
from uuid import uuid4

from backend.app.persistence.repositories.session_repository import SessionRepository
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.app.persistence.services.session_runtime_service import SessionRuntimeService
from backend.app.persistence.services.trade_runtime_service import TradeRuntimeService
from backend.app.persistence.services.pnl_runtime_service import PnlRuntimeService
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate


class TradeDecisionOrchestrator:

    def __init__(
        self,
        total_capital: float = 10000.0,
        mode: str = "paper",
        broker_name: str = "internal",
        broker_mode: str = "paper",
    ) -> None:

        self.total_capital = total_capital
        self.trade_gate = CSSUnifiedTradeGate()

        self.session_repository = SessionRepository()
        self.persistence_service = PersistenceService()
        self.session_runtime_service = SessionRuntimeService()
        self.trade_runtime_service = TradeRuntimeService()
        self.pnl_runtime_service = PnlRuntimeService()

        self.session_id = self._initialize_runtime_session(
            mode=mode,
            broker_name=broker_name,
            broker_mode=broker_mode,
        )

    def _initialize_runtime_session(
        self,
        mode: str,
        broker_name: str,
        broker_mode: str,
    ) -> str:

        active_sessions = (
            self.session_repository
            .get_active_sessions()
        )

        if active_sessions:
            active_session = active_sessions[0]

            return str(
                active_session["session_id"]
            )

        return (
            self.session_runtime_service
            .create_runtime_session(
                mode=mode,
                broker_name=broker_name,
                broker_mode=broker_mode,
            )
        )

    def _safe_float(
        self,
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:
            if value is None:
                return default

            return float(value)

        except Exception:
            return default

    def _trade_already_exists(
        self,
        symbol: str,
        direction: str = "long",
    ) -> bool:

        return (
            self.trade_runtime_service
            .trade_exists(
                session_id=self.session_id,
                symbol=symbol,
                direction=direction,
            )
        )

    def _persist_trade_open(
        self,
        symbol: str,
    ) -> str | None:

        if self._trade_already_exists(
            symbol=symbol,
            direction="long",
        ):
            return None

        trade_id = str(uuid4())

        self.trade_runtime_service.open_trade(
            trade_id=trade_id,
            session_id=self.session_id,
            broker_name="internal",
            broker_mode="paper",
            symbol=symbol,
            direction="long",
            order_type="market",
            quantity=Decimal("1"),
            filled_quantity=Decimal("1"),
            entry_price=Decimal("0"),
            raw_payload_json=None,
        )

        return trade_id

    def _persist_trade_close(
        self,
        trade_id: str | None,
    ) -> None:

        if trade_id is None:
            return

        self.trade_runtime_service.close_trade(
            trade_id=trade_id,
            exit_price=Decimal("0"),
            realized_pnl=Decimal("0"),
        )

    def _persist_runtime_snapshot(self) -> None:

        self.pnl_runtime_service.create_snapshot(
            session_id=self.session_id,
            broker_name="internal",
            broker_mode="paper",
            equity=Decimal(str(self.total_capital)),
            cash_balance=Decimal(str(self.total_capital)),
            buying_power=Decimal(str(self.total_capital)),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            open_positions=0,
            payload_json=None,
        )

    def _build_decision_payload(
        self,
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        symbol = str(
            market_data.get("symbol", "UNKNOWN")
        )

        trade_id = self._persist_trade_open(
            symbol=symbol
        )

        self._persist_trade_close(
            trade_id=trade_id
        )

        self._persist_runtime_snapshot()

        duplicate_trade_blocked = (
            trade_id is None
        )

        return {
            "symbol": symbol,
            "trade_id": trade_id,
            "execute_trade": False,
            "decision_score": 0.0,
            "raw_score": 0.0,
            "regime": "SAFE",
            "components": {},
            "filters": {
                "governance_approved": False,
                "persistence_enabled": True,
                "duplicate_trade_blocked": duplicate_trade_blocked,
            },
            "runtime": {
                "session_id": self.session_id,
                "persistence_ready": True,
                "session_tracking": True,
                "trade_tracking": True,
                "pnl_tracking": True,
                "startup_recovery_enabled": True,
            },
        }

    def evaluate_trade(
        self,
        market_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        return self._build_decision_payload(
            market_data
        )

    def evaluate_market_batch(
        self,
        market_dataset: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        results = []

        for data in market_dataset:
            decision = self.evaluate_trade(
                data
            )

            results.append(decision)

        return {
            "session_id": self.session_id,
            "total_scanned": len(results),
            "executed_trades": [],
            "all_decisions": results,
        }
