"""
Capital Strata Systems
Phase 97B.1

OANDA Margin Adapter Skeleton
"""

from datetime import datetime, timezone

from engine.risk.broker_margin_contract import (
    BrokerMarginProvider,
    BrokerMarginSnapshot,
)


class OandaMarginAdapter(BrokerMarginProvider):
    """
    Deterministic OANDA margin adapter.

    No live API calls.
    No credential access.
    No execution logic.
    """

    def __init__(
        self,
        account_id: str = "SIMULATED-OANDA",
        available_margin: float = 10000.0,
        required_margin: float = 2000.0,
    ):
        self.account_id = account_id
        self.available_margin = float(available_margin)
        self.required_margin = float(required_margin)

    def get_margin_snapshot(self) -> BrokerMarginSnapshot:
        free_margin = self.available_margin - self.required_margin

        utilization = 0.0
        if self.available_margin > 0:
            utilization = (
                self.required_margin / self.available_margin
            ) * 100.0

        return BrokerMarginSnapshot(
            broker_name="OANDA",
            account_id=self.account_id,
            required_margin=round(self.required_margin, 2),
            available_margin=round(self.available_margin, 2),
            free_margin=round(free_margin, 2),
            margin_utilization_pct=round(utilization, 2),
            margin_source="SIMULATED",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )