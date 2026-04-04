from __future__ import annotations

from typing import Dict, List


class PositionManager:

    def __init__(self):
        self.positions: Dict[str, Dict] = {}
        self.closed_log: List[Dict] = []

    # =========================
    # OPEN
    # =========================

    def open_long_position(
        self,
        *,
        symbol: str,
        quantity: float,
        entry_price: float,
        cycle_no: int,
        opened_at_utc: str,
        asset_class: str,
        **kwargs,
    ):
        self.positions[symbol] = {
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": entry_price,
            "status": "OPEN",
            "peak_price": entry_price,
        }

    # =========================

    def has_open_position(self, symbol: str) -> bool:
        return symbol in self.positions and self.positions[symbol]["status"] == "OPEN"

    # =========================
    # EXIT ENGINE
    # =========================

    def update_positions(
        self,
        *,
        latest_prices: Dict[str, float],
        cycle_no: int,
        now: str,
        intelligence_by_symbol: Dict[str, Dict],
    ) -> List[Dict]:

        closed = []

        for sym, pos in list(self.positions.items()):

            if pos["status"] != "OPEN":
                continue

            price = latest_prices.get(sym)
            if not price:
                continue

            entry = pos["entry_price"]
            pnl = (price - entry) / entry

            # track peak
            if price > pos["peak_price"]:
                pos["peak_price"] = price

            peak = pos["peak_price"]
            drawdown = (price - peak) / peak if peak else 0

            intel = intelligence_by_symbol.get(sym, {})
            pressure = float(intel.get("pressure_score", 0))
            accel = float(intel.get("pressure_acceleration", 0))

            reason = None

            # 🔴 STOP LOSS
            if pnl <= -0.012:
                reason = "STOP_LOSS"

            # 🟢 TRAILING LOCK (tightened slightly)
            elif pnl > 0.008 and drawdown < -0.003:
                reason = "TRAIL_LOCK"

            # ⚠️ PRESSURE FADE
            elif pnl > 0 and pressure < 0.18:
                reason = "PRESSURE_FADE"

            # ⚠️ MOMENTUM REVERSAL
            elif pnl > 0 and accel < -0.08:
                reason = "ACCEL_REVERSAL"

            # 💰 TAKE PROFIT
            elif pnl > 0.02:
                reason = "TAKE_PROFIT"

            if reason:
                pos["status"] = "CLOSED"
                pos["exit_price"] = price
                pos["pnl"] = pnl

                record = {
                    "symbol": sym,
                    "exit_reason": reason,
                    "net_realized_pnl_pct": pnl,
                }

                closed.append(record)
                self.closed_log.append(record)

                print(f"[CLOSE] {sym} reason={reason} pnl={round(pnl*100,2)}%")

                del self.positions[sym]

        return closed

    # =========================

    def summary(self):
        return {
            "open_positions_count": len(self.positions),
            "closed_positions_count": len(self.closed_log),
            "net_realized_pnl_usd": 0.0,
        }