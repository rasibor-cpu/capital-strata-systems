from __future__ import annotations

from typing import Dict, List, Any


def _safe(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


class PositionManager:
    """
    Enhanced Position Manager with Dynamic Exit Intelligence
    """

    def __init__(
        self,
        take_profit_pct: float = 0.018,
        stop_loss_pct: float = 0.010,
        max_hold_cycles: int = 5,
    ):
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.closed_positions: List[Dict[str, Any]] = []

        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_cycles = max_hold_cycles

    def has_open_position(self, symbol: str) -> bool:
        return symbol in self.open_positions

    def get_open_positions(self) -> Dict[str, Dict[str, Any]]:
        return self.open_positions

    def get_closed_positions(self) -> List[Dict[str, Any]]:
        return self.closed_positions

    def open_long_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        cycle_no: int,
        opened_at_utc: str,
    ):
        self.open_positions[symbol] = {
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": entry_price,
            "cycle_opened": cycle_no,
            "opened_at": opened_at_utc,
            "cycles_held": 0,
        }

    def update_positions(
        self,
        latest_prices: Dict[str, float],
        cycle_no: int,
        now: str,
    ) -> List[Dict[str, Any]]:
        closed: List[Dict[str, Any]] = []

        for symbol in list(self.open_positions.keys()):
            pos = self.open_positions[symbol]

            price = _safe(latest_prices.get(symbol), 0.0)
            entry = _safe(pos.get("entry_price"), 0.0)
            qty = _safe(pos.get("quantity"), 0.0)

            if price <= 0 or entry <= 0:
                continue

            pnl_pct = (price - entry) / entry
            pnl_usd = (price - entry) * qty

            pos["cycles_held"] += 1

            # === HARD EXITS (unchanged core safety) ===
            if pnl_pct >= self.take_profit_pct:
                reason = "TP"
            elif pnl_pct <= -self.stop_loss_pct:
                reason = "SL"

            else:
                # === DYNAMIC EXIT INTELLIGENCE ===

                cycles = pos["cycles_held"]

                # 🔥 1. EARLY PROFIT LOCK
                if pnl_pct > 0.004:  # ~0.4% profit
                    # If profit exists but not growing fast enough → lock it
                    if cycles >= 2:
                        reason = "EARLY_TP"
                    else:
                        reason = None

                # 🔥 2. SIGNAL DECAY (weak trades)
                elif pnl_pct < -0.002:  # small loss threshold
                    if cycles >= 2:
                        reason = "SIGNAL_DECAY"
                    else:
                        reason = None

                else:
                    reason = None

                # 🔥 3. MAX HOLD FALLBACK (only if no decision yet)
                if reason is None and cycles >= self.max_hold_cycles:
                    reason = "TIME"

            if reason:
                trade = {
                    "symbol": symbol,
                    "exit_price": price,
                    "entry_price": entry,
                    "quantity": qty,
                    "realized_pnl_usd": pnl_usd,
                    "exit_reason": reason,
                    "closed_at": now,
                    "cycle_closed": cycle_no,
                    "cycles_held": pos["cycles_held"],
                }

                closed.append(trade)
                self.closed_positions.append(trade)
                del self.open_positions[symbol]

        return closed