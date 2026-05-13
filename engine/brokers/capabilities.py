"""
Broker Capability Descriptors
-----------------------------

Purpose:
- Declare broker-specific execution constraints
- Validate orders BEFORE routing
- Prevent invalid instrument / order-type / size combinations
- Fail closed by design

This module is PURE DATA + VALIDATION (no execution).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set, Optional


class BrokerCapabilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrokerCapabilities:
    name: str
    instruments: Set[str]
    order_types: Set[str]
    min_qty: int
    max_qty: int
    supports_fractional: bool
    supports_short: bool
    supports_market_orders: bool
    supports_limit_orders: bool
    paper_only: bool


# -------------------------------------------------------------------
# Canonical broker capability registry
# -------------------------------------------------------------------

BROKER_CAPABILITIES: Dict[str, BrokerCapabilities] = {
    "OANDA_PAPER": BrokerCapabilities(
        name="OANDA_PAPER",
        instruments={"EURUSD", "GBPUSD", "USDJPY"},
        order_types={"MARKET", "LIMIT"},
        min_qty=1_000,
        max_qty=1_000_000,
        supports_fractional=False,
        supports_short=True,
        supports_market_orders=True,
        supports_limit_orders=True,
        paper_only=True,
    ),
    "ALPACA_PAPER": BrokerCapabilities(
        name="ALPACA_PAPER",
        instruments={"AAPL", "MSFT", "SPY"},
        order_types={"MARKET", "LIMIT"},
        min_qty=1,
        max_qty=100_000,
        supports_fractional=True,
        supports_short=True,
        supports_market_orders=True,
        supports_limit_orders=True,
        paper_only=True,
    ),
    "IBKR_PAPER": BrokerCapabilities(
        name="IBKR_PAPER",
        instruments={"AAPL", "MSFT", "SPY", "QQQ", "ES", "CL"},
        order_types={"MARKET", "LIMIT"},
        min_qty=1,
        max_qty=100_000,
        supports_fractional=False,
        supports_short=True,
        supports_market_orders=True,
        supports_limit_orders=True,
        paper_only=True,
    ),
    "BINANCE_PAPER": BrokerCapabilities(
        name="BINANCE_PAPER",
        instruments={"BTCUSDT", "ETHUSDT", "SOLUSDT"},
        order_types={"MARKET", "LIMIT"},
        min_qty=1,
        max_qty=1_000_000,
        supports_fractional=True,
        supports_short=False,
        supports_market_orders=True,
        supports_limit_orders=True,
        paper_only=True,
    ),
}


def get_broker_capabilities(broker_name: str) -> BrokerCapabilities:
    if broker_name not in BROKER_CAPABILITIES:
        raise BrokerCapabilityError(f"Unknown broker: {broker_name}")
    return BROKER_CAPABILITIES[broker_name]


def validate_order(
    *,
    broker_name: str,
    instrument: str,
    order_type: str,
    quantity: int,
    side: str,
) -> None:
    caps = get_broker_capabilities(broker_name)

    if instrument not in caps.instruments:
        raise BrokerCapabilityError(
            f"{broker_name}: instrument {instrument} not supported"
        )

    if order_type not in caps.order_types:
        raise BrokerCapabilityError(
            f"{broker_name}: order_type {order_type} not supported"
        )

    if quantity < caps.min_qty or quantity > caps.max_qty:
        raise BrokerCapabilityError(
            f"{broker_name}: quantity {quantity} outside allowed range "
            f"[{caps.min_qty}, {caps.max_qty}]"
        )

    if side.upper() == "SELL" and not caps.supports_short:
        raise BrokerCapabilityError(
            f"{broker_name}: short selling not supported"
        )

    if order_type == "MARKET" and not caps.supports_market_orders:
        raise BrokerCapabilityError(
            f"{broker_name}: market orders not supported"
        )

    if order_type == "LIMIT" and not caps.supports_limit_orders:
        raise BrokerCapabilityError(
            f"{broker_name}: limit orders not supported"
        )
