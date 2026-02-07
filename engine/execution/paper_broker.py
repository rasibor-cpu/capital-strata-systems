"""
Paper Broker – REA Capital Trading Engine (V1 Freeze)

Canonical paper close path:
- Duplicate warning (non-blocking)
- PnL calc
- Auto-ledger logging (TEST vs LIVE separate files)
- ALWAYS returns a PaperFillResult (never None)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from trade_ticket import TradeTicket
from engine.reporting.pnl_ledger import append_pnl_event


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PaperFillResult:
    utrn: str
    pnl: float
    exit_px: float
    timestamp_utc: str


class PaperBroker:
    """
    Central paper execution handler.
    """

    def execute_and_close(
        self,
        ticket: TradeTicket,
        fill_price: float,
        fees: float = 0.0,
    ) -> PaperFillResult:
        if ticket is None:
            raise ValueError("ticket is required")
        if not isinstance(ticket, TradeTicket):
            raise TypeError("execute_and_close requires TradeTicket")
        if fill_price is None:
            raise ValueError("fill_price is required")

        # Duplicate warning (non-blocking)
        dup = ticket.run_duplicate_check()
        if dup.decision == "WARN":
            print(f"WARNING | DUPLICATE_TRADE | {dup.reason}")
            print(f"WARNING | UTRN={ticket.utrn}")

        # Qty derive
        if ticket.entry_px <= 0:
            raise ValueError("ticket.entry_px must be > 0")

        qty = float(ticket.qty or 0.0)
        if qty <= 0.0:
            qty = float(ticket.amount) / float(ticket.entry_px)

        # PnL calc
        side = str(ticket.side).upper().strip()
        if side in ("BUY", "LONG"):
            pnl = (float(fill_price) - float(ticket.entry_px)) * qty
        else:
            pnl = (float(ticket.entry_px) - float(fill_price)) * qty

        # Auto-ledger
        append_pnl_event(
            mode=ticket.mode,
            symbol=ticket.symbol,
            side=ticket.side,
            qty=qty,
            entry_px=ticket.entry_px,
            exit_px=float(fill_price),
            fees=float(fees),
            trade_type=ticket.trade_type,
            execution_date=ticket.execution_date,
            value_date=ticket.value_date,
            currency=ticket.currency,
            amount=ticket.amount,
            fx_rate=ticket.fx_rate,
            exchange_rate_text=ticket.exchange_rate_text,
            tag=ticket.tag,
            trade_id=ticket.utrn,
            ledger_path=ticket.ledger_path(),
        )

        # GUARANTEED return
        return PaperFillResult(
            utrn=ticket.utrn,
            pnl=float(pnl),
            exit_px=float(fill_price),
            timestamp_utc=_utc_now_iso(),
        )
