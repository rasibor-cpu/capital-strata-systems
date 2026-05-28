from __future__ import annotations

from typing import Any, Dict, Iterable


def _to_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def compute_edge_metrics(
    trades: Iterable[Dict[str, Any]],
) -> Dict[str, float]:

    trade_list = list(
        trades or []
    )

    if not trade_list:
        return {
            "trade_count": 0.0,
            "gross_pnl": 0.0,
            "total_costs": 0.0,
            "net_pnl": 0.0,
            "win_rate": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "expectancy": 0.0,
            "profit_factor": 0.0,
        }

    net_results = []

    gross_pnl = 0.0
    total_costs = 0.0

    for trade in trade_list:

        gross = _to_float(
            trade.get("gross_pnl")
        )

        costs = (
            _to_float(trade.get("costs"))
            + _to_float(trade.get("fees"))
            + _to_float(trade.get("slippage"))
            + _to_float(trade.get("spread_cost"))
            + _to_float(trade.get("financing_cost"))
        )

        net = gross - costs

        gross_pnl += gross
        total_costs += costs
        net_results.append(net)

    wins = [
        result
        for result in net_results
        if result > 0
    ]

    losses = [
        result
        for result in net_results
        if result < 0
    ]

    trade_count = len(
        net_results
    )

    win_count = len(
        wins
    )

    loss_count = len(
        losses
    )

    net_pnl = sum(
        net_results
    )

    gross_profit = sum(
        wins
    )

    gross_loss = abs(
        sum(
            losses
        )
    )

    win_rate = (
        win_count / trade_count
        if trade_count > 0
        else 0.0
    )

    average_win = (
        gross_profit / win_count
        if win_count > 0
        else 0.0
    )

    average_loss = (
        gross_loss / loss_count
        if loss_count > 0
        else 0.0
    )

    expectancy = (
        net_pnl / trade_count
        if trade_count > 0
        else 0.0
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else gross_profit
    )

    return {
        "trade_count": float(trade_count),
        "gross_pnl": float(gross_pnl),
        "total_costs": float(total_costs),
        "net_pnl": float(net_pnl),
        "win_rate": float(win_rate),
        "average_win": float(average_win),
        "average_loss": float(average_loss),
        "expectancy": float(expectancy),
        "profit_factor": float(profit_factor),
    }


__all__ = [
    "compute_edge_metrics",
]
