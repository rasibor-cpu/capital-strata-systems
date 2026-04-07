from __future__ import annotations

from typing import Dict, List
from datetime import datetime


class PositionManager:

    def __init__(self):
        self.positions: Dict[str, Dict] = {}
        self.closed_log: List[Dict] = []

    # =========================
    # CORE OPEN (NEW ENGINE)
    # =========================

    def open_position(
        self,
        *,
        symbol: str,
        entry_price: float,
        size: float,
        take_profit: float,
        stop_loss: float,
        side: str = "LONG",
        confidence: float = 0.0,
        regime: str = "UNKNOWN",
    ) -> None:

        if symbol in self.positions:
            return

        self.positions[symbol] = {
            "symbol": symbol,
            "entry_price": entry_price,
            "size": abs(size),
            "side": side,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "confidence": confidence,
            "regime": regime,
            "opened_at": datetime.utcnow(),
        }

    # =========================
    # BACKWARD COMPATIBILITY
    # =========================

    def open_long_position(self, **kwargs):
        self.open_position(side="LONG", **kwargs)

    def open_short_position(self, **kwargs):
        self.open_position(side="SHORT", **kwargs)

    # =========================
    # UPDATE
    # =========================

    def update_positions(self, market_prices: Dict[str, float]) -> None:

        to_close = []

        for symbol, pos in self.positions.items():

            if symbol not in market_prices:
                continue

            price = float(market_prices[symbol])
            side = pos["side"]

            if side == "LONG":
                if price >= pos["take_profit"]:
                    to_close.append((symbol, price, "TP"))
                elif price <= pos["stop_loss"]:
                    to_close.append((symbol, price, "SL"))

            elif side == "SHORT":
                if price <= pos["take_profit"]:
                    to_close.append((symbol, price, "TP"))
                elif price >= pos["stop_loss"]:
                    to_close.append((symbol, price, "SL"))

        for symbol, exit_price, reason in to_close:
            self.close_position(symbol, exit_price, reason)

    # =========================
    # CLOSE
    # =========================

    def close_position(self, symbol: str, exit_price: float, reason: str):

        if symbol not in self.positions:
            return

        pos = self.positions.pop(symbol)

        entry = pos["entry_price"]
        size = pos["size"]
        side = pos["side"]

        if side == "LONG":
            pnl = (exit_price - entry) * size
        else:
            pnl = (entry - exit_price) * size

        self.closed_log.append({
            "symbol": symbol,
            "entry_price": entry,
            "exit_price": exit_price,
            "size": size,
            "side": side,
            "pnl": pnl,
            "reason": reason,
            "confidence": pos["confidence"],
            "regime": pos["regime"],
            "opened_at": pos["opened_at"],
            "closed_at": datetime.utcnow(),
        })

    # =========================
    # GETTERS
    # =========================

    def get_open_positions(self) -> List[Dict]:
        return list(self.positions.values())

    def get_closed_positions(self) -> List[Dict]:
        return self.closed_log

    def get_total_pnl(self) -> float:
        return sum(t["pnl"] for t in self.closed_log)