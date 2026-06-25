from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Mapping, Sequence

from .trade_outcome_repository import TradeOutcomeRepository, TradeOutcomeRepositoryError


class StrategyEvolutionEngineError(RuntimeError):
    """Fail-closed exception for adaptive strategy evolution recommendations."""


class StrategyEvolutionEngine:
    """Recommendation-only engine for strategy lifecycle and allocation guidance."""

    _WINDOWS: tuple[int | str, ...] = (20, 50, 100, "lifetime")
    _REGIME_BUCKETS = ("BULL", "BEAR", "SIDEWAYS", "HIGH_VOLATILITY", "LOW_VOLATILITY", "UNKNOWN")

    def __init__(
        self,
        repository: TradeOutcomeRepository,
        *,
        minimum_history: int = 20,
    ) -> None:
        if minimum_history <= 0:
            raise StrategyEvolutionEngineError("minimum_history must be positive")
        self.repository = repository
        self.minimum_history = int(minimum_history)

    def evolve(
        self,
        *,
        completed_trades: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        trades = self._load_trades(completed_trades)
        registry = self._build_strategy_registry(trades)

        if len(trades) < self.minimum_history or not registry:
            return {
                "status": "INSUFFICIENT_DATA",
                "minimum_history": self.minimum_history,
                "lifetime_trade_count": len(trades),
                "strategy_registry": registry,
                "rankings": [],
                "promotions": [],
                "retirements": [],
                "recommended_strategy_weights": {},
                "explainability": [],
            }

        rankings = self._rank_strategies(registry)
        promotions = self._promotion_actions(rankings)
        weights = self._recommended_weights(rankings)
        explainability = self._explainability(rankings, promotions)

        top_strategies = [row for row in rankings if row["trend"] != "DECLINING"][:5]
        declining = [row for row in rankings if row["trend"] == "DECLINING"][:5]
        retirements = [row for row in promotions if row["action"] == "RETIRE_STRATEGY"]

        return {
            "status": "OK",
            "minimum_history": self.minimum_history,
            "lifetime_trade_count": len(trades),
            "strategy_registry": registry,
            "rankings": rankings,
            "top_strategies": top_strategies,
            "declining_strategies": declining,
            "promotions": promotions,
            "retirements": retirements,
            "recommended_strategy_weights": weights,
            "explainability": explainability,
        }

    def _load_trades(self, completed_trades: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        if completed_trades is not None:
            rows = [dict(item) for item in completed_trades]
        else:
            try:
                rows = self.repository.load_outcomes()
            except TradeOutcomeRepositoryError as exc:
                raise StrategyEvolutionEngineError(f"Unable to load completed trades: {exc}") from exc

        normalized: list[dict[str, Any]] = []
        for row in rows:
            strategy_id = str(row.get("strategy_id") or "").strip()
            if not strategy_id:
                continue
            normalized.append(
                {
                    "strategy_id": strategy_id,
                    "asset_class": str(row.get("asset_class") or "UNKNOWN").strip().upper() or "UNKNOWN",
                    "market_regime": self._normalize_regime(str(row.get("market_regime") or "UNKNOWN")),
                    "realized_pnl": float(row.get("realized_pnl", 0.0) or 0.0),
                    "holding_duration_seconds": float(row.get("holding_duration_seconds", 0.0) or 0.0),
                }
            )
        return normalized

    def _build_strategy_registry(self, trades: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in trades:
            strategy_id = str(row.get("strategy_id") or "").strip()
            grouped.setdefault(strategy_id, []).append(dict(row))

        registry: list[dict[str, Any]] = []
        for strategy_id in sorted(grouped.keys()):
            rows = grouped[strategy_id]
            lifetime_stats = self._performance_stats(rows)
            rolling_windows = self._rolling_window_stats(rows)
            trend = self._performance_trend(rolling_windows)
            regime_adaptation = self._regime_adaptation(rows)
            confidence = self._confidence(lifetime_stats, rolling_windows.get("20", {}))

            registry.append(
                {
                    "strategy_name": strategy_id,
                    "asset_class": self._dominant_asset_class(rows),
                    "trades": int(lifetime_stats["trades"]),
                    "wins": int(lifetime_stats["wins"]),
                    "losses": int(lifetime_stats["losses"]),
                    "average_return": float(lifetime_stats["average_return"]),
                    "average_duration": float(lifetime_stats["average_duration"]),
                    "profit_factor": float(lifetime_stats["profit_factor"]),
                    "expectancy": float(lifetime_stats["expectancy"]),
                    "sharpe_estimate": float(lifetime_stats["sharpe_estimate"]),
                    "maximum_drawdown": float(lifetime_stats["maximum_drawdown"]),
                    "recovery_factor": float(lifetime_stats["recovery_factor"]),
                    "current_confidence": float(confidence),
                    "rolling_windows": rolling_windows,
                    "performance_trend": trend,
                    "recommended_regimes": regime_adaptation["recommended_regimes"],
                    "avoided_regimes": regime_adaptation["avoided_regimes"],
                    "regime_performance": regime_adaptation["regime_performance"],
                }
            )
        return registry

    def _rolling_window_stats(self, rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        ordered = list(rows)
        for window in self._WINDOWS:
            key = str(window)
            if window == "lifetime":
                sample = ordered
            else:
                size = int(window)
                sample = ordered[-size:] if len(ordered) >= size else ordered

            stats = self._performance_stats(sample)
            if window != "lifetime" and len(ordered) < int(window):
                stats["status"] = "INSUFFICIENT_DATA"
            else:
                stats["status"] = "OK"
            output[key] = stats
        return output

    @staticmethod
    def _performance_stats(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "average_return": 0.0,
                "average_duration": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "sharpe_estimate": 0.0,
                "maximum_drawdown": 0.0,
                "recovery_factor": 0.0,
            }

        pnls = [float(row.get("realized_pnl", 0.0) or 0.0) for row in rows]
        durations = [float(row.get("holding_duration_seconds", 0.0) or 0.0) for row in rows]
        wins = [value for value in pnls if value > 0.0]
        losses = [abs(value) for value in pnls if value < 0.0]

        trade_count = len(pnls)
        win_count = len(wins)
        loss_count = len(losses)
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        avg_return = mean(pnls)
        avg_duration = mean(durations) if durations else 0.0

        win_rate = win_count / max(1, trade_count)
        loss_rate = loss_count / max(1, trade_count)
        avg_win = gross_profit / max(1, win_count)
        avg_loss = gross_loss / max(1, loss_count)
        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

        volatility = pstdev(pnls) if len(pnls) > 1 else 0.0
        sharpe = 0.0 if volatility == 0 else (avg_return / volatility) * math.sqrt(trade_count)

        cumulative = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for pnl in pnls:
            cumulative += pnl
            peak = max(peak, cumulative)
            max_drawdown = max(max_drawdown, peak - cumulative)

        net_profit = sum(pnls)
        recovery_factor = net_profit if max_drawdown <= 0 else net_profit / max_drawdown
        profit_factor = gross_profit if gross_loss <= 0 else gross_profit / gross_loss

        return {
            "trades": trade_count,
            "wins": win_count,
            "losses": loss_count,
            "average_return": round(avg_return, 8),
            "average_duration": round(avg_duration, 8),
            "profit_factor": round(profit_factor, 8),
            "expectancy": round(expectancy, 8),
            "sharpe_estimate": round(sharpe, 8),
            "maximum_drawdown": round(max_drawdown, 8),
            "recovery_factor": round(recovery_factor, 8),
            "win_rate": round(win_rate, 8),
            "volatility": round(volatility, 8),
            "net_profit": round(net_profit, 8),
        }

    @staticmethod
    def _performance_trend(rolling_windows: Mapping[str, Mapping[str, Any]]) -> str:
        recent = float(rolling_windows.get("20", {}).get("average_return", 0.0) or 0.0)
        medium = float(rolling_windows.get("50", {}).get("average_return", 0.0) or 0.0)
        baseline = float(rolling_windows.get("lifetime", {}).get("average_return", 0.0) or 0.0)

        delta = recent - ((medium + baseline) / 2.0)
        if delta > 0.05:
            return "IMPROVING"
        if delta < -0.05:
            return "DECLINING"
        return "STABLE"

    def _regime_adaptation(self, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in self._REGIME_BUCKETS}
        for row in rows:
            regime = self._normalize_regime(str(row.get("market_regime") or "UNKNOWN"))
            buckets.setdefault(regime, []).append(dict(row))

        regime_stats: list[dict[str, Any]] = []
        for regime in self._REGIME_BUCKETS:
            stats = self._performance_stats(buckets.get(regime, []))
            regime_stats.append(
                {
                    "regime": regime,
                    "trades": int(stats["trades"]),
                    "expectancy": float(stats["expectancy"]),
                    "win_rate": float(stats.get("win_rate", 0.0)),
                    "average_return": float(stats["average_return"]),
                }
            )

        recommended = [row["regime"] for row in regime_stats if row["trades"] >= 3 and row["expectancy"] > 0.0]
        avoided = [row["regime"] for row in regime_stats if row["trades"] >= 3 and row["expectancy"] < 0.0]

        return {
            "regime_performance": regime_stats,
            "recommended_regimes": recommended,
            "avoided_regimes": avoided,
        }

    @staticmethod
    def _dominant_asset_class(rows: Sequence[Mapping[str, Any]]) -> str:
        counts: dict[str, int] = {}
        for row in rows:
            key = str(row.get("asset_class") or "UNKNOWN").strip().upper() or "UNKNOWN"
            counts[key] = counts.get(key, 0) + 1
        if not counts:
            return "UNKNOWN"
        return sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]

    @staticmethod
    def _confidence(lifetime_stats: Mapping[str, Any], recent_stats: Mapping[str, Any]) -> float:
        trades = int(lifetime_stats.get("trades", 0) or 0)
        win_rate = float(lifetime_stats.get("win_rate", 0.0) or 0.0)
        sharpe = float(lifetime_stats.get("sharpe_estimate", 0.0) or 0.0)
        recent_expectancy = float(recent_stats.get("expectancy", 0.0) or 0.0)

        sample_score = min(1.0, trades / 100.0)
        sharpe_score = max(0.0, min((sharpe + 2.0) / 4.0, 1.0))
        expectancy_score = max(0.0, min((recent_expectancy + 1.0) / 2.0, 1.0))
        confidence = (sample_score * 0.35) + (win_rate * 0.25) + (sharpe_score * 0.20) + (expectancy_score * 0.20)
        return round(max(0.0, min(confidence, 1.0)), 8)

    def _rank_strategies(self, registry: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for row in registry:
            rolling = row.get("rolling_windows", {})
            lifetime = rolling.get("lifetime", {}) if isinstance(rolling, Mapping) else {}
            recent = rolling.get("20", {}) if isinstance(rolling, Mapping) else {}
            trend = str(row.get("performance_trend") or "STABLE")

            overall_score = self._composite_score(
                expectancy=float(lifetime.get("expectancy", 0.0) or 0.0),
                sharpe=float(lifetime.get("sharpe_estimate", 0.0) or 0.0),
                drawdown=float(lifetime.get("maximum_drawdown", 0.0) or 0.0),
                confidence=float(row.get("current_confidence", 0.0) or 0.0),
                trend=trend,
            )
            current_score = self._composite_score(
                expectancy=float(recent.get("expectancy", 0.0) or 0.0),
                sharpe=float(recent.get("sharpe_estimate", 0.0) or 0.0),
                drawdown=float(recent.get("maximum_drawdown", 0.0) or 0.0),
                confidence=float(row.get("current_confidence", 0.0) or 0.0),
                trend=trend,
            )

            ranked.append(
                {
                    "strategy_name": str(row.get("strategy_name") or ""),
                    "asset_class": str(row.get("asset_class") or "UNKNOWN"),
                    "overall_score": round(overall_score, 8),
                    "current_score": round(current_score, 8),
                    "confidence": float(row.get("current_confidence", 0.0) or 0.0),
                    "trend": trend,
                    "expectancy": float(lifetime.get("expectancy", 0.0) or 0.0),
                    "supporting_statistics": {
                        "lifetime": lifetime,
                        "recent_20": recent,
                        "recommended_regimes": row.get("recommended_regimes", []),
                        "avoided_regimes": row.get("avoided_regimes", []),
                    },
                }
            )

        ranked.sort(
            key=lambda item: (
                float(item.get("overall_score", 0.0)),
                float(item.get("current_score", 0.0)),
                float(item.get("confidence", 0.0)),
                str(item.get("strategy_name", "")),
            ),
            reverse=True,
        )

        weights = self._recommended_weights(ranked)
        for item in ranked:
            strategy = str(item.get("strategy_name") or "")
            weight = float(weights.get(strategy, 0.0) or 0.0)
            item["recommended_weight"] = round(weight, 8)
            item["expected_contribution"] = round(weight * float(item.get("expectancy", 0.0) or 0.0), 8)

        return ranked

    @staticmethod
    def _composite_score(*, expectancy: float, sharpe: float, drawdown: float, confidence: float, trend: str) -> float:
        expectancy_score = max(0.0, min((expectancy + 1.0) / 2.0, 1.0))
        sharpe_score = max(0.0, min((sharpe + 2.0) / 4.0, 1.0))
        drawdown_penalty = max(0.0, min(drawdown / 10.0, 1.0))
        trend_bonus = 0.1 if trend == "IMPROVING" else (-0.1 if trend == "DECLINING" else 0.0)

        score = (expectancy_score * 0.4) + (sharpe_score * 0.25) + (confidence * 0.25) + (0.1 * (1.0 - drawdown_penalty))
        return max(0.0, min(score + trend_bonus, 1.0))

    @staticmethod
    def _recommended_weights(rankings: Sequence[Mapping[str, Any]]) -> dict[str, float]:
        positives = [max(0.0, float(row.get("overall_score", 0.0) or 0.0)) for row in rankings]
        total = sum(positives)
        if total <= 0:
            return {str(row.get("strategy_name") or ""): 0.0 for row in rankings}

        output: dict[str, float] = {}
        for row, score in zip(rankings, positives):
            key = str(row.get("strategy_name") or "")
            output[key] = round(score / total, 8)
        return output

    @staticmethod
    def _promotion_actions(rankings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for row in rankings:
            strategy = str(row.get("strategy_name") or "")
            overall = float(row.get("overall_score", 0.0) or 0.0)
            current = float(row.get("current_score", 0.0) or 0.0)
            trend = str(row.get("trend") or "STABLE")
            expectancy = float(row.get("expectancy", 0.0) or 0.0)

            if trend == "DECLINING" and current < 0.25 and expectancy < 0.0:
                action = "RETIRE_STRATEGY"
                reason = "Declining trend with negative expectancy and weak current score."
            elif trend == "DECLINING" or current < 0.4:
                action = "REDUCE_ALLOCATION"
                reason = "Recent performance is weaker than baseline."
            elif trend == "IMPROVING" and current >= 0.6 and overall >= 0.55:
                action = "INCREASE_ALLOCATION"
                reason = "Improving trend with strong current and overall score."
            else:
                action = "MAINTAIN_ALLOCATION"
                reason = "Performance remains stable relative to baseline."

            actions.append(
                {
                    "strategy_name": strategy,
                    "action": action,
                    "reason": reason,
                    "confidence": float(row.get("confidence", 0.0) or 0.0),
                    "trend": trend,
                }
            )
        return actions

    @staticmethod
    def _explainability(
        rankings: Sequence[Mapping[str, Any]],
        promotions: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        action_by_strategy = {str(item.get("strategy_name") or ""): item for item in promotions}
        output: list[dict[str, Any]] = []
        for row in rankings:
            strategy = str(row.get("strategy_name") or "")
            action = action_by_strategy.get(strategy, {})
            output.append(
                {
                    "strategy_name": strategy,
                    "recommendation": str(action.get("action") or "MAINTAIN_ALLOCATION"),
                    "performance_trend": str(row.get("trend") or "STABLE"),
                    "reason": str(action.get("reason") or "No recommendation reason available."),
                    "confidence": float(row.get("confidence", 0.0) or 0.0),
                    "supporting_statistics": row.get("supporting_statistics", {}),
                }
            )
        return output

    @staticmethod
    def _normalize_regime(regime: str) -> str:
        value = str(regime or "").strip().upper()
        if not value:
            return "UNKNOWN"

        if "BULL" in value or value in {"RISK_ON", "TRENDING_UP", "UP"}:
            return "BULL"
        if "BEAR" in value or value in {"RISK_OFF", "TRENDING_DOWN", "DOWN"}:
            return "BEAR"
        if "SIDE" in value or value in {"RANGING", "RANGE", "FLAT"}:
            return "SIDEWAYS"
        if "HIGH" in value and "VOL" in value:
            return "HIGH_VOLATILITY"
        if "LOW" in value and "VOL" in value:
            return "LOW_VOLATILITY"
        return "UNKNOWN"
