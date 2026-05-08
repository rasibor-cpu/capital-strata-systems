from __future__ import annotations

from typing import Any, Dict, List

from dashboard.runtime._utils import safe_float


class PositionStateBuilder:
    """
    PCNRASS-safe normalized position state builder.

    Purpose:
    - Convert raw positions payloads into a stable DashboardState-ready contract.
    - Keep position summary logic out of dashboard rendering.
    - Avoid mutation of source payloads.
    """

    def build(self, positions_payload: Dict[str, Any] | None) -> Dict[str, Any]:
        payload = positions_payload or {}
        positions = payload.get("positions", []) or []

        normalized_positions: List[Dict[str, Any]] = []
        asset_counts: Dict[str, int] = {}
        asset_unrealized_pnl: Dict[str, float] = {}
        asset_realized_pnl: Dict[str, float] = {}
        active_symbols: List[str] = []

        total_exposure = 0.0
        total_unrealized_pnl = 0.0
        total_realized_pnl = 0.0
        long_count = 0
        short_count = 0
        winners = 0
        losers = 0

        for item in positions:
            if not isinstance(item, dict):
                continue

            symbol = str(item.get("symbol", "UNKNOWN"))
            asset_class = str(item.get("asset_class", "UNKNOWN")).upper()
            side = str(item.get("side", "UNKNOWN")).upper()

            qty = safe_float(item.get("qty", item.get("quantity", 0.0)))
            entry_price = safe_float(item.get("entry_price", item.get("entry", 0.0)))
            current_price = safe_float(
                item.get("current_price", item.get("mark_price", entry_price))
            )

            exposure = abs(qty * current_price)
            unrealized_pnl = safe_float(item.get("unrealized_pnl", 0.0))
            realized_pnl = safe_float(item.get("realized_pnl", 0.0))

            if side == "LONG" or side == "BUY":
                long_count += 1
            elif side == "SHORT" or side == "SELL":
                short_count += 1

            if unrealized_pnl > 0:
                winners += 1
            elif unrealized_pnl < 0:
                losers += 1

            total_exposure += exposure
            total_unrealized_pnl += unrealized_pnl
            total_realized_pnl += realized_pnl

            asset_counts[asset_class] = asset_counts.get(asset_class, 0) + 1
            asset_unrealized_pnl[asset_class] = asset_unrealized_pnl.get(asset_class, 0.0) + unrealized_pnl
            asset_realized_pnl[asset_class] = asset_realized_pnl.get(asset_class, 0.0) + realized_pnl

            if symbol not in active_symbols:
                active_symbols.append(symbol)

            normalized_positions.append(
                {
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "side": side,
                    "qty": qty,
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "exposure": exposure,
                    "unrealized_pnl": unrealized_pnl,
                    "realized_pnl": realized_pnl,
                }
            )

        return {
            "positions": normalized_positions,
            "open_count": len(normalized_positions),
            "active_symbols": active_symbols,
            "asset_counts": asset_counts,
            "asset_unrealized_pnl": asset_unrealized_pnl,
            "asset_realized_pnl": asset_realized_pnl,
            "total_exposure": total_exposure,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_realized_pnl": total_realized_pnl,
            "net_pnl": total_unrealized_pnl + total_realized_pnl,
            "long_count": long_count,
            "short_count": short_count,
            "winner_count": winners,
            "loser_count": losers,
        }

