"""Executive KPI projection from the canonical metric map."""

from __future__ import annotations

from collections.abc import Mapping

from .executive_models import MetricValue


EXECUTIVE_KPI_KEYS = (
    "net_profit",
    "daily_return",
    "ytd_return",
    "nav",
    "available_cash",
    "capital_utilization",
    "capital_efficiency",
    "liquidity_ratio",
    "leverage",
    "win_rate",
    "profit_factor",
    "sharpe_ratio",
    "maximum_drawdown",
    "realized_pnl",
    "unrealized_pnl",
)


def select_executive_kpis(
    metrics: Mapping[str, MetricValue],
) -> dict[str, MetricValue]:
    return {
        key: metrics[key]
        for key in EXECUTIVE_KPI_KEYS
        if key in metrics
    }


__all__ = ["EXECUTIVE_KPI_KEYS", "select_executive_kpis"]
