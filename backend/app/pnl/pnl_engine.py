from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


# =========================
# EXECUTION COST MODEL
# =========================
@dataclass
class ExecutionCost:
    spread: float = 0.0
    slippage: float = 0.0
    fees: float = 0.0

    @property
    def total(self) -> float:
        return self.spread + self.slippage + self.fees


# =========================
# POSITION MODEL
# =========================
@dataclass
class Position:
    symbol: str
    asset_class: str  # CRYPTO | FX | FUTURES | OPTIONS
    side: str         # LONG | SHORT
    quantity: float
    entry_price: float

    current_price: float = 0.0
    exit_price: float = None
    status: str = "OPEN"

    costs: ExecutionCost = field(default_factory=ExecutionCost)

    def raw_pnl(self) -> float:
        if self.side == "LONG":
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity

    def net_pnl(self) -> float:
        return self.raw_pnl() - self.costs.total


# =========================
# PORTFOLIO MODEL
# =========================
@dataclass
class Portfolio:
    starting_balance: float = 0.0
    current_balance: float = 0.0

    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    open_positions: List[Position] = field(default_factory=list)
    closed_positions: List[Position] = field(default_factory=list)

    # ---------------------
    # Add position
    # ---------------------
    def add_position(self, position: Position):
        self.open_positions.append(position)

    # ---------------------
    # Update price
    # ---------------------
    def update_market_price(self, symbol: str, price: float):
        for pos in self.open_positions:
            if pos.symbol == symbol and pos.status == "OPEN":
                pos.current_price = price

    # ---------------------
    # Compute unrealized
    # ---------------------
    def compute_unrealized_pnl(self) -> float:
        total = 0.0
        for pos in self.open_positions:
            if pos.status == "OPEN":
                total += pos.net_pnl()

        self.unrealized_pnl = total
        return total

    # ---------------------
    # Close position
    # ---------------------
    def close_position(self, symbol: str, exit_price: float):
        for pos in self.open_positions:
            if pos.symbol == symbol and pos.status == "OPEN":

                pos.exit_price = exit_price
                pos.current_price = exit_price
                pos.status = "CLOSED"

                pnl = pos.net_pnl()

                # Move to realized
                self.realized_pnl += pnl
                self.current_balance += pnl

                self.closed_positions.append(pos)

        # Clean open positions
        self.open_positions = [
            p for p in self.open_positions if p.status == "OPEN"
        ]

    # ---------------------
    # Equity
    # ---------------------
    def equity(self) -> float:
        return self.current_balance + self.unrealized_pnl