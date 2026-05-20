from typing import Any

from backend.brokers.ibkr.ibkr_adapter import IBKRAdapter
from backend.app.persistence.services.broker_reconciliation_service import BrokerReconciliationService


class IBKRRuntimeManager:

    def __init__(
        self,
        paper_trading: bool = True,
    ) -> None:

        self.adapter = IBKRAdapter(
            paper_trading=paper_trading
        )

        self.reconciliation_service = (
            BrokerReconciliationService()
        )

    def initialize(self) -> bool:
        return self.adapter.connect()

    def shutdown(self) -> None:
        self.adapter.disconnect()

    def is_healthy(self) -> bool:
        return self.adapter.is_connected()

    def get_runtime_health(self) -> dict[str, Any]:
        return self.adapter.health_check()

    def get_account_snapshot(self) -> dict[str, Any]:
        return self.adapter.get_account_snapshot()

    def get_positions(self) -> list[dict[str, Any]]:
        return self.adapter.get_positions()

    def reconcile_runtime_state(
        self,
        session_id: str,
    ) -> dict[str, Any]:

        broker_positions = (
            self.get_positions()
        )

        return (
            self.reconciliation_service
            .reconcile_against_broker_state(
                session_id=session_id,
                broker_positions=broker_positions,
            )
        )
