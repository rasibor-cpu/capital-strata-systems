from __future__ import annotations

from typing import Any, Mapping


class OptimizationBacktestingEngineError(RuntimeError):
    """Fail-closed exception for optimization backtesting."""


class OptimizationBacktestingEngine:
    """Replay recommendation effects against historical evidence."""

    def backtest(
        self,
        historical_trades: list[Mapping[str, Any]] | None,
        optimization_package: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if historical_trades is not None and not isinstance(historical_trades, list):
            raise OptimizationBacktestingEngineError("historical_trades must be a list when provided")
        if optimization_package is not None and not isinstance(optimization_package, Mapping):
            raise OptimizationBacktestingEngineError("optimization_package must be a mapping when provided")

        trades = [self._normalize_trade(trade) for trade in (historical_trades or [])]
        if not trades:
            return {
                "baseline_expectancy": 0.0,
                "optimized_expectancy": 0.0,
                "baseline_drawdown": 0.0,
                "optimized_drawdown": 0.0,
                "win_rate_delta": 0.0,
                "profit_factor_delta": 0.0,
                "trade_frequency_delta": 0.0,
                "backtest_decision": "REJECT",
                "reason": "no_historical_trades",
            }

        package = dict(optimization_package or {})
        baseline = self._metrics(trades)
        optimized_trades = self._apply_recommendations(trades, package)
        optimized = self._metrics(optimized_trades)

        decision = "ACCEPT"
        reason = "optimized_improves_or_holds"
        if optimized["expectancy"] < baseline["expectancy"] or optimized["drawdown"] > baseline["drawdown"]:
            decision = "REJECT"
            reason = "worsened_performance"

        return {
            "baseline_expectancy": round(baseline["expectancy"], 8),
            "optimized_expectancy": round(optimized["expectancy"], 8),
            "baseline_drawdown": round(baseline["drawdown"], 8),
            "optimized_drawdown": round(optimized["drawdown"], 8),
            "win_rate_delta": round(optimized["win_rate"] - baseline["win_rate"], 8),
            "profit_factor_delta": round(optimized["profit_factor"] - baseline["profit_factor"], 8),
            "trade_frequency_delta": round(optimized["trade_frequency"] - baseline["trade_frequency"], 8),
            "backtest_decision": decision,
            "reason": reason,
        }

    def _apply_recommendations(self, trades: list[dict[str, Any]], package: Mapping[str, Any]) -> list[dict[str, Any]]:
        sizing = package.get("recommended_sizing_changes", [])
        if not isinstance(sizing, list):
            sizing = []
        sizing_map = {
            (str(row.get("strategy_id", "")), str(row.get("market_regime", ""))): row
            for row in sizing
            if isinstance(row, Mapping)
        }

        output: list[dict[str, Any]] = []
        for trade in trades:
            key = (trade["strategy_id"], trade["market_regime"])
            row = dict(sizing_map.get(key, {}))
            action = str(row.get("action", "KEEP"))
            multiplier = 1.0
            if action == "INCREASE":
                multiplier = 1.10
            elif action == "REDUCE":
                multiplier = 0.85

            adjusted = dict(trade)
            adjusted["pnl"] = round(trade["pnl"] * multiplier, 8)
            output.append(adjusted)
        return output

    def _metrics(self, trades: list[dict[str, Any]]) -> dict[str, float]:
        if not trades:
            return {"expectancy": 0.0, "drawdown": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "trade_frequency": 0.0}

        total_pnl = sum(row["pnl"] for row in trades)
        wins = [row for row in trades if row["pnl"] > 0.0]
        losses = [row for row in trades if row["pnl"] < 0.0]
        gross_profit = sum(row["pnl"] for row in wins)
        gross_loss = abs(sum(row["pnl"] for row in losses))
        win_rate = len(wins) / len(trades)
        expectancy = total_pnl / len(trades)

        equity = 0.0
        peak = 0.0
        drawdown = 0.0
        for row in trades:
            equity += row["pnl"]
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)

        return {
            "expectancy": expectancy,
            "drawdown": drawdown,
            "win_rate": win_rate,
            "profit_factor": (gross_profit / gross_loss) if gross_loss > 0.0 else 0.0,
            "trade_frequency": float(len(trades)),
        }

    @staticmethod
    def _normalize_trade(payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise OptimizationBacktestingEngineError("each historical trade must be a mapping")
        return {
            "strategy_id": str(payload.get("strategy_id") or payload.get("strategy") or "UNKNOWN").strip() or "UNKNOWN",
            "market_regime": str(payload.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN",
            "pnl": OptimizationBacktestingEngine._to_float(payload.get("realized_pnl", payload.get("pnl", 0.0))),
        }

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
