"""Origin propagation through the trade lifecycle (Issue #102).

recommendation -> user action -> order -> fill -> position lot -> partial close -> final close -> journal
-> performance -> commercial ledgers.

Rules:
- An order must have a recorded origin before any fill is accepted (fail closed).
- Each opening order creates its own position lot (lot id = opening order id). Lots of different origins are never
  merged, even in the same symbol. A lot's origin is the ledger's *current* state for its opening order, so a resolved
  review flows into results through the recorded transition, never by silent rewriting.
- Realised P&L on a close belongs to the lot being closed, not to the closing order. The closing order's own origin is
  kept on the journal entry for transparency.
- A close that names only a symbol is allocated only when every open lot in that symbol currently shares one origin
  and one recommendation; otherwise it is refused (AttributionError) so a person chooses the lot.
- Journal entries are append-only and record the origin as it stood at that moment, plus the policy version.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .model import AttributionError, OriginLedger, TradeOrigin

log = logging.getLogger("css.trade_origin.lifecycle")


@dataclass
class PositionLot:
    lot_id: str                   # = opening order id
    symbol: str
    side: str                     # BUY = long, SELL = short
    opened_at: datetime
    recommendation_id: Optional[str] = None
    quantity_opened: float = 0.0
    quantity_open: float = 0.0
    avg_entry_price: float = 0.0
    realized_pnl: float = 0.0
    closes: List[dict] = field(default_factory=list)

    @property
    def is_closed(self) -> bool:
        return self.quantity_opened > 0 and self.quantity_open <= 1e-12


class TradeLifecycle:
    def __init__(self, ledger: OriginLedger):
        self.ledger = ledger
        self.lots: Dict[str, PositionLot] = {}
        self.journal: List[dict] = []
        self._fills_seen: set = set()

    def origin_of(self, lot: PositionLot) -> TradeOrigin:
        return self.ledger.current(lot.lot_id)

    # ---------------------------------------------------------------- journal
    def _journal(self, event: str, at: datetime, lot: PositionLot, order_id: str, **extra) -> dict:
        rec = self.ledger.require(lot.lot_id)
        e = {"event": event, "at": at.isoformat(), "order_id": order_id, "lot_id": lot.lot_id, "symbol": lot.symbol,
             "origin": self.origin_of(lot).value, "recommendation_id": rec.recommendation_id,
             "recommendation_version": rec.recommendation_version, "policy_version": rec.policy_version, **extra}
        self.journal.append(e)
        return e

    def _dedupe(self, fill_id: str) -> None:
        if fill_id in self._fills_seen:
            raise AttributionError(f"fill {fill_id} already applied")
        self._fills_seen.add(fill_id)

    # ---------------------------------------------------------------- opening
    def apply_open_fill(self, order_id: str, fill_id: str, symbol: str, side: str, qty: float, price: float,
                        at: datetime) -> PositionLot:
        rec = self.ledger.require(order_id)               # no origin, no fill
        if qty <= 0:
            raise AttributionError("fill quantity must be positive")
        self._dedupe(fill_id)
        lot = self.lots.get(order_id)
        if lot is None:
            lot = PositionLot(lot_id=order_id, symbol=symbol.upper(), side=side.upper(), opened_at=at,
                              recommendation_id=rec.recommendation_id)
            self.lots[order_id] = lot
        elif lot.symbol != symbol.upper() or lot.side != side.upper():
            raise AttributionError("fill does not match its order's lot")
        total = lot.quantity_open + qty
        lot.avg_entry_price = (lot.avg_entry_price * lot.quantity_open + price * qty) / total
        lot.quantity_open = total
        lot.quantity_opened += qty
        self._journal("open_fill", at, lot, order_id, fill_id=fill_id, quantity=qty, price=price)
        return lot

    # ---------------------------------------------------------------- closing
    def apply_close_fill(self, order_id: str, fill_id: str, qty: float, price: float, at: datetime,
                         lot_id: Optional[str] = None, symbol: Optional[str] = None) -> List[dict]:
        closing_origin = self.ledger.current(order_id)
        if qty <= 0:
            raise AttributionError("fill quantity must be positive")
        if lot_id is not None:
            lots = [self._lot(lot_id)]
        else:
            if not symbol:
                raise AttributionError("a close must name a lot or a symbol")
            lots = sorted((l for l in self.lots.values() if l.symbol == symbol.upper() and l.quantity_open > 0),
                          key=lambda l: l.opened_at)
            if len({(self.origin_of(l), l.recommendation_id) for l in lots}) > 1:
                raise AttributionError(
                    f"open {symbol} lots have different origins; choose the lot to close instead of guessing")
        if not lots or qty > sum(l.quantity_open for l in lots) + 1e-12:
            raise AttributionError("close quantity exceeds the open quantity")
        self._dedupe(fill_id)
        entries, remaining = [], qty
        for lot in lots:                                   # FIFO within lots that share one origin
            if remaining <= 1e-12:
                break
            take = min(remaining, lot.quantity_open)
            pnl = (price - lot.avg_entry_price) * take * (1 if lot.side == "BUY" else -1)
            lot.quantity_open -= take
            lot.realized_pnl += pnl
            remaining -= take
            lot.closes.append({"order_id": order_id, "fill_id": fill_id, "quantity": take, "price": price,
                               "realized_pnl": pnl, "at": at.isoformat()})
            entries.append(self._journal("final_close" if lot.is_closed else "partial_close", at, lot, order_id,
                                         fill_id=fill_id, quantity=take, price=price, realized_pnl=pnl,
                                         closing_order_origin=closing_origin.value))
        return entries

    def _lot(self, lot_id: str) -> PositionLot:
        lot = self.lots.get(lot_id)
        if lot is None:
            raise AttributionError(f"unknown lot {lot_id}")
        return lot
