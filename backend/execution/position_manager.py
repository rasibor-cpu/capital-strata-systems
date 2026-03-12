from __future__ import annotations

from typing import Dict, Any


class PositionManager:
    """
    CSS Position Manager

    Tracks open trades so the engine:
    - does not duplicate entries
    - can monitor TP / SL
    - can reduce positions partially
    - can update stops dynamically
    """

    def __init__(self) -> None:
        self.open_positions: Dict[str, Dict[str, Any]] = {}

    def has_position(self, symbol: str) -> bool:
        return symbol in self.open_positions

    def open_position(
        self,
        symbol: str,
        entry_price: float,
        size: float,
        take_profit_pct: float,
        stop_loss_pct: float,
    ) -> None:
        tp_price = entry_price * (1 + take_profit_pct)
        sl_price = entry_price * (1 - stop_loss_pct)

        self.open_positions[symbol] = {
            "entry_price": entry_price,
            "size": size,
            "remaining_size": size,
            "take_profit": tp_price,
            "stop_loss": sl_price,
        }

        print(
            f"POSITION OPENED: {symbol} | "
            f"entry={entry_price:.6f} | "
            f"tp={tp_price:.6f} | "
            f"sl={sl_price:.6f}"
        )

    def update_stop(self, symbol: str, new_stop: float) -> None:
        if symbol not in self.open_positions:
            return

        pos = self.open_positions[symbol]
        old_stop = float(pos.get("stop_loss", 0.0))

        if new_stop > old_stop:
            pos["stop_loss"] = new_stop
            print(
                f"STOP UPDATED: {symbol} | "
                f"old_stop={old_stop:.6f} | "
                f"new_stop={new_stop:.6f}"
            )

    def reduce_position(
        self,
        symbol: str,
        exit_price: float,
        size_reduction: float,
        reason: str = "",
    ) -> float:
        """
        Reduce an open position by size_reduction and return realized pnl.
        """
        if symbol not in self.open_positions:
            return 0.0

        pos = self.open_positions[symbol]

        entry = float(pos["entry_price"])
        remaining = float(pos.get("remaining_size", pos.get("size", 0.0)))
        reduce_amt = max(0.0, min(float(size_reduction), remaining))

        if reduce_amt <= 0:
            return 0.0

        pnl = (exit_price - entry) * reduce_amt
        pos["remaining_size"] = remaining - reduce_amt

        print(
            f"POSITION REDUCED: {symbol} | "
            f"reduced={reduce_amt:.8f} | "
            f"remaining={pos['remaining_size']:.8f} | "
            f"exit={exit_price:.6f} | "
            f"PNL={pnl:.4f} | "
            f"reason={reason}"
        )

        return pnl

    def close_position(self, symbol: str, exit_price: float, reason: str = "") -> float:
        if symbol not in self.open_positions:
            return 0.0

        pos = self.open_positions[symbol]

        entry = float(pos["entry_price"])
        remaining = float(pos.get("remaining_size", pos.get("size", 0.0)))

        pnl = (exit_price - entry) * remaining

        print(
            f"POSITION CLOSED: {symbol} | "
            f"entry={entry:.6f} | "
            f"exit={exit_price:.6f} | "
            f"remaining={remaining:.8f} | "
            f"PNL={pnl:.4f} | "
            f"reason={reason}"
        )

        del self.open_positions[symbol]
        return pnl

    def check_exit(self, symbol: str, price: float) -> bool:
        if symbol not in self.open_positions:
            return False

        pos = self.open_positions[symbol]

        if price >= float(pos["take_profit"]):
            print(f"TAKE PROFIT HIT: {symbol}")
            return True

        if price <= float(pos["stop_loss"]):
            print(f"STOP LOSS HIT: {symbol}")
            return True

        return False