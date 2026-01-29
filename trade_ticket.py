from __future__ import annotations

"""
Manual Trade Ticket (HARD GATE)

Purpose:
- Present a clear trade ticket
- Require explicit human confirmation
- Log every intent and decision
- Never auto-send orders

This is the LAST gate before any broker call.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json
import os


@dataclass
class TradeTicket:
    instrument: str
    side: str              # 'buy' or 'sell'
    units: int
    price_snapshot: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""
    created_utc: str = ""

    def finalize(self) -> None:
        self.created_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


class ManualTradeGate:
    def __init__(self, log_path: str) -> None:
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def _log(self, record: Dict[str, Any]) -> None:
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def present_and_confirm(self, t: TradeTicket) -> bool:
        """
        Returns True ONLY if user explicitly confirms.
        """
        t.finalize()

        print("\n" + "=" * 60)
        print("MANUAL TRADE TICKET — CONFIRMATION REQUIRED")
        print("=" * 60)
        print(f"Time (UTC):      {t.created_utc}")
        print(f"Instrument:      {t.instrument}")
        print(f"Side:            {t.side.upper()}")
        print(f"Units:           {t.units}")
        print(f"Price snapshot:  {t.price_snapshot:.6f}")

        if t.stop_loss is not None:
            print(f"Stop Loss:       {t.stop_loss:.6f}")
        else:
            print("Stop Loss:       NONE")

        if t.take_profit is not None:
            print(f"Take Profit:     {t.take_profit:.6f}")
        else:
            print("Take Profit:     NONE")

        if t.reason:
            print(f"Reason:          {t.reason}")

        print("=" * 60)
        ans = input("Type EXACTLY 'YES' to send this order: ").strip()

        decision = {
            "ticket": t.__dict__,
            "confirmed": ans == "YES",
            "confirmed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        }

        self._log(decision)

        if ans == "YES":
            print("✔ Order CONFIRMED — sending to broker.")
            return True

        print("✖ Order CANCELLED by user.")
        return False