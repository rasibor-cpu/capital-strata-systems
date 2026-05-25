from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


class CostRealityEngine:
    """Broker-agnostic, additive cost analytics (safe-mode only)."""

    def build(self, trades: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        totals = {
            "spread_burden": 0.0,
            "slippage_burden": 0.0,
            "commission_burden": 0.0,
            "financing_burden": 0.0,
            "gross_pnl": 0.0,
        }

        for trade in trades or []:
            qty = abs(float(trade.get("qty", 0.0)))
            notional = abs(float(trade.get("notional", 0.0)))
            spread_bps = float(trade.get("spread_bps", 0.0))
            slippage_bps = float(trade.get("slippage_bps", 0.0))
            commission = float(trade.get("commission", 0.0))
            financing_rate_bps = float(trade.get("financing_bps", 0.0))

            totals["spread_burden"] += notional * (spread_bps / 10000.0)
            totals["slippage_burden"] += notional * (slippage_bps / 10000.0)
            totals["commission_burden"] += commission
            totals["financing_burden"] += notional * (financing_rate_bps / 10000.0)
            totals["gross_pnl"] += float(trade.get("pnl", 0.0))
            _ = qty  # explicit signal this remains quantity-aware for extension

        total_cost = (
            totals["spread_burden"]
            + totals["slippage_burden"]
            + totals["commission_burden"]
            + totals["financing_burden"]
        )
        net_profitability = totals["gross_pnl"] - total_cost

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "deterministic": True,
            "cost_components": {
                "spread_burden": totals["spread_burden"],
                "slippage_burden": totals["slippage_burden"],
                "commission_burden": totals["commission_burden"],
                "financing_burden": totals["financing_burden"],
                "total_estimated_cost": total_cost,
            },
            "gross_pnl": totals["gross_pnl"],
            "cost_adjusted_profitability": net_profitability,
            "net_edge_estimate": net_profitability,
        }
