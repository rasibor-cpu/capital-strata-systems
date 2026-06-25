from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Position:
    symbol: str
    asset_class: str
    side: str
    quantity: float
    entry_price: float
    current_price: float | None = None


class Portfolio:
    """Backward-compatible lightweight portfolio API used by legacy pnl tests."""

    def __init__(self, *, starting_balance: float, current_balance: float | None = None) -> None:
        self.starting_balance = float(starting_balance)
        self.current_balance = float(current_balance if current_balance is not None else starting_balance)
        self.realized_pnl = 0.0
        self._positions: dict[str, Position] = {}

    def add_position(self, position: Position) -> None:
        if not isinstance(position, Position):
            raise TypeError("position must be Position")
        if position.current_price is None:
            position.current_price = float(position.entry_price)
        self._positions[position.symbol] = position

    def update_market_price(self, symbol: str, price: float) -> None:
        if symbol in self._positions:
            self._positions[symbol].current_price = float(price)

    def compute_unrealized_pnl(self) -> float:
        total = 0.0
        for position in self._positions.values():
            direction = 1.0 if str(position.side).strip().upper() == "LONG" else -1.0
            total += direction * (float(position.current_price or position.entry_price) - float(position.entry_price)) * float(position.quantity)
        return total

    def close_position(self, symbol: str, exit_price: float) -> float:
        position = self._positions.pop(symbol)
        direction = 1.0 if str(position.side).strip().upper() == "LONG" else -1.0
        pnl = direction * (float(exit_price) - float(position.entry_price)) * float(position.quantity)
        self.realized_pnl += pnl
        self.current_balance += pnl
        return pnl
