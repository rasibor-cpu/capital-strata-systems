from typing import Any

from backend.app.persistence.services.persistence_service import PersistenceService


class BrokerReconciliationService:

    def __init__(self) -> None:
        self.persistence = PersistenceService()

    def get_runtime_open_trades(self, session_id: str) -> list[dict[str, Any]]:
        return self.persistence.trades.get_open_trades(session_id=session_id)

    def reconcile_against_broker_state(
        self,
        session_id: str,
        broker_positions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        runtime_trades = self.get_runtime_open_trades(session_id=session_id)

        runtime_symbols = {trade["symbol"] for trade in runtime_trades}
        broker_symbols = {position["symbol"] for position in broker_positions}

        orphan_runtime_positions = runtime_symbols - broker_symbols
        orphan_broker_positions = broker_symbols - runtime_symbols

        return {
            "session_id": session_id,
            "runtime_trade_count": len(runtime_trades),
            "broker_position_count": len(broker_positions),
            "orphan_runtime_positions": list(orphan_runtime_positions),
            "orphan_broker_positions": list(orphan_broker_positions),
            "reconciliation_required": bool(
                orphan_runtime_positions or orphan_broker_positions
            ),
            "ibkr_ready": True,
        }
