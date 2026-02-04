"""
Alpaca Paper Broker Adapter
===========================

SAFE BY DESIGN:
- PAPER MODE ONLY
- Envelope-validated execution
- NO live trading
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from engine.brokers.base_broker import BaseBroker, BrokerExecutionResult


class AlpacaPaperBroker(BaseBroker):
    """
    Paper-only Alpaca broker adapter.
    """

    name = "ALPACA_PAPER"

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
                f"Broker refused order: decision envelope = {decision_envelope.get('final_decision')}"
            )

        # ---------------------------------------------------------
        # SIMULATED PAPER FILL
        # ---------------------------------------------------------
        order_id = f"PAPER-{uuid.uuid4()}"

        fill_price = price
        if fill_price is None:
            # fallback synthetic fill
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
                "note": "Simulated Alpaca paper fill",
                "order_type": order_type,
            },
        }

        return result
