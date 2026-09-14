from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class OrderIntent:
    broker: str
    symbol: str
    side: str
    quantity: Decimal
    reference_price: Decimal
    estimated_fee_bps: Decimal = Decimal("0")
    estimated_slippage_bps: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if not self.broker.strip() or not self.symbol.strip():
            raise ValueError("broker and symbol are required")
        if self.side.upper() not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if self.quantity <= 0 or self.reference_price <= 0:
            raise ValueError("quantity and reference price must be positive")


def simulate_order_intent(intent: OrderIntent, *, capability_allowed: bool, governance_allowed: bool) -> dict[str, Any]:
    notional = intent.quantity * intent.reference_price
    total_bps = intent.estimated_fee_bps + intent.estimated_slippage_bps
    estimated_cost = (notional * total_bps / Decimal("10000")).quantize(Decimal("0.0001"))
    approved_for_simulation = capability_allowed and governance_allowed
    return {
        "schema_version": "css.order_intent_simulation.v1",
        "broker": intent.broker.upper(),
        "symbol": intent.symbol.upper(),
        "side": intent.side.upper(),
        "quantity": format(intent.quantity, "f"),
        "reference_price": format(intent.reference_price, "f"),
        "notional": format(notional, "f"),
        "estimated_cost": format(estimated_cost, "f"),
        "capability_allowed": capability_allowed,
        "governance_allowed": governance_allowed,
        "simulation_status": "SIMULATED" if approved_for_simulation else "BLOCKED",
        "execution_route": None,
        "submitted_to_broker": False,
        "execution_allowed": False,
    }
