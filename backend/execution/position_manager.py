from __future__ import annotations

from typing import Dict, List, Any, Optional


def _safe(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


class PositionManager:
    """
    Enhanced Position Manager with Dynamic Exit Intelligence
    and execution-cost-aware net PnL tracking.

    Notes:
    - Preserves original exit framework:
        TP / SL / EARLY_TP / SIGNAL_DECAY / TIME
    - Adds:
        gross vs net unrealized PnL
        entry + exit execution cost tracking
        asset_class tagging for downstream reporting
    - Backward-compatible:
        existing callers can keep using open_long_position(...)
        and update_positions(...) exactly as before.
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

    def _normalize_cost_payload(self, payload: Optional[Dict[str, Any]]) -> Dict[str, float]:
        """
        Normalize cost payload to a stable shape.

        Supported keys:
        - spread_cost_usd
        - slippage_cost_usd
        - fee_cost_usd
        - total_cost_usd

        If total_cost_usd is not provided, it is derived as:
            spread + slippage + fee
        """
        payload = payload or {}

        spread_cost_usd = _safe(payload.get("spread_cost_usd"), 0.0)
        slippage_cost_usd = _safe(payload.get("slippage_cost_usd"), 0.0)
        fee_cost_usd = _safe(payload.get("fee_cost_usd"), 0.0)

        explicit_total = payload.get("total_cost_usd")
        if explicit_total is None:
            total_cost_usd = spread_cost_usd + slippage_cost_usd + fee_cost_usd
        else:
            total_cost_usd = _safe(explicit_total, 0.0)

        return {
            "spread_cost_usd": spread_cost_usd,
            "slippage_cost_usd": slippage_cost_usd,
            "fee_cost_usd": fee_cost_usd,
            "total_cost_usd": total_cost_usd,
        }

    def open_long_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        cycle_no: int,
        opened_at_utc: str,
        asset_class: str = "unknown",
        entry_costs: Optional[Dict[str, Any]] = None,
    ):
        normalized_entry_costs = self._normalize_cost_payload(entry_costs)

        self.open_positions[symbol] = {
            "symbol": symbol,
            "asset_class": asset_class,
            "quantity": quantity,
            "entry_price": entry_price,
            "cycle_opened": cycle_no,
            "opened_at": opened_at_utc,
            "cycles_held": 0,
            # Execution cost baseline captured at entry
            "entry_spread_cost_usd": normalized_entry_costs["spread_cost_usd"],
            "entry_slippage_cost_usd": normalized_entry_costs["slippage_cost_usd"],
            "entry_fee_cost_usd": normalized_entry_costs["fee_cost_usd"],
            "entry_total_cost_usd": normalized_entry_costs["total_cost_usd"],
            # Live tracking fields initialized
            "last_price": entry_price,
            "gross_unrealized_pnl_usd": 0.0,
            "net_unrealized_pnl_usd": -normalized_entry_costs["total_cost_usd"],
            "gross_unrealized_pnl_pct": 0.0,
            "net_unrealized_pnl_pct": 0.0,
            "estimated_total_round_trip_cost_usd": normalized_entry_costs["total_cost_usd"],
        }

    def update_positions(
        self,
        latest_prices: Dict[str, float],
        cycle_no: int,
        now: str,
        exit_costs_by_symbol: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Update open positions using latest prices and optionally symbol-level exit cost estimates.

        exit_costs_by_symbol example:
        {
            "EURUSD": {
                "spread_cost_usd": 0.40,
                "slippage_cost_usd": 0.15,
                "fee_cost_usd": 0.05
            },
            "BTC-USD": {
                "total_cost_usd": 1.25
            }
        }

        Backward compatibility:
        - Existing callers may omit exit_costs_by_symbol entirely.
        """
        closed: List[Dict[str, Any]] = []
        exit_costs_by_symbol = exit_costs_by_symbol or {}

        for symbol in list(self.open_positions.keys()):
            pos = self.open_positions[symbol]

            price = _safe(latest_prices.get(symbol), 0.0)
            entry = _safe(pos.get("entry_price"), 0.0)
            qty = _safe(pos.get("quantity"), 0.0)

            if price <= 0 or entry <= 0 or qty <= 0:
                continue

            entry_total_cost_usd = _safe(pos.get("entry_total_cost_usd"), 0.0)

            normalized_exit_costs = self._normalize_cost_payload(
                exit_costs_by_symbol.get(symbol)
            )
            exit_total_cost_usd = normalized_exit_costs["total_cost_usd"]

            gross_pnl_pct = (price - entry) / entry
            gross_pnl_usd = (price - entry) * qty

            net_pnl_usd = gross_pnl_usd - entry_total_cost_usd - exit_total_cost_usd
            notional_usd = entry * qty
            net_pnl_pct = (net_pnl_usd / notional_usd) if notional_usd > 0 else 0.0

            pos["cycles_held"] += 1
            pos["last_price"] = price

            # Live gross/net tracking for dashboard and risk visibility
            pos["gross_unrealized_pnl_usd"] = gross_pnl_usd
            pos["net_unrealized_pnl_usd"] = net_pnl_usd
            pos["gross_unrealized_pnl_pct"] = gross_pnl_pct
            pos["net_unrealized_pnl_pct"] = net_pnl_pct

            pos["estimated_exit_spread_cost_usd"] = normalized_exit_costs["spread_cost_usd"]
            pos["estimated_exit_slippage_cost_usd"] = normalized_exit_costs["slippage_cost_usd"]
            pos["estimated_exit_fee_cost_usd"] = normalized_exit_costs["fee_cost_usd"]
            pos["estimated_exit_total_cost_usd"] = exit_total_cost_usd
            pos["estimated_total_round_trip_cost_usd"] = entry_total_cost_usd + exit_total_cost_usd

            # === HARD EXITS (preserved, now using gross trade movement for original behavior) ===
            if gross_pnl_pct >= self.take_profit_pct:
                reason = "TP"
            elif gross_pnl_pct <= -self.stop_loss_pct:
                reason = "SL"

            else:
                # === DYNAMIC EXIT INTELLIGENCE ===
                cycles = pos["cycles_held"]

                # 1. EARLY PROFIT LOCK
                if gross_pnl_pct > 0.004:  # ~0.4% profit
                    if cycles >= 2:
                        reason = "EARLY_TP"
                    else:
                        reason = None

                # 2. SIGNAL DECAY (weak trades)
                elif gross_pnl_pct < -0.002:  # small loss threshold
                    if cycles >= 2:
                        reason = "SIGNAL_DECAY"
                    else:
                        reason = None

                else:
                    reason = None

                # 3. MAX HOLD FALLBACK
                if reason is None and cycles >= self.max_hold_cycles:
                    reason = "TIME"

            if reason:
                trade = {
                    "symbol": symbol,
                    "asset_class": pos.get("asset_class", "unknown"),
                    "exit_price": price,
                    "entry_price": entry,
                    "quantity": qty,
                    "gross_realized_pnl_usd": gross_pnl_usd,
                    "realized_pnl_usd": net_pnl_usd,
                    "net_realized_pnl_usd": net_pnl_usd,
                    "gross_realized_pnl_pct": gross_pnl_pct,
                    "net_realized_pnl_pct": net_pnl_pct,
                    "entry_spread_cost_usd": _safe(pos.get("entry_spread_cost_usd"), 0.0),
                    "entry_slippage_cost_usd": _safe(pos.get("entry_slippage_cost_usd"), 0.0),
                    "entry_fee_cost_usd": _safe(pos.get("entry_fee_cost_usd"), 0.0),
                    "entry_total_cost_usd": entry_total_cost_usd,
                    "exit_spread_cost_usd": normalized_exit_costs["spread_cost_usd"],
                    "exit_slippage_cost_usd": normalized_exit_costs["slippage_cost_usd"],
                    "exit_fee_cost_usd": normalized_exit_costs["fee_cost_usd"],
                    "exit_total_cost_usd": exit_total_cost_usd,
                    "total_round_trip_cost_usd": entry_total_cost_usd + exit_total_cost_usd,
                    "exit_reason": reason,
                    "closed_at": now,
                    "cycle_closed": cycle_no,
                    "cycles_held": pos["cycles_held"],
                }

                closed.append(trade)
                self.closed_positions.append(trade)
                del self.open_positions[symbol]

        return closed