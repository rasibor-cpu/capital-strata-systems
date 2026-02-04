"""
Binance Paper Broker Adapter (Simulated)
========================================

SAFE BY DESIGN:
- PAPER/SIM MODE ONLY
- Envelope-validated execution
- NO live trading
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from engine.brokers.base_broker import BaseBroker, BrokerExecutionResult


class BinancePaperBroker(BaseBroker):
    """
    Simulated paper broker for Binance-style crypto execution.
    """

    name = "BINANCE_PAPER"

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

        # ---------------------------------------------------------
        # HARD SAFETY CHECK
        # ---------------------------------------------------------
        if decision_envelope.get("final_decision") != "ALLOW":
            raise RuntimeError(
                f"BINANCE_PAPER refused order: decision envelope = {decision_envelope.get('final_decision')}"
            )

        order_id = f"BINANCE-PAPER-{uuid.uuid4()}"

        # Synthetic fill price
        fill_price = price
        if fill_price is None:
            snapshot = decision_envelope.get("inputs", {}).get("snapshot", {})
            fill_price = snapshot.get("price", 0.0)

        result: BrokerExecutionResult = {
            "order_id": order_id,
            "broker": self.name,
            "instrument": instrument,
            "side": side,
            "status": "FILLED",
            "filled_qty": quantity,
            "avg_fill_price": fill_price,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "raw": {
                "note": "Simulated Binance paper fill",
                "order_type": order_type,
            },
        }
        return result
