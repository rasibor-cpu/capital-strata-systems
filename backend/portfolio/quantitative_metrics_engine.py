from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from backend.portfolio.utils import safe_series


class QuantitativeMetricsEngineError(RuntimeError):
    """Fail-closed exception for quantitative metric analysis."""


class QuantitativeMetricsEngine:
    """Dependency-free portfolio metrics from deterministic return series."""

    def compute(
        self,
        portfolio_returns: Iterable[Any] | None,
        benchmark_returns: Iterable[Any] | None = None,
        asset_returns: Mapping[str, Iterable[Any]] | None = None,
        risk_free_rate: float = 0.0,
    ) -> dict[str, Any]:
        returns = self._series(portfolio_returns)
        if len(returns) < 2:
            return self._unavailable("portfolio_return_series_insufficient")

        benchmark = self._series(benchmark_returns)
        assets = self._asset_series(asset_returns)
        excess = [value - risk_free_rate for value in returns]
        downside = [min(0.0, value - risk_free_rate) for value in returns]
        volatility = self._stddev(returns)
        downside_deviation = math.sqrt(sum(value * value for value in downside) / len(downside))
        cumulative = self._cumulative_curve(returns)
        drawdowns = self._drawdowns(cumulative)
        max_drawdown = abs(min(drawdowns)) if drawdowns else 0.0

        rolling_sharpe = self._ratio(self._mean(excess), volatility)
        rolling_sortino = self._ratio(self._mean(excess), downside_deviation)
        calmar = self._ratio(sum(returns), max_drawdown)
        omega = self._omega_ratio(returns, risk_free_rate)
        information_ratio = None
        alpha = None
        beta = None
        if len(benchmark) >= 2:
            paired = self._paired(returns, benchmark)
            active = [left - right for left, right in paired]
            information_ratio = self._ratio(self._mean(active), self._stddev(active))
            benchmark_values = [right for _, right in paired]
            portfolio_values = [left for left, _ in paired]
            beta = self._beta(portfolio_values, benchmark_values)
            alpha = self._mean(portfolio_values) - beta * self._mean(benchmark_values)

        correlation_inputs = dict(assets)
        if not correlation_inputs:
            correlation_inputs["PORTFOLIO"] = returns
            if len(benchmark) >= 2:
                correlation_inputs["BENCHMARK"] = benchmark

        return {
            "status": "OK",
            "metrics": {
                "rolling_sharpe": self._round(rolling_sharpe),
                "rolling_sortino": self._round(rolling_sortino),
                "calmar_ratio": self._round(calmar),
                "omega_ratio": self._round(omega),
                "information_ratio": self._round(information_ratio),
                "alpha": self._round(alpha),
                "beta": self._round(beta),
                "max_drawdown": self._round(max_drawdown),
                "drawdown_distribution": [self._round(abs(value)) for value in drawdowns],
                "volatility": self._round(volatility),
                "downside_deviation": self._round(downside_deviation),
            },
            "correlation_matrix": self._correlation_matrix(correlation_inputs),
            "sample_size": len(returns),
            "advisory_only": True,
        }

    @staticmethod
    def _series(values: Iterable[Any] | None) -> list[float]:
        return safe_series(values)

    def _asset_series(self, asset_returns: Mapping[str, Iterable[Any]] | None) -> dict[str, list[float]]:
        if not isinstance(asset_returns, Mapping):
            return {}
        result: dict[str, list[float]] = {}
        for key, values in asset_returns.items():
            name = str(key or "").strip().upper()
            if not name:
                continue
            series = self._series(values)
            if len(series) >= 2:
                result[name] = series
        return result

    @staticmethod
    def _cumulative_curve(returns: list[float]) -> list[float]:
        total = 1.0
        curve = []
        for value in returns:
            total *= 1.0 + value
            curve.append(total)
        return curve

    @staticmethod
    def _drawdowns(curve: list[float]) -> list[float]:
        peak = None
        drawdowns = []
        for value in curve:
            peak = value if peak is None else max(peak, value)
            drawdowns.append((value - peak) / peak if peak else 0.0)
        return drawdowns

    def _correlation_matrix(self, inputs: Mapping[str, list[float]]) -> dict[str, dict[str, float]]:
        names = sorted(inputs.keys())
        matrix: dict[str, dict[str, float]] = {}
        for left in names:
            matrix[left] = {}
            for right in names:
                if left == right:
                    matrix[left][right] = 1.0
                    continue
                paired = self._paired(inputs[left], inputs[right])
                if len(paired) < 2:
                    matrix[left][right] = 0.0
                else:
                    matrix[left][right] = self._round(
                        self._correlation([item[0] for item in paired], [item[1] for item in paired])
                    )
        return matrix

    @staticmethod
    def _paired(left: list[float], right: list[float]) -> list[tuple[float, float]]:
        size = min(len(left), len(right))
        return list(zip(left[:size], right[:size]))

    @staticmethod
    def _mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def _stddev(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = self._mean(values)
        return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))

    def _correlation(self, left: list[float], right: list[float]) -> float:
        std_left = self._stddev(left)
        std_right = self._stddev(right)
        if std_left == 0.0 or std_right == 0.0:
            return 0.0
        mean_left = self._mean(left)
        mean_right = self._mean(right)
        covariance = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right)) / len(left)
        return max(-1.0, min(1.0, covariance / (std_left * std_right)))

    def _beta(self, portfolio: list[float], benchmark: list[float]) -> float:
        variance = self._stddev(benchmark) ** 2
        if variance == 0.0:
            return 0.0
        mean_portfolio = self._mean(portfolio)
        mean_benchmark = self._mean(benchmark)
        covariance = sum((a - mean_portfolio) * (b - mean_benchmark) for a, b in zip(portfolio, benchmark)) / len(portfolio)
        return covariance / variance

    @staticmethod
    def _ratio(numerator: float, denominator: float) -> float | None:
        if denominator == 0.0:
            return None
        return numerator / denominator

    @staticmethod
    def _omega_ratio(returns: list[float], threshold: float) -> float | None:
        gains = sum(max(0.0, value - threshold) for value in returns)
        losses = sum(abs(min(0.0, value - threshold)) for value in returns)
        if losses == 0.0:
            return None
        return gains / losses

    @staticmethod
    def _round(value: float | None) -> float | None:
        if value is None:
            return None
        return round(value, 8)

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "metrics": {},
            "correlation_matrix": {},
            "sample_size": 0,
            "reasons": [reason],
            "advisory_only": True,
        }
