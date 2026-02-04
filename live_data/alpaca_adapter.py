"""
ALPACA Paper Trading Adapter
----------------------------

Purpose:
- Paper / simulated adapter for Alpaca
- Used by ExecutionRouter in TEST / REPLAY modes
- Produces safe fills for replay + audit

IMPORTANT:
- This adapter NEVER sends live orders
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Any


class AlpacaPaperAdapter:
    """
    Paper / simulated Alpaca adapter.
    """

    broker_name = "ALPACA_PAPER"

    def __init__(self) -> None:
        self.mode = "TEST"

    def execute_order(
        self,
        *,
        instrument: str,
        side: str,
        quantity: int,
        order_type: str,
        price: float | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "order_id": f"ALPACA-PAPER-{uuid.uuid4()}",
            "broker": self.broker_name,
            "instrument": instrument,
            "side": side,
            "status": "FILLED",
            "filled_qty": quantity,
            "avg_fill_price": price or 0.0,
            "timestamp_utc": now.isoformat(),
            "raw": {
                "note": "Simulated Alpaca paper fill",
                "order_type": order_type,
            },
        }

    # Router compatibility
    def execute(
        self,
        *,
        instrument: str,
        side: str,
        quantity: int,
        order_type: str,
        price: float | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.execute_order(
            instrument=instrument,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            **kwargs,
        )
