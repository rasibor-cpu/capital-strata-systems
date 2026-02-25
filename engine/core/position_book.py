"""
PositionBook v2 – Institutional Position Lifecycle Engine
Capital Strata Systems (CSS)

Features:
- Multi-bar hold
- Stop-loss enforcement
- Take-profit support
- Max-hold time stop
- Opposite-signal exit
- Deterministic & side-effect free
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


# ============================================================
# POSITION STRUCTURE
# ============================================================

@dataclass
class Position:
    instrument: str
    side: str                      # "BUY" | "SELL"
    size: float
    entry_price: float
    opened_step: int
    stop_distance_pct: float
    take_profit_pct: Optional[float]
    max_hold_steps: int
    realized_pnl: float = 0.0


# ============================================================
# POSITION BOOK
# ============================================================

class PositionBook:

    def __init__(self) -> None:
        self.positions: Dict[str, Position] = {}

    # ----------------------------------------------------------
    # OPEN POSITION
    # ----------------------------------------------------------

    def open_position(
        self,
        *,
        instrument: str,
        side: str,
        size: float,
        price: float,
        step: int,
        stop_distance_pct: float = 0.01,
        take_profit_pct: Optional[float] = 0.02,
        max_hold_steps: int = 50,
    ) -> None:

        if instrument in self.positions:
            return  # Already open — no pyramiding for now

        self.positions[instrument] = Position(
            instrument=instrument,
            side=side,
            size=size,
            entry_price=price,
            opened_step=step,
            stop_distance_pct=stop_distance_pct,
            take_profit_pct=take_profit_pct,
            max_hold_steps=max_hold_steps,
        )

    # ----------------------------------------------------------
    # EVALUATE EXIT CONDITIONS
    # ----------------------------------------------------------

    def evaluate_exit(
        self,
        *,
        instrument: str,
        current_price: float,
        current_step: int,
        incoming_signal: Optional[str] = None,
    ) -> float:
        """
        Returns realized pnl if position closed.
        Returns 0.0 if still open.
        """

        pos = self.positions.get(instrument)
        if pos is None:
            return 0.0

        # Calculate pnl helper
        def calc_pnl(exit_price: float) -> float:
            if pos.side == "BUY":
                return (exit_price - pos.entry_price) * pos.size
            else:
                return (pos.entry_price - exit_price) * pos.size

        # 1) Stop Loss
        stop_level = (
            pos.entry_price * (1 - pos.stop_distance_pct)
            if pos.side == "BUY"
            else pos.entry_price * (1 + pos.stop_distance_pct)
        )

        if (pos.side == "BUY" and current_price <= stop_level) or (
            pos.side == "SELL" and current_price >= stop_level
        ):
            pnl = calc_pnl(current_price)
            del self.positions[instrument]
            return pnl

        # 2) Take Profit
        if pos.take_profit_pct is not None:
            tp_level = (
                pos.entry_price * (1 + pos.take_profit_pct)
                if pos.side == "BUY"
                else pos.entry_price * (1 - pos.take_profit_pct)
            )

            if (pos.side == "BUY" and current_price >= tp_level) or (
                pos.side == "SELL" and current_price <= tp_level
            ):
                pnl = calc_pnl(current_price)
                del self.positions[instrument]
                return pnl

        # 3) Opposite Signal Exit
        if incoming_signal and incoming_signal != pos.side:
            pnl = calc_pnl(current_price)
            del self.positions[instrument]
            return pnl

        # 4) Max Hold Exit
        if current_step - pos.opened_step >= pos.max_hold_steps:
            pnl = calc_pnl(current_price)
            del self.positions[instrument]
            return pnl

        return 0.0

    # ----------------------------------------------------------
    # CHECK IF POSITION EXISTS
    # ----------------------------------------------------------

    def has_position(self, instrument: str) -> bool:
        return instrument in self.positions

    # ----------------------------------------------------------
    # SUMMARY
    # ----------------------------------------------------------

    def summary(self) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {}
        for inst, pos in self.positions.items():
            out[inst] = {
                "side": pos.side,
                "size": pos.size,
                "entry_price": pos.entry_price,
                "opened_step": pos.opened_step,
            }
        return out