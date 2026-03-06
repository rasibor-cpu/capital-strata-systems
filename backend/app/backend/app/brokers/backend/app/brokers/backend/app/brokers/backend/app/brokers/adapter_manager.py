"""
Broker Adapter Manager
Capital Strata Systems (CSS)

Purpose:
- Resolve the selected broker to the correct adapter class.
- Create initialized adapter instances using registry-approved metadata.
- Keep broker selection explicit and governance-controlled.

Rules:
- No silent fallback to another broker.
- Unsupported brokers must fail closed.
- Adapters must be instantiated only through registered mappings.
"""

from __future__ import annotations

from typing import Any, Dict, Type

from .base_adapter import BaseBrokerAdapter, BrokerCapabilityError
from .broker_registry import get_broker_spec


class AdapterManagerError(Exception):
    """Raised when the adapter manager cannot resolve or build an adapter."""


class CoinbaseAdapter(BaseBrokerAdapter):
    """
    Placeholder Coinbase adapter.

    This will be replaced or wired to the existing live Coinbase adapter layer
    after bootstrap scaffolding is complete.
    """

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def get_account_info(self) -> Dict[str, Any]:
        return {
            "broker": self.broker_name,
            "mode": self.mode,
            "connected": self.connected,
        }

    def get_positions(self) -> list[Dict[str, Any]]:
        return []

    def get_orders(self) -> list[Dict[str, Any]]:
        return []

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        return []

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: float | None = None,
        extra: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return {
            "ok": False,
            "message": "Coinbase adapter placeholder does not place live orders yet.",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
        }

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "message": "Coinbase adapter placeholder does not cancel orders yet.",
            "order_id": order_id,
        }

    def supports_asset_class(self, asset_class: str) -> bool:
        return asset_class.strip().lower() == "spot_crypto"


class OandaAdapter(BaseBrokerAdapter):
    """
    Placeholder OANDA adapter.
    """

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def get_account_info(self) -> Dict[str, Any]:
        return {
            "broker": self.broker_name,
            "mode": self.mode,
            "connected": self.connected,
        }

    def get_positions(self) -> list[Dict[str, Any]]:
        return []

    def get_orders(self) -> list[Dict[str, Any]]:
        return []

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        return []

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: float | None = None,
        extra: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return {
            "ok": False,
            "message": "OANDA adapter placeholder does not place live orders yet.",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
        }

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "message": "OANDA adapter placeholder does not cancel orders yet.",
            "order_id": order_id,
        }

    def supports_asset_class(self, asset_class: str) -> bool:
        return asset_class.strip().lower() == "fx"


class AlpacaAdapter(BaseBrokerAdapter):
    """
    Placeholder Alpaca adapter.
    """

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def get_account_info(self) -> Dict[str, Any]:
        return {
            "broker": self.broker_name,
            "mode": self.mode,
            "connected": self.connected,
        }

    def get_positions(self) -> list[Dict[str, Any]]:
        return []

    def get_orders(self) -> list[Dict[str, Any]]:
        return []

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        return []

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: float | None = None,
        extra: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return {
            "ok": False,
            "message": "Alpaca adapter placeholder does not place live orders yet.",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
        }

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "message": "Alpaca adapter placeholder does not cancel orders yet.",
            "order_id": order_id,
        }

    def supports_asset_class(self, asset_class: str) -> bool:
        normalized = asset_class.strip().lower()
        return normalized in {"equities", "crypto"}


ADAPTER_CLASS_REGISTRY: Dict[str, Type[BaseBrokerAdapter]] = {
    "coinbase": CoinbaseAdapter,
    "oanda": OandaAdapter,
    "alpaca": AlpacaAdapter,
}


def create_adapter(
    broker_name: str,
    mode: str,
    credentials: Dict[str, Any] | None = None,
    asset_class: str | None = None,
) -> BaseBrokerAdapter:
    """
    Create a broker adapter instance for the selected broker.

    Raises:
        AdapterManagerError: If the broker is unsupported or adapter creation fails.
        BrokerCapabilityError: If the broker does not support the requested asset class.
    """
    spec = get_broker_spec(broker_name)
    key = spec.name

    if key not in ADAPTER_CLASS_REGISTRY:
        raise AdapterManagerError(
            f"No adapter class registered for broker '{broker_name}'."
        )

    adapter_cls = ADAPTER_CLASS_REGISTRY[key]

    try:
        adapter = adapter_cls(
            broker_name=spec.name,
            mode=mode,
            credentials=credentials or {},
        )
    except Exception as exc:
        raise AdapterManagerError(
            f"Failed to instantiate adapter for broker '{broker_name}': {exc}"
        ) from exc

    if asset_class and not adapter.supports_asset_class(asset_class):
        raise BrokerCapabilityError(
            f"Broker '{broker_name}' does not support asset class '{asset_class}'."
        )

    return adapter
