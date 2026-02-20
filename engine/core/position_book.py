"""
PositionBook – Canonical Position Lifecycle Engine
Capital Strata Systems (CSS)

Purpose:
- Maintain authoritative open positions
- Track entry price, size, direction
- Compute realized + unrealized PnL
- Support partial closes
- Futures-ready design

Fail-safe: deterministic, no external side effects
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Position:
    instrument: str
    side: str            # "BUY" or "SELL"
    size: float          # position size (notional units)
    avg_entry_price: float
    realized_pnl: float = 0.0


# ============================================================
# POSITION BOOK
# ============================================================

class PositionBook:

    def __init__(self) -> None:
        self.positions: Dict[str, Position] = {}

    # ----------------------------------------------------------
    # OPEN OR INCREASE POSITION
    # ----------------------------------------------------------

    def open_or_increase(
        self,
        *,
        instrument: str,
        side: str,
        size: float,
        price: float,
    ) -> None:

        if size <= 0 or price <= 0:
            return

        existing = self.positions.get(instrument)

        if existing is None:
            self.positions[instrument] = Position(
                instrument=instrument,
                side=side,
                size=size,
                avg_entry_price=price,
            )
            return

        # If same direction, adjust weighted average entry
        if existing.side == side:
            total_size = existing.size + size
            weighted_price = (
                (existing.avg_entry_price * existing.size) +
                (price * size)
            ) / total_size

            existing.size = total_size
            existing.avg_entry_price = weighted_price
            return

        # Opposite direction => reduce or flip
        self._reduce_or_flip(
            instrument=instrument,
            incoming_side=side,
            size=size,
            price=price,
        )

    # ----------------------------------------------------------
    # REDUCE OR FLIP POSITION
    # ----------------------------------------------------------

    def _reduce_or_flip(
        self,
        *,
        instrument: str,
        incoming_side: str,
        size: float,
        price: float,
    ) -> None:

        existing = self.positions.get(instrument)
        if existing is None:
            return

        if size < existing.size:
            # Partial close
            pnl = self._calculate_pnl(
                side=existing.side,
                entry_price=existing.avg_entry_price,
                exit_price=price,
                size=size,
            )
            existing.size -= size
            existing.realized_pnl += pnl
            return

        if size == existing.size:
            # Full close
            pnl = self._calculate_pnl(
                side=existing.side,
                entry_price=existing.avg_entry_price,
                exit_price=price,
                size=size,
            )
            existing.realized_pnl += pnl
            del self.positions[instrument]
            return

        # Flip position
        close_size = existing.size
        pnl = self._calculate_pnl(
            side=existing.side,
            entry_price=existing.avg_entry_price,
            exit_price=price,
            size=close_size,
        )
        remaining = size - close_size

        del self.positions[instrument]

        self.positions[instrument] = Position(
            instrument=instrument,
            side=incoming_side,
            size=remaining,
            avg_entry_price=price,
            realized_pnl=pnl,
        )

    # ----------------------------------------------------------
    # CALCULATE PNL
    # ----------------------------------------------------------

    def _calculate_pnl(
        self,
        *,
        side: str,
        entry_price: float,
        exit_price: float,
        size: float,
    ) -> float:

        if side == "BUY":
            return (exit_price - entry_price) * size
        else:
            return (entry_price - exit_price) * size

    # ----------------------------------------------------------
    # UNREALIZED PNL SNAPSHOT
    # ----------------------------------------------------------

    def unrealized_snapshot(
        self,
        *,
        market_prices: Dict[str, float],
    ) -> Dict[str, float]:

        snapshot: Dict[str, float] = {}

        for inst, pos in self.positions.items():
            current_price = market_prices.get(inst)
            if current_price is None:
                continue

            pnl = self._calculate_pnl(
                side=pos.side,
                entry_price=pos.avg_entry_price,
                exit_price=current_price,
                size=pos.size,
            )

            snapshot[inst] = pnl

        return snapshot

    # ----------------------------------------------------------
    # POSITION SUMMARY
    # ----------------------------------------------------------

    def summary(self) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {}

        for inst, pos in self.positions.items():
            out[inst] = {
                "side": pos.side,
                "size": pos.size,
                "avg_entry_price": pos.avg_entry_price,
                "realized_pnl": pos.realized_pnl,
            }

        return out