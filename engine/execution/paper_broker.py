"""
Paper Broker – REA Capital Trading Engine (V1 Freeze)

Responsibilities:
- Simulate execution
- Close trades
- Auto-log to correct ledger (TEST or LIVE)
- Enforce duplicate warning (non-blocking)
- Preserve UTRN across lifecycle

This is the canonical trade-close logging point.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from trade_ticket import TradeTicket
from engine.reporting.pnl_ledger import append_pnl_event


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PaperFillResult:
    utrn: str
    pnl: float
    exit_px: float
    timestamp_utc: str


class PaperBroker:
    """
    Central paper execution handler.

    Any broker adapter should route simulated fills here.
    """

    def execute_and_close(
        self,
        ticket: TradeTicket,
        fill_price: float,
        fees: float = 0.0,
    ) -> PaperFillResult:
        """
        Simulates immediate fill and close (paper mode).

        ticket.mode determines which ledger file is used.
        """

        if not isinstance(ticket, TradeTicket):
            raise TypeError("execute_and_close requires TradeTicket")

        # ---------------------------------------------------
        # Duplicate Warning (non-blocking)
        # ---------------------------------------------------
        dup = ticket.run_duplicate_check()
        if dup.decision == "WARN":
            print(f"\nWARNING | DUPLICATE_TRADE | {dup.reason}")
            print(f"WARNING | UTRN={ticket.utrn}")

        # ---------------------------------------------------
        # Basic PnL Calculation
        # ---------------------------------------------------
        if ticket.entry_px <= 0:
            raise ValueError("entry_px must be set on ticket")

        qty = ticket.qty
        if qty <= 0:
            qty = ticket.amount / ticket.entry_px

        if ticket.side.upper() in ("BUY", "LONG"):
            pnl = (fill_price - ticket.entry_px) * qty
        else:
            pnl
