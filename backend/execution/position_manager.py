from __future__ import annotations

from typing import Dict, List, Any, Optional

from backend.trading.profit_capture_engine import ProfitCaptureEngine


def _safe(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


class PositionManager:
    """
    Enhanced Position Manager with:

    - Cost-aware gross/net PnL tracking
    - Backward-compatible update_positions signature
    - Original dynamic exit framework preserved
    - Profit engine integration (peak + trailing logic)
    - Regime / momentum / tier-aware exit modulation
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

        self.profit_engine = ProfitCaptureEngine(
            take_profit_bps=250.0,
            stop_loss_bps=120.0,
            trail_trigger_bps=40.0,
            locked_profit_bps=15.0,
        )

    def has_open_position(self, symbol: str) -> bool:
        return symbol in self.open_positions

    def get_open_positions(self) -> Dict[str, Dict[str, Any]]:
        return self.open_positions

    def get_closed_positions(self) -> List[Dict[str, Any]]:
        return self.closed_positions

    def summary(self) -> Dict[str, Any]:
        gross_closed = sum(_safe(t.get("gross_realized_pnl_usd"), 0.0) for t in self.closed_positions)
        net_closed = sum(_safe(t.get("net_realized_pnl_usd"), _safe(t.get("realized_pnl_usd"), 0.0)) for t in self.closed_positions)

        wins = 0
        losses = 0
        for t in self.closed_positions:
            pnl = _safe(t.get("net_realized_pnl_usd"), _safe(t.get("realized_pnl_usd"), 0.0))
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1

        return {
            "open_positions_count": len(self.open_positions),
            "closed_positions_count": len(self.closed_positions),
            "gross_realized_pnl_usd": round(gross_closed, 6),
            "net_realized_pnl_usd": round(net_closed, 6),
            "wins": wins,
            "losses": losses,
        }

    def _normalize_cost_payload(self, payload: Optional[Dict[str, Any]]) -> Dict[str, float]:
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
        regime: str = "NEUTRAL",
        pressure_score: float = 0.0,
        acceleration_score: float = 0.0,
        signal_tier: str = "WATCH",
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
            "peak_price": entry_price,
            "regime": str(regime).upper(),
            "pressure_score": _safe(pressure_score, 0.0),
            "acceleration_score": _safe(acceleration_score, 0.0),
            "signal_tier": str(signal_tier).upper(),
            "entry_spread_cost_usd": normalized_entry_costs["spread_cost_usd"],
            "entry_slippage_cost_usd": normalized_entry_costs["slippage_cost_usd"],
            "entry_fee_cost_usd": normalized_entry_costs["fee_cost_usd"],
            "entry_total_cost_usd": normalized_entry_costs["total_cost_usd"],
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
        now: Optional[str] = None,
        timestamp_utc: Optional[str] = None,
        exit_costs_by_symbol: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Backward compatible:
        - callers may pass now=...
        - older callers may pass timestamp_utc=...
        """
        if now is None:
            now = timestamp_utc or ""

        closed: List[Dict[str, Any]] = []
        exit_costs_by_symbol = exit_costs_by_symbol or {}

        for symbol in list(self.open_positions.keys()):
            pos = self.open_positions[symbol]

            price = _safe(latest_prices.get(symbol), 0.0)
            entry = _safe(pos.get("entry_price"), 0.0)
            qty = _safe(pos.get("quantity"), 0.0)

            if price <= 0 or entry <= 0 or qty <= 0:
                continue

            peak_price = _safe(pos.get("peak_price"), entry)
            if price > peak_price:
                peak_price = price
                pos["peak_price"] = peak_price

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
            pos["gross_unrealized_pnl_usd"] = gross_pnl_usd
            pos["net_unrealized_pnl_usd"] = net_pnl_usd
            pos["gross_unrealized_pnl_pct"] = gross_pnl_pct
            pos["net_unrealized_pnl_pct"] = net_pnl_pct
            pos["estimated_exit_spread_cost_usd"] = normalized_exit_costs["spread_cost_usd"]
            pos["estimated_exit_slippage_cost_usd"] = normalized_exit_costs["slippage_cost_usd"]
            pos["estimated_exit_fee_cost_usd"] = normalized_exit_costs["fee_cost_usd"]
            pos["estimated_exit_total_cost_usd"] = exit_total_cost_usd
            pos["estimated_total_round_trip_cost_usd"] = entry_total_cost_usd + exit_total_cost_usd

            regime = str(pos.get("regime", "NEUTRAL")).upper()
            pressure = _safe(pos.get("pressure_score"), 0.0)
            accel = _safe(pos.get("acceleration_score"), 0.0)
            tier = str(pos.get("signal_tier", "WATCH")).upper()

            profit_decision = self.profit_engine.evaluate(
                entry_price=entry,
                current_price=price,
                peak_price=peak_price,
            )
            action = profit_decision.get("action")

            hold_bias = 0

            if regime == "TREND":
                hold_bias += 1
            elif regime == "BREAKOUT":
                hold_bias += 2
            elif regime == "MEAN_REVERSION":
                hold_bias -= 1

            if pressure > 0.5:
                hold_bias += 1
            if accel > 0.3:
                hold_bias += 1

            if tier == "ELITE":
                hold_bias += 2
            elif tier == "QUALIFIED":
                hold_bias += 1

            if action == "STOP_LOSS":
                reason = "SL"

            elif action == "EXIT_LOCK_PROFIT":
                if hold_bias >= 2:
                    reason = None
                else:
                    reason = "TRAILING_LOCK"

            elif action == "TAKE_PROFIT":
                if hold_bias >= 3:
                    reason = None
                else:
                    reason = "TP"

            else:
                reason = None

            if reason is None:
                if gross_pnl_pct >= self.take_profit_pct:
                    if hold_bias >= 3:
                        reason = None
                    else:
                        reason = "TP"

                elif gross_pnl_pct <= -self.stop_loss_pct:
                    reason = "SL"

                else:
                    cycles = pos["cycles_held"]

                    if gross_pnl_pct > 0.004:
                        if cycles >= 2 and hold_bias <= 1:
                            reason = "EARLY_TP"
                        else:
                            reason = None

                    elif gross_pnl_pct < -0.002:
                        if cycles >= 2:
                            reason = "SIGNAL_DECAY"
                        else:
                            reason = None

                    else:
                        reason = None

                    if reason is None and cycles >= self.max_hold_cycles:
                        if hold_bias >= 2:
                            reason = None
                        else:
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
                    "regime": regime,
                    "pressure_score": pressure,
                    "acceleration_score": accel,
                    "signal_tier": tier,
                }

                closed.append(trade)
                self.closed_positions.append(trade)
                del self.open_positions[symbol]

        return closed