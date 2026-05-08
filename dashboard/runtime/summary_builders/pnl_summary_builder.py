from __future__ import annotations

from typing import Any, Dict


class PnLSummaryBuilder:
    """
    PCNRASS-safe PnL summary aggregation builder.

    Purpose:
    - Build executive/runtime PnL summaries from normalized dashboard state.
    - Keep aggregation logic separate from renderers.
    - Prevent dashboard layers from touching raw engine internals.
    - Remain a presentation-layer builder, not the accounting authority.
    - In production/live mode, consume canonical ledger state rather than
      independently determining accounting truth.
    - Treat engine.ledger.pnl_engine.PnLEngine as the canonical PnL source.
    """

    def build(
        self,
        account_state: Dict[str, Any] | None,
        position_state: Dict[str, Any] | None,
    ) -> Dict[str, Any]:

        account = account_state or {}
        positions = position_state or {}

        realized_pnl = self._to_float(
            positions.get("total_realized_pnl", 0.0)
        )

        unrealized_pnl = self._to_float(
            positions.get("total_unrealized_pnl", 0.0)
        )

        net_pnl = realized_pnl + unrealized_pnl

        total_exposure = self._to_float(
            positions.get("total_exposure", 0.0)
        )

        account_equity = self._to_float(
            account.get("equity", account.get("balance", 0.0))
        )

        exposure_utilization = 0.0

        if account_equity > 0:
            exposure_utilization = (
                total_exposure / account_equity
            ) * 100.0

        winners = int(positions.get("winner_count", 0))
        losers = int(positions.get("loser_count", 0))

        total_closed_bias = winners + losers

        win_rate = 0.0

        if total_closed_bias > 0:
            win_rate = (winners / total_closed_bias) * 100.0

        asset_realized = positions.get(
            "asset_realized_pnl",
            {},
        )

        asset_unrealized = positions.get(
            "asset_unrealized_pnl",
            {},
        )

        return {
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "net_pnl": net_pnl,
            "total_exposure": total_exposure,
            "exposure_utilization_pct": exposure_utilization,
            "winner_count": winners,
            "loser_count": losers,
            "win_rate_pct": win_rate,
            "asset_realized_pnl": asset_realized,
            "asset_unrealized_pnl": asset_unrealized,
            "account_equity": account_equity,
        }

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            if value is None:
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0
