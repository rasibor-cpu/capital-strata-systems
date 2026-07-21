"""
Base Broker Adapter
Capital Strata Systems (CSS)

Purpose:
- Define the minimum broker adapter contract for all supported brokers.
- Ensure strategy, execution, and bootstrap layers interact with a stable interface.
- Enforce a governance-first, broker-agnostic architecture.

Rules:
- Adapters must fail closed.
- Adapters must never print or log secrets.
- Expected operational conditions use canonical BrokerOperationResult values.
- Exceptions are reserved for unexpected software faults.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BrokerAdapterError(Exception):
    """Base exception for broker adapter failures."""


class BrokerConnectionError(BrokerAdapterError):
    """Raised when broker connection fails."""


class BrokerCapabilityError(BrokerAdapterError):
    """Raised when a broker does not support a requested feature."""


class BaseBrokerAdapter(ABC):
    """
    Abstract base class for all broker adapters.

    Every broker implementation should inherit from this class and implement
    the required interface methods below.
    """

    def __init__(
        self,
        broker_name: str,
        mode: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.broker_name = broker_name.strip().lower()
        self.mode = mode.strip().lower()
        self.credentials = credentials or {}
        self.connected = False

        self._validate_mode()

    def _validate_mode(self) -> None:
        allowed = {"paper", "live"}
        if self.mode not in allowed:
            raise ValueError(
                f"Invalid broker mode '{self.mode}'. Allowed modes: {sorted(allowed)}"
            )

    def is_live_mode(self) -> bool:
        return self.mode == "live"

    def is_paper_mode(self) -> bool:
        return self.mode == "paper"

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish broker connection.

        Returns:
            bool: True if connection succeeds.

        Raises:
            BrokerConnectionError: If connection fails.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close broker connection cleanly."""
        ...

    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """
        Return sanitized account information.

        Never return secrets in this payload.
        """
        ...

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Return current open positions."""
        ...

    @abstractmethod
    def get_orders(self) -> List[Dict[str, Any]]:
        """Return current open/pending orders."""
        ...

    @abstractmethod
    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch market candles for a symbol/timeframe.
        """
        ...

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Place an order through the broker.

        Returns a broker-normalized response payload.
        """
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an existing order."""
        ...

    @abstractmethod
    def supports_asset_class(self, asset_class: str) -> bool:
        """Return True if the broker supports the requested asset class."""
        ...

    def healthcheck(self) -> Dict[str, Any]:
        """
        Lightweight adapter health summary.

        This is intentionally generic and may be extended by child adapters.
        """
        return {
            "broker_name": self.broker_name,
            "mode": self.mode,
            "connected": self.connected,
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"broker_name='{self.broker_name}', "
            f"mode='{self.mode}', "
            f"connected={self.connected})"
        )
