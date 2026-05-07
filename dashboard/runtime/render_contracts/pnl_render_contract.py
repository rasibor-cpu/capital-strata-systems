from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class PnLRenderContract:
    """
    PCNRASS-safe immutable render contract for PnL display.

    Purpose:
    - Define exactly what renderers may consume.
    - Prevent renderer-side calculations.
    - Prevent direct engine access from UI layers.
    - Create stable presentation contracts for future web/API/mobile renderers.
    """

    realized_pnl: float
    unrealized_pnl: float
    net_pnl: float

    total_exposure: float
    exposure_utilization_pct: float

    winner_count: int
    loser_count: int
    win_rate_pct: float

    account_equity: float

    asset_realized_pnl: Dict[str, float]
    asset_unrealized_pnl: Dict[str, float]

    @classmethod
    def from_summary(cls, pnl_summary: dict) -> "PnLRenderContract":
        summary = pnl_summary or {}

        return cls(
            realized_pnl=float(summary.get("realized_pnl", 0.0)),
            unrealized_pnl=float(summary.get("unrealized_pnl", 0.0)),
            net_pnl=float(summary.get("net_pnl", 0.0)),
            total_exposure=float(summary.get("total_exposure", 0.0)),
            exposure_utilization_pct=float(
                summary.get("exposure_utilization_pct", 0.0)
            ),
            winner_count=int(summary.get("winner_count", 0)),
            loser_count=int(summary.get("loser_count", 0)),
            win_rate_pct=float(summary.get("win_rate_pct", 0.0)),
            account_equity=float(summary.get("account_equity", 0.0)),
            asset_realized_pnl=dict(
                summary.get("asset_realized_pnl", {})
            ),
            asset_unrealized_pnl=dict(
                summary.get("asset_unrealized_pnl", {})
            ),
        )