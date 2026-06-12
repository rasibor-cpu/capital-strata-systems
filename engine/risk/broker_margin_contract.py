"""
Capital Strata Systems
Phase 97A

Broker Margin Contract

Canonical broker margin interface.

No broker implementation.
No API calls.
No dashboard integration.
"""

from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass(frozen=True)
class BrokerMarginSnapshot:
    broker_name: str
    account_id: str

    required_margin: float
    available_margin: float
    free_margin: float

    margin_utilization_pct: float

    margin_source: str
    timestamp: str


class BrokerMarginProvider(ABC):
    """
    Canonical broker margin interface.

    All brokers must implement this contract.
    """

    @abstractmethod
    def get_margin_snapshot(self) -> BrokerMarginSnapshot:
        """
        Return current broker margin state.
        """
        raise NotImplementedError