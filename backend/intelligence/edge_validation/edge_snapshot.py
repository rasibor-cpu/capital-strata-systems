from __future__ import annotations

from typing import Any, Dict, Iterable

from backend.intelligence.edge_validation.edge_metrics import (
    compute_edge_metrics,
)


def build_edge_snapshot(
    trades: Iterable[Dict[str, Any]],
) -> Dict[str, float]:

    metrics = compute_edge_metrics(
        trades
    )

    snapshot = {
        "trade_count": metrics[
            "trade_count"
        ],
        "gross_pnl": metrics[
            "gross_pnl"
        ],
        "total_costs": metrics[
            "total_costs"
        ],
        "net_pnl": metrics[
            "net_pnl"
        ],
        "expectancy": metrics[
            "expectancy"
        ],
        "profit_factor": metrics[
            "profit_factor"
        ],
        "win_rate": metrics[
            "win_rate"
        ],
        "average_win": metrics[
            "average_win"
        ],
        "average_loss": metrics[
            "average_loss"
        ],
    }

    return snapshot


__all__ = [
    "build_edge_snapshot",
]
