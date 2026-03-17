from __future__ import annotations

from typing import Dict, List, Any


class PositionManager:
    """
    CSS Position Manager (stable + compatible)

    Features:
    - supports multiple call signatures
    - enforces max open positions
    - handles TP / SL exits
    - tracks PnL
    """

    def __init__(
        self,
        take_profit_pct: float = 0.018,
        stop_loss_pct: float = 0.010,
        max_hold_cycles: int = 5,
    ):

        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_cycles = max_hold_cycles

        # 🔥 FIXED (no comma, no syntax error)
        self.max_open_positions = 4

        self.positions: Dict[str, Dict[str, Any]] = {}

    # ---------------------------------------------------------
    # OPEN POSITION
    # ---------------------------------------------------------

    def open_long_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        cycle_no: int | None = None,
        opened_at_utc: str | None = None,
    ) -> None:

        if symbol in self.positions:
            return

        if len(self.positions) >= self.max_open_positions:
            return

        self.positions[symbol] = {
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": entry_price,
            "cycle_opened": cycle_no,
            "opened_at": opened_at_utc,
            "cycles_held": 0,
        }

    # compatibility alias
    def open_position(self, symbol: str, quantity: float, entry_price: float, **kwargs):
        self.open_long_position(symbol, quantity, entry_price, **kwargs)

    # ---------------------------------------------------------
    # UPDATE POSITIONS
    # ---------------------------------------------------------

    def update_positions(
        self,
        latest_prices: Dict[str, float] | None = None,
        cycle_no: int | None = None,
        now: str | None = None,
    ) -> List[Dict[str, Any]]:

        closed_positions: List[Dict[str, Any]] = []

        if latest_prices is None:
            latest_prices = {}

        for symbol in list(self.positions.keys()):

            pos = self.positions[symbol]

            price = latest_prices.get(symbol)

            if price is None or price <= 0:
                continue

            entry = pos["entry_price"]
            qty = pos["quantity"]

            pnl_pct = (price - entry) / entry

            pos["cycles_held"] += 1

            exit_reason = None

            # ---- TAKE PROFIT ----
            if pnl_pct >= self.take_profit_pct:
                exit_reason = "TP"

            # ---- STOP LOSS ----
            elif pnl_pct <= -self.stop_loss_pct:
                exit_reason = "SL"

            # ---- TIME EXIT ----
            elif pos["cycles_held"] >= self.max_hold_cycles:
                exit_reason = "TIME"

            if exit_reason:

                realized_pnl = (price - entry) * qty

                closed_positions.append(
                    {
                        "symbol": symbol,
                        "exit_price": price,
                        "entry_price": entry,
                        "quantity": qty,
                        "realized_pnl_usd": realized_pnl,
                        "exit_reason": exit_reason,
                        "closed_at": now,
                    }
                )

                del self.positions[symbol]

        return closed_positions

    # ---------------------------------------------------------
    # UTILITIES
    # ---------------------------------------------------------

    def get_open_positions(self) -> Dict[str, Dict[str, Any]]:
        return self.positions

    def has_open_position(self, symbol: str) -> bool:
        return symbol in self.positions