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
        """
        Build PnL summary exclusively from the CanonicalPnLSnapshotContract.
        Legacy position state calculation and aggregation is retired (Phase 105B).
        """
        positions = position_state or {}
        account = account_state or {}

        # Pure passthrough from Canonical PnL Snapshot
        realized_pnl = _first_safe_float(
            positions,
            ("realized_pnl", "total_realized_pnl"),
        )
        unrealized_pnl = _first_safe_float(
            positions,
            ("unrealized_pnl", "total_unrealized_pnl"),
        )
        net_pnl = safe_float(positions.get("net_pnl", realized_pnl + unrealized_pnl))
        account_equity = _first_safe_float(
            positions,
            ("equity",),
            default=_first_safe_float(
                account,
                ("equity", "total_equity", "account_equity"),
            ),
        )
        
        # We don't calculate exposures and win rates here anymore as they belong to 
        # risk or trade ledgers, but we safely pass 0.0 to satisfy strict type rendering if needed,
        # or we just let them be 0 until a dedicated summary builder handles them.
        total_exposure = safe_float(positions.get("total_exposure", 0.0))
        exposure_utilization = 0.0
        if account_equity > 0:
            exposure_utilization = (total_exposure / account_equity) * 100.0
            
        winners = safe_int(positions.get("winner_count", 0))
        losers = safe_int(positions.get("loser_count", 0))
        total_closed_bias = winners + losers
        win_rate = 0.0
        if total_closed_bias > 0:
            win_rate = (winners / total_closed_bias) * 100.0

        return {
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "net_pnl": net_pnl,
            "equity": account_equity,
            "peak_equity": safe_float(positions.get("peak_equity", account_equity)),
            "current_drawdown": safe_float(positions.get("current_drawdown", 0.0)),
            "max_drawdown": safe_float(positions.get("max_drawdown", 0.0)),
            "total_exposure": total_exposure,
            "exposure_utilization_pct": exposure_utilization,
            "winner_count": winners,
            "loser_count": losers,
            "win_rate_pct": win_rate,
            "asset_realized_pnl": _safe_pnl_map(positions.get("asset_realized_pnl", {})),
            "asset_unrealized_pnl": _safe_pnl_map(positions.get("asset_unrealized_pnl", {})),
            "open_positions": safe_int(
                positions.get("open_positions", positions.get("open_count", 0))
            ),
            "closed_positions": safe_int(
                positions.get("closed_positions", positions.get("closed_count", 0))
            ),
            "source": str(positions.get("source", "engine.ledger.pnl_engine.PnLEngine")),
            "account_equity": account_equity,
        }


def _first_safe_float(
    values: Dict[str, Any],
    keys: tuple[str, ...],
    default: float = 0.0,
) -> float:
    for key in keys:
        if key in values and values.get(key) is not None:
            return safe_float(values.get(key))
    return safe_float(default)


def _safe_pnl_map(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}

    return {
        str(key): safe_float(amount)
        for key, amount in value.items()
    }

