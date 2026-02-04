"""
Base Broker Interface (Paper / Live Agnostic)
=============================================

Purpose:
- Define a strict execution contract
- Enforce envelope-driven execution
- Prevent strategy logic from leaking into brokers

ALL brokers (paper or live) must implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any


class BrokerExecutionResult(Dict[str, Any]):
    """
    Normalized broker response.
    Required keys:
    - order_id
    - status
    - filled_qty
    - avg_fill_price
    - timestamp_utc
    - raw
    """
    pass


class BaseBroker(ABC):
    """
    Abstract broker interface.
    """

    name: str = "BASE"

    @abstractmethod
    def submit_order(
        self,
        *,
        instrument: str,
        side: str,
        quantity: float,
        order_type: str,
        price: float | None,
        decision_envelope: Dict[str, Any],
    ) -> BrokerExecutionResult:
        """
        Submit an order to the broker.

        Rules:
        - decision_envelope MUST be supplied
        - broker MUST refuse if envelope.final_decision != ALLOW
        - broker MUST be paper-only unless explicitly live-enabled elsewhere
        """
        raise NotImplementedError
