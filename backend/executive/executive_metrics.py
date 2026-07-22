"""Single calculation authority for Executive Intelligence financial metrics."""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from .executive_models import MetricValue, TrafficLight


class ExecutiveMetricEngine:
    """Calculate the canonical metric set exactly once from a read-only snapshot."""

    def calculate(self, snapshot: Mapping[str, Any] | None) -> dict[str, MetricValue]:
        source = dict(snapshot or {})
        as_of = str(
            source.get("as_of")
            or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        revenue = _number(source.get("revenue"))
        cost_of_revenue = _number(source.get("cost_of_revenue", source.get("cost_of_goods_sold")))
        operating_expenses = _number(source.get("operating_expenses"))
        taxes = _number(source.get("taxes"))
        gross_profit = revenue - cost_of_revenue
        operating_profit = gross_profit - operating_expenses
        net_profit = _optional_number(source.get("net_profit"))
        if net_profit is None:
            net_profit = operating_profit - taxes

        realized = _number(source.get("realized_pnl"))
        unrealized = _number(source.get("unrealized_pnl"))
        equity = _first_number(
            source,
            "portfolio_equity",
            "equity",
            "nav",
            default=0.0,
        )
        nav = _first_number(source, "nav", "portfolio_equity", "equity", default=equity)
        cash = _first_number(source, "available_cash", "cash", default=0.0)
        buying_power = _number(source.get("buying_power"))
        deployed = _first_number(source, "deployed_capital", "capital_used", default=0.0)
        liabilities = _number(source.get("liabilities"))
        gross_exposure = _first_number(source, "gross_exposure", "exposure", default=0.0)
        opening_equity = _number(source.get("opening_equity"))
        total_trades = int(_number(source.get("total_trades")))
        wins = int(_number(source.get("wins")))
        losses = int(_number(source.get("losses", max(total_trades - wins, 0))))
        winning_pnl = _number(source.get("winning_pnl"))
        losing_pnl = abs(_number(source.get("losing_pnl")))
        returns = _number_sequence(source.get("returns"))
        equity_curve = _number_sequence(source.get("equity_curve"))
        current_drawdown, maximum_drawdown = _drawdowns(equity_curve)

        win_rate = _ratio(wins, total_trades)
        profit_factor = _ratio(winning_pnl, losing_pnl)
        average_win = _ratio(winning_pnl, wins)
        average_loss = _ratio(losing_pnl, losses)
        expectancy = (win_rate * average_win) - ((1.0 - win_rate) * average_loss)
        volatility = statistics.pstdev(returns) * math.sqrt(252) if len(returns) > 1 else 0.0
        sharpe = _sharpe(returns)
        sortino = _sortino(returns)
        capital_utilization = _ratio(deployed, equity)
        capital_efficiency = _ratio(net_profit, deployed)
        liquidity_ratio = _ratio(cash, liabilities)
        cash_ratio = _ratio(cash, liabilities)
        leverage = _ratio(gross_exposure, equity)

        values: dict[str, tuple[str, float, str, TrafficLight]] = {
            "net_profit": ("Net Profit", net_profit, "currency", _profit_status(net_profit)),
            "gross_profit": ("Gross Profit", gross_profit, "currency", _profit_status(gross_profit)),
            "operating_profit": (
                "Operating Profit",
                operating_profit,
                "currency",
                _profit_status(operating_profit),
            ),
            "daily_return": (
                "Daily Return",
                _return(source, "daily_return", opening_equity, equity),
                "ratio",
                _return_status(_return(source, "daily_return", opening_equity, equity)),
            ),
            "weekly_return": _return_tuple(source, "weekly_return", "Weekly Return"),
            "monthly_return": _return_tuple(source, "monthly_return", "Monthly Return"),
            "quarterly_return": _return_tuple(source, "quarterly_return", "Quarterly Return"),
            "annual_return": _return_tuple(source, "annual_return", "Annual Return"),
            "ytd_return": _return_tuple(source, "ytd_return", "YTD Return"),
            "mtd_return": _return_tuple(source, "mtd_return", "MTD Return"),
            "nav": ("NAV", nav, "currency", _availability_status(nav)),
            "available_cash": ("Available Cash", cash, "currency", _availability_status(cash)),
            "buying_power": ("Buying Power", buying_power, "currency", _availability_status(buying_power)),
            "capital_utilization": (
                "Capital Utilization",
                capital_utilization,
                "ratio",
                _bounded_status(capital_utilization, 0.25, 0.85),
            ),
            "capital_efficiency": (
                "Capital Efficiency",
                capital_efficiency,
                "ratio",
                _return_status(capital_efficiency),
            ),
            "liquidity_ratio": (
                "Liquidity Ratio",
                liquidity_ratio,
                "ratio",
                _minimum_status(liquidity_ratio, 1.0, 0.5),
            ),
            "cash_ratio": (
                "Cash Ratio",
                cash_ratio,
                "ratio",
                _minimum_status(cash_ratio, 1.0, 0.5),
            ),
            "leverage": ("Leverage", leverage, "ratio", _maximum_status(leverage, 1.5, 2.5)),
            "win_rate": ("Win Rate", win_rate, "ratio", _minimum_status(win_rate, 0.55, 0.45)),
            "profit_factor": (
                "Profit Factor",
                profit_factor,
                "ratio",
                _minimum_status(profit_factor, 1.5, 1.0),
            ),
            "expectancy": ("Expectancy", expectancy, "currency", _profit_status(expectancy)),
            "sharpe_ratio": ("Sharpe Ratio", sharpe, "ratio", _minimum_status(sharpe, 1.0, 0.0)),
            "sortino_ratio": ("Sortino Ratio", sortino, "ratio", _minimum_status(sortino, 1.0, 0.0)),
            "maximum_drawdown": (
                "Maximum Drawdown",
                maximum_drawdown,
                "ratio",
                _maximum_status(maximum_drawdown, 0.10, 0.20),
            ),
            "current_drawdown": (
                "Current Drawdown",
                current_drawdown,
                "ratio",
                _maximum_status(current_drawdown, 0.05, 0.10),
            ),
            "volatility": (
                "Volatility",
                volatility,
                "ratio",
                _maximum_status(volatility, 0.15, 0.30),
            ),
            "realized_pnl": ("Realized PnL", realized, "currency", _profit_status(realized)),
            "unrealized_pnl": ("Unrealized PnL", unrealized, "currency", _profit_status(unrealized)),
            "portfolio_equity": (
                "Portfolio Equity",
                equity,
                "currency",
                _availability_status(equity),
            ),
            "exposure": (
                "Exposure",
                gross_exposure,
                "currency",
                _availability_status(gross_exposure),
            ),
            "broker_allocation": (
                "Broker Allocation",
                _allocation_total(source.get("broker_allocation")),
                "ratio",
                _allocation_status(source.get("broker_allocation")),
            ),
            "strategy_allocation": (
                "Strategy Allocation",
                _allocation_total(source.get("strategy_allocation")),
                "ratio",
                _allocation_status(source.get("strategy_allocation")),
            ),
            "asset_allocation": (
                "Asset Allocation",
                _allocation_total(source.get("asset_allocation")),
                "ratio",
                _allocation_status(source.get("asset_allocation")),
            ),
        }
        return {
            key: MetricValue(
                key=key,
                label=label,
                value=round(value, 8),
                unit=unit,
                status=status,
                as_of=as_of,
            )
            for key, (label, value, unit, status) in values.items()
        }


def serialize_metrics(metrics: Mapping[str, MetricValue]) -> dict[str, dict[str, Any]]:
    return {key: metric.as_dict() for key, metric in metrics.items()}


def _number(value: Any) -> float:
    try:
        return float(value if value not in (None, "") else 0.0)
    except (TypeError, ValueError):
        return 0.0


def _optional_number(value: Any) -> float | None:
    return None if value in (None, "") else _number(value)


def _first_number(source: Mapping[str, Any], *keys: str, default: float) -> float:
    for key in keys:
        if source.get(key) not in (None, ""):
            return _number(source[key])
    return default


def _number_sequence(value: Any) -> list[float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_number(item) for item in value]


def _ratio(numerator: float, denominator: float | int) -> float:
    return numerator / float(denominator) if denominator else 0.0


def _return(source: Mapping[str, Any], key: str, opening: float, closing: float) -> float:
    if source.get(key) not in (None, ""):
        return _number(source[key])
    return _ratio(closing - opening, opening)


def _return_tuple(source: Mapping[str, Any], key: str, label: str) -> tuple[str, float, str, TrafficLight]:
    value = _number(source.get(key))
    return label, value, "ratio", _return_status(value)


def _drawdowns(curve: Sequence[float]) -> tuple[float, float]:
    if not curve:
        return 0.0, 0.0
    peak = curve[0]
    maximum = 0.0
    current = 0.0
    for value in curve:
        peak = max(peak, value)
        current = _ratio(peak - value, peak)
        maximum = max(maximum, current)
    return current, maximum


def _sharpe(returns: Sequence[float]) -> float:
    if len(returns) < 2:
        return 0.0
    deviation = statistics.pstdev(returns)
    return statistics.mean(returns) / deviation * math.sqrt(252) if deviation else 0.0


def _sortino(returns: Sequence[float]) -> float:
    if len(returns) < 2:
        return 0.0
    downside = [min(value, 0.0) for value in returns]
    deviation = math.sqrt(sum(value * value for value in downside) / len(downside))
    return statistics.mean(returns) / deviation * math.sqrt(252) if deviation else 0.0


def _allocation_total(value: Any) -> float:
    if not isinstance(value, Mapping):
        return 0.0
    return sum(_number(item) for item in value.values())


def _allocation_status(value: Any) -> TrafficLight:
    total = _allocation_total(value)
    return TrafficLight.GREEN if abs(total - 1.0) <= 0.02 else TrafficLight.AMBER if total else TrafficLight.RED


def _profit_status(value: float) -> TrafficLight:
    return TrafficLight.GREEN if value > 0 else TrafficLight.AMBER if value == 0 else TrafficLight.RED


def _return_status(value: float) -> TrafficLight:
    return _profit_status(value)


def _availability_status(value: float) -> TrafficLight:
    return TrafficLight.GREEN if value > 0 else TrafficLight.AMBER


def _minimum_status(value: float, green: float, amber: float) -> TrafficLight:
    return TrafficLight.GREEN if value >= green else TrafficLight.AMBER if value >= amber else TrafficLight.RED


def _maximum_status(value: float, green: float, amber: float) -> TrafficLight:
    return TrafficLight.GREEN if value <= green else TrafficLight.AMBER if value <= amber else TrafficLight.RED


def _bounded_status(value: float, lower: float, upper: float) -> TrafficLight:
    if lower <= value <= upper:
        return TrafficLight.GREEN
    if value <= 1.0:
        return TrafficLight.AMBER
    return TrafficLight.RED


__all__ = ["ExecutiveMetricEngine", "serialize_metrics"]
