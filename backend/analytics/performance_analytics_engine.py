from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


class PerformanceAnalyticsEngineError(RuntimeError):
    """Fail-closed exception for performance analytics operations."""


@dataclass(frozen=True)
class PerformanceMetrics:
    trade_count: int
    win_rate: float
    profit_factor: float
    expectancy: float
    average_r: float
    average_hold_time: float
    max_drawdown: float
    recovery_factor: float
    consecutive_wins: int
    consecutive_losses: int
    asset_performance: dict[str, dict[str, float]]
    strategy_performance: dict[str, dict[str, float]]
    regime_performance: dict[str, dict[str, float]]
    trade_quality_distribution: dict[str, int]
    gross_profit: float
    gross_loss: float
    total_pnl: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PerformanceAnalyticsEngine:
    """Deterministic analytics for trade performance and learning telemetry."""

    _QUALITY_BUCKETS = (
        (85.0, "A"),
        (70.0, "B"),
        (55.0, "C"),
        (40.0, "D"),
    )

    def analyze(self, completed_trades: list[Mapping[str, Any]] | None) -> dict[str, Any]:
        if completed_trades is None:
            raise PerformanceAnalyticsEngineError("completed_trades must not be None")
        if not isinstance(completed_trades, list):
            raise PerformanceAnalyticsEngineError("completed_trades must be a list")

        trades = [self._normalize_trade(trade) for trade in completed_trades]
        if not trades:
            return PerformanceMetrics(
                trade_count=0,
                win_rate=0.0,
                profit_factor=0.0,
                expectancy=0.0,
                average_r=0.0,
                average_hold_time=0.0,
                max_drawdown=0.0,
                recovery_factor=0.0,
                consecutive_wins=0,
                consecutive_losses=0,
                asset_performance={},
                strategy_performance={},
                regime_performance={},
                trade_quality_distribution={},
                gross_profit=0.0,
                gross_loss=0.0,
                total_pnl=0.0,
            ).to_dict()

        winners = [trade for trade in trades if trade["pnl"] > 0.0]
        losers = [trade for trade in trades if trade["pnl"] < 0.0]
        gross_profit = round(sum(trade["pnl"] for trade in winners), 8)
        gross_loss = round(abs(sum(trade["pnl"] for trade in losers)), 8)
        total_pnl = round(sum(trade["pnl"] for trade in trades), 8)
        win_rate = len(winners) / len(trades)
        loss_rate = len(losers) / len(trades)
        average_win = (gross_profit / len(winners)) if winners else 0.0
        average_loss = (abs(sum(trade["pnl"] for trade in losers)) / len(losers)) if losers else 0.0
        expectancy = (win_rate * average_win) - (loss_rate * average_loss)
        average_r = self._average([trade["r_multiple"] for trade in trades])
        average_hold_time = self._average([trade["hold_time_minutes"] for trade in trades])
        max_drawdown, recovery_factor = self._drawdown_and_recovery(trades, total_pnl)
        consecutive_wins, consecutive_losses = self._consecutive_streaks(trades)

        asset_performance = self._group_performance(trades, "asset_class")
        strategy_performance = self._group_performance(trades, "strategy_id")
        regime_performance = self._group_performance(trades, "market_regime")
        trade_quality_distribution = self._trade_quality_distribution(trades)

        metrics = PerformanceMetrics(
            trade_count=len(trades),
            win_rate=round(win_rate, 8),
            profit_factor=round((gross_profit / gross_loss) if gross_loss > 0.0 else 0.0, 8),
            expectancy=round(expectancy, 8),
            average_r=round(average_r, 8),
            average_hold_time=round(average_hold_time, 8),
            max_drawdown=round(max_drawdown, 8),
            recovery_factor=round(recovery_factor, 8),
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            asset_performance=asset_performance,
            strategy_performance=strategy_performance,
            regime_performance=regime_performance,
            trade_quality_distribution=trade_quality_distribution,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            total_pnl=total_pnl,
        )
        return metrics.to_dict()

    def _normalize_trade(self, trade: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(trade, Mapping):
            raise PerformanceAnalyticsEngineError("each trade must be a mapping")

        trade_id = str(trade.get("trade_id") or "").strip()
        symbol = str(trade.get("symbol") or "").strip().upper()
        asset_class = str(trade.get("asset_class") or "UNKNOWN").strip().upper() or "UNKNOWN"
        strategy_id = str(trade.get("strategy_id") or trade.get("strategy") or "UNKNOWN").strip() or "UNKNOWN"
        market_regime = str(trade.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN"

        if not trade_id:
            raise PerformanceAnalyticsEngineError("trade_id must be non-empty")
        if not symbol:
            raise PerformanceAnalyticsEngineError("symbol must be non-empty")

        pnl = self._to_float(trade.get("realized_pnl", trade.get("pnl", 0.0)), "realized_pnl")
        hold_seconds = self._to_float(
            trade.get("holding_duration_seconds", trade.get("hold_time_seconds", 0.0)),
            "holding_duration_seconds",
        )
        if hold_seconds < 0.0:
            raise PerformanceAnalyticsEngineError("holding duration must be non-negative")

        quality_score = self._to_float(trade.get("quality_score", 0.0), "quality_score")
        if quality_score < 0.0 or quality_score > 100.0:
            raise PerformanceAnalyticsEngineError("quality_score must be between 0 and 100")

        risk_value = abs(self._to_float(trade.get("risk", trade.get("risk_amount", 0.0)), "risk"))
        if risk_value <= 0.0:
            risk_value = max(1.0, abs(pnl))
        r_multiple = pnl / risk_value if risk_value else 0.0

        return {
            "trade_id": trade_id,
            "symbol": symbol,
            "asset_class": asset_class,
            "strategy_id": strategy_id,
            "market_regime": market_regime,
            "pnl": round(pnl, 8),
            "hold_time_minutes": round(hold_seconds / 60.0, 8),
            "r_multiple": round(r_multiple, 8),
            "quality_score": round(quality_score, 8),
            "quality_bucket": self._quality_bucket(quality_score),
        }

    @staticmethod
    def _to_float(value: Any, field_name: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise PerformanceAnalyticsEngineError(f"{field_name} must be numeric") from exc

    @staticmethod
    def _average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _consecutive_streaks(trades: list[dict[str, Any]]) -> tuple[int, int]:
        wins = losses = best_wins = best_losses = 0
        for trade in trades:
            if trade["pnl"] > 0.0:
                wins += 1
                losses = 0
            elif trade["pnl"] < 0.0:
                losses += 1
                wins = 0
            else:
                wins = 0
                losses = 0
            best_wins = max(best_wins, wins)
            best_losses = max(best_losses, losses)
        return best_wins, best_losses

    @staticmethod
    def _drawdown_and_recovery(trades: list[dict[str, Any]], total_pnl: float) -> tuple[float, float]:
        equity = 0.0
        peak = 0.0
        drawdown = 0.0
        for trade in trades:
            equity += trade["pnl"]
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        recovery_factor = (total_pnl / drawdown) if drawdown > 0.0 else 0.0
        return drawdown, recovery_factor

    @staticmethod
    def _group_performance(trades: list[dict[str, Any]], field_name: str) -> dict[str, dict[str, float]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            grouped[str(trade[field_name])].append(trade)

        summary: dict[str, dict[str, float]] = {}
        for key in sorted(grouped.keys()):
            bucket = grouped[key]
            trade_count = len(bucket)
            pnl = sum(item["pnl"] for item in bucket)
            win_rate = sum(1 for item in bucket if item["pnl"] > 0.0) / trade_count if trade_count else 0.0
            summary[key] = {
                "trade_count": float(trade_count),
                "win_rate": round(win_rate, 8),
                "realized_pnl": round(pnl, 8),
            }
        return summary

    def _trade_quality_distribution(self, trades: list[dict[str, Any]]) -> dict[str, int]:
        counts = Counter(trade["quality_bucket"] for trade in trades)
        return {bucket: counts[bucket] for bucket in sorted(counts.keys())}

    def _quality_bucket(self, quality_score: float) -> str:
        for threshold, bucket in self._QUALITY_BUCKETS:
            if quality_score >= threshold:
                return bucket
        return "E"
