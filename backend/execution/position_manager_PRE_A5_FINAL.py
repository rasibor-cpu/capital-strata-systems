from __future__ import annotations

from typing import Dict, List
from datetime import datetime, timezone


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PositionManager:

    DEFAULT_TRAIL_TRIGGER_PCT = 0.015
    DEFAULT_TRAIL_STOP_PCT = 0.0075

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

        side = str(side).upper().strip()
        if side not in {"LONG", "SHORT"}:
            side = "LONG"

        self.positions[symbol] = {
            "symbol": symbol,
            "entry_price": float(entry_price),
            "size": abs(float(size)),
            "side": side,
            "take_profit": float(take_profit),
            "stop_loss": float(stop_loss),
            "confidence": float(confidence),
            "regime": regime,
            "opened_at": _utc_now(),

            # trailing engine fields
            "peak_price_seen": float(entry_price),
            "trailing_active": False,
            "trail_trigger_pct": self.DEFAULT_TRAIL_TRIGGER_PCT,
            "trail_stop_pct": self.DEFAULT_TRAIL_STOP_PCT,

            # runtime tracking
            "current_price": float(entry_price),
            "unrealized_pnl": 0.0,
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
            entry_price = float(pos["entry_price"])

            pos["current_price"] = price
            pos["unrealized_pnl"] = self._compute_pnl(
                side=side,
                entry=entry_price,
                exit_price=price,
                size=float(pos["size"]),
            )

            # ---------------------------
            # Peak favorable excursion
            # ---------------------------
            if side == "LONG":
                pos["peak_price_seen"] = max(
                    float(pos["peak_price_seen"]),
                    price
                )
            else:
                pos["peak_price_seen"] = min(
                    float(pos["peak_price_seen"]),
                    price
                )

            # ---------------------------
            # Stop loss always active
            # ---------------------------
            if side == "LONG":
                if price <= pos["stop_loss"]:
                    to_close.append((symbol, price, "SL"))
                    continue

            elif side == "SHORT":
                if price >= pos["stop_loss"]:
                    to_close.append((symbol, price, "SL"))
                    continue

            # ---------------------------
            # Activate trailing
            # ---------------------------
            if not pos["trailing_active"]:
                if self._trail_trigger_hit(pos, price):
                    pos["trailing_active"] = True

            # ---------------------------
            # Trailing exit
            # ---------------------------
            if pos["trailing_active"]:
                if self._trail_exit_hit(pos, price):
                    to_close.append((symbol, price, "TRAIL_TP"))
                    continue

            # ---------------------------
            # Legacy TP fallback
            # ---------------------------
            if not pos["trailing_active"]:
                if side == "LONG":
                    if price >= pos["take_profit"]:
                        pos["trailing_active"] = True
                elif side == "SHORT":
                    if price <= pos["take_profit"]:
                        pos["trailing_active"] = True

        for symbol, exit_price, reason in to_close:
            self.close_position(symbol, exit_price, reason)


    def refresh_positions_from_loader(self, price_loader) -> None:
        """
        A5 PCNRASS SAFE:
        Refreshes current_price and unrealized_pnl for all open positions using
        an external price loader. Does not alter entry_price, size, side,
        take_profit, stop_loss, confidence, regime, or close positions directly.
        """
        market_prices = {}

        for symbol in list(self.positions.keys()):
            try:
                data = price_loader(symbol)
                if isinstance(data, dict):
                    price = (
                        data.get("price")
                        or data.get("close")
                        or data.get("current_price")
                    )
                else:
                    price = data

                if price is not None:
                    market_prices[symbol] = float(price)
            except Exception:
                continue

        if market_prices:
            self.update_positions(market_prices)


    # =========================
    # CLOSE
    # =========================

    def close_position(self, symbol: str, exit_price: float, reason: str):

        if symbol not in self.positions:
            return

        pos = self.positions.pop(symbol)

        entry = float(pos["entry_price"])
        size = float(pos["size"])
        side = pos["side"]

        pnl = self._compute_pnl(
            side=side,
            entry=entry,
            exit_price=float(exit_price),
            size=size,
        )

        self.closed_log.append({
            "symbol": symbol,
            "entry_price": entry,
            "exit_price": float(exit_price),
            "size": size,
            "side": side,
            "pnl": pnl,
            "reason": reason,
            "confidence": pos["confidence"],
            "regime": pos["regime"],
            "opened_at": pos["opened_at"],
            "closed_at": _utc_now(),
        })

    # =========================
    # HELPERS
    # =========================

    def _compute_pnl(
        self,
        *,
        side: str,
        entry: float,
        exit_price: float,
        size: float,
    ) -> float:
        if side == "SHORT":
            return (entry - exit_price) * size
        return (exit_price - entry) * size

    def _trail_trigger_hit(self, pos: Dict, price: float) -> bool:
        entry = float(pos["entry_price"])
        trigger_pct = float(pos["trail_trigger_pct"])
        side = pos["side"]

        if side == "LONG":
            return price >= entry * (1.0 + trigger_pct)
        else:
            return price <= entry * (1.0 - trigger_pct)

    def _trail_exit_hit(self, pos: Dict, price: float) -> bool:
        peak = float(pos["peak_price_seen"])
        trail_pct = float(pos["trail_stop_pct"])
        side = pos["side"]

        if side == "LONG":
            trail_level = peak * (1.0 - trail_pct)
            return price <= trail_level
        else:
            trail_level = peak * (1.0 + trail_pct)
            return price >= trail_level

    # =========================
    # GETTERS
    # =========================

    def get_open_positions(self) -> List[Dict]:
        return list(self.positions.values())

    def get_closed_positions(self) -> List[Dict]:
        return self.closed_log

    def get_total_pnl(self) -> float:
        return sum(t["pnl"] for t in self.closed_log)
