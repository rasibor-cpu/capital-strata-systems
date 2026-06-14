from __future__ import annotations

from typing import Any, Dict

from dashboard.runtime._utils import safe_float, safe_int


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

        realized_pnl = safe_float(
            positions.get(
                "realized_pnl",
                positions.get("total_realized_pnl", 0.0),
            )
        )

        unrealized_pnl = safe_float(
            positions.get(
                "unrealized_pnl",
                positions.get("total_unrealized_pnl", 0.0),
            )
        )

        net_pnl = safe_float(
            positions.get("net_pnl", realized_pnl + unrealized_pnl)
        )

        total_exposure = safe_float(
            positions.get("total_exposure", 0.0)
        )

        account_equity = safe_float(
            positions.get(
                "equity",
                account.get("equity", account.get("balance", 0.0)),
            )
        )

        exposure_utilization = 0.0

        if account_equity > 0:
            exposure_utilization = (
                total_exposure / account_equity
            ) * 100.0

        winners = safe_int(positions.get("winner_count", 0))
        losers = safe_int(positions.get("loser_count", 0))

        total_closed_bias = winners + losers

        win_rate = 0.0

        if total_closed_bias > 0:
            win_rate = (winners / total_closed_bias) * 100.0

        asset_realized = _safe_pnl_map(
            positions.get("asset_realized_pnl", {})
        )

        asset_unrealized = _safe_pnl_map(
            positions.get("asset_unrealized_pnl", {})
        )

        return {
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "net_pnl": net_pnl,
            "equity": account_equity,
            "peak_equity": safe_float(
                positions.get("peak_equity", account_equity)
            ),
            "current_drawdown": safe_float(
                positions.get("current_drawdown", 0.0)
            ),
            "max_drawdown": safe_float(
                positions.get("max_drawdown", 0.0)
            ),
            "total_exposure": total_exposure,
            "exposure_utilization_pct": exposure_utilization,
            "winner_count": winners,
            "loser_count": losers,
            "win_rate_pct": win_rate,
            "asset_realized_pnl": asset_realized,
            "asset_unrealized_pnl": asset_unrealized,
            "open_positions": safe_int(
                positions.get("open_positions", positions.get("open_count", 0))
            ),
            "closed_positions": safe_int(
                positions.get("closed_positions", 0)
            ),
            "source": str(positions.get("source", "LEGACY_POSITION_STATE")),
            "account_equity": account_equity,
        }


def _safe_pnl_map(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}

    return {
        str(key): safe_float(amount)
        for key, amount in value.items()
    }

