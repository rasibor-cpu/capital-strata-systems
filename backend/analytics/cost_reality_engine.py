from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


class CostRealityEngine:
    """
    Safe-mode execution cost analytics engine.

    Read-only analytics layer.
    No execution gating or broker mutation occurs here.
    """

    DEFAULT_SPREAD_BPS = {
        "crypto": 12.0,
        "fx": 3.0,
        "futures": 2.0,
        "options": 18.0,
        "equities": 4.0,
        "unknown": 8.0,
    }

    DEFAULT_SLIPPAGE_BPS = {
        "crypto": 6.0,
        "fx": 1.5,
        "futures": 1.0,
        "options": 12.0,
        "equities": 2.0,
        "unknown": 4.0,
    }

    DEFAULT_COMMISSION_BPS = {
        "crypto": 10.0,
        "fx": 1.0,
        "futures": 1.5,
        "options": 4.0,
        "equities": 1.0,
        "unknown": 2.0,
    }

    DEFAULT_FINANCING_BPS = {
        "crypto": 2.0,
        "fx": 1.0,
        "futures": 1.5,
        "options": 3.0,
        "equities": 0.5,
        "unknown": 1.0,
    }

    def evaluate(
        self,
        asset_class: str = "unknown",
        expected_move_bps: float = 0.0,
    ) -> Dict[str, Any]:
        asset_key = str(asset_class or "unknown").lower()

        spread = self.DEFAULT_SPREAD_BPS.get(asset_key, self.DEFAULT_SPREAD_BPS["unknown"])
        slippage = self.DEFAULT_SLIPPAGE_BPS.get(asset_key, self.DEFAULT_SLIPPAGE_BPS["unknown"])
        commission = self.DEFAULT_COMMISSION_BPS.get(asset_key, self.DEFAULT_COMMISSION_BPS["unknown"])
        financing = self.DEFAULT_FINANCING_BPS.get(asset_key, self.DEFAULT_FINANCING_BPS["unknown"])

        total_cost = spread + slippage + commission + financing
        net_edge = float(expected_move_bps) - total_cost

        return {
            "timestamp": self._now(),
            "asset_class": asset_key,
            "expected_move_bps": round(float(expected_move_bps), 6),
            "spread_bps": round(spread, 6),
            "slippage_bps": round(slippage, 6),
            "commission_bps": round(commission, 6),
            "financing_bps": round(financing, 6),
            "total_cost_bps": round(total_cost, 6),
            "net_edge_bps": round(net_edge, 6),
            "cost_adjusted_profitable": net_edge > 0,
            "mode": "safe_read_only",
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()