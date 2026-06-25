from __future__ import annotations

from typing import Any, Mapping

from .optimization_summary_report import OptimizationSummaryReport
from .performance_analytics_engine import PerformanceAnalyticsEngine
from .portfolio_optimization_engine import PortfolioOptimizationEngine
from .profitability_optimizer import ProfitabilityOptimizer


class AutonomousProfitabilityProgramError(RuntimeError):
    """Fail-closed exception for autonomous profitability optimization orchestration."""


class AutonomousProfitabilityProgram:
    """Single backend orchestration path for profitability and portfolio optimization."""

    def __init__(
        self,
        *,
        profitability_optimizer: ProfitabilityOptimizer | None = None,
        portfolio_optimizer: PortfolioOptimizationEngine | None = None,
        performance_engine: PerformanceAnalyticsEngine | None = None,
        summary_report: OptimizationSummaryReport | None = None,
    ) -> None:
        self.profitability_optimizer = profitability_optimizer or ProfitabilityOptimizer()
        self.portfolio_optimizer = portfolio_optimizer or PortfolioOptimizationEngine()
        self.performance_engine = performance_engine or PerformanceAnalyticsEngine()
        self.summary_report = summary_report or OptimizationSummaryReport()

    def optimize_cycle(
        self,
        *,
        completed_trades: list[Mapping[str, Any]] | None,
        strategy_league_table: list[Mapping[str, Any]] | None,
        position_context: list[Mapping[str, Any]] | None,
        allocation_rows: list[dict[str, Any]] | None,
        sizing_rows: list[dict[str, Any]] | None,
        strategy_rows: list[dict[str, Any]] | None,
        current_thresholds: Mapping[str, Any] | None = None,
        asset_class_exposure_limits: dict[str, float] | None = None,
        max_symbol_exposure: float = 1.0,
        max_total_allocation: float = 1.0,
        backtesting_results: Mapping[str, Any] | None = None,
        validation_results: Mapping[str, Any] | None = None,
        readiness_assessment: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if completed_trades is not None and not isinstance(completed_trades, list):
            raise AutonomousProfitabilityProgramError("completed_trades must be a list when provided")
        if strategy_league_table is not None and not isinstance(strategy_league_table, list):
            raise AutonomousProfitabilityProgramError("strategy_league_table must be a list when provided")
        if position_context is not None and not isinstance(position_context, list):
            raise AutonomousProfitabilityProgramError("position_context must be a list when provided")

        trades = list(completed_trades or [])
        league = list(strategy_league_table or [])
        positions = list(position_context or [])

        optimization_package = self.profitability_optimizer.optimize(
            completed_trades=trades,
            strategy_league_table=league,
            position_context=positions,
            current_thresholds=current_thresholds,
        )

        performance_metrics = self.performance_engine.analyze(trades)

        exposure_limits = dict(asset_class_exposure_limits or {"UNKNOWN": max(1.0, float(max_total_allocation))})
        portfolio_recommendations = self.portfolio_optimizer.optimize(
            list(allocation_rows or []),
            list(sizing_rows or []),
            list(strategy_rows or []),
            asset_class_exposure_limits=exposure_limits,
            max_symbol_exposure=float(max_symbol_exposure),
            max_total_allocation=float(max_total_allocation),
        )

        portfolio_summary = self._portfolio_summary(portfolio_recommendations)
        package_with_portfolio = {
            **optimization_package,
            "portfolio_summary": portfolio_summary,
            "metadata": {
                **dict(optimization_package.get("metadata", {})),
                "best_strategy": self._best_strategy(optimization_package),
                "expectancy": performance_metrics.get("expectancy", 0.0),
                "expected_return": optimization_package.get("estimated_improvement", 0.0),
                "profit_factor": performance_metrics.get("profit_factor", 0.0),
                "sharpe_ratio": self._safe_divide(
                    performance_metrics.get("expectancy", 0.0),
                    abs(performance_metrics.get("max_drawdown", 0.0)) + 1e-9,
                ),
                "sortino_ratio": self._safe_divide(
                    performance_metrics.get("expectancy", 0.0),
                    abs(performance_metrics.get("gross_loss", 0.0)) + 1e-9,
                ),
                "max_drawdown": abs(float(performance_metrics.get("max_drawdown", 0.0) or 0.0)),
                "learning_confidence": optimization_package.get("confidence_score", 0.0),
                "capital_efficiency": portfolio_summary["capital_efficiency"],
                "market_regime": self._dominant_regime(performance_metrics),
                "optimization_score": self._optimization_score(
                    confidence=optimization_package.get("confidence_score", 0.0),
                    profit_factor=performance_metrics.get("profit_factor", 0.0),
                    capital_efficiency=portfolio_summary["capital_efficiency"],
                ),
            },
            "recommended_improvements": self._recommended_improvements(
                optimization_package,
                portfolio_recommendations,
            ),
        }

        report = self.summary_report.build(
            optimization_package=package_with_portfolio,
            backtesting_results=dict(backtesting_results or {"backtest_decision": "ACCEPT", "performance_summary": {}}),
            validation_results=dict(validation_results or {"summary": {"SAFE": 0, "REVIEW": 0, "REJECT": 0}}),
            readiness_assessment=dict(readiness_assessment or {"readiness": "READY"}),
        )

        return {
            "optimization_package": package_with_portfolio,
            "performance_metrics": performance_metrics,
            "portfolio_recommendations": portfolio_recommendations,
            "portfolio_summary": portfolio_summary,
            "optimization_report": report,
            "unified_optimization_summary": report.get("optimization_summary", {}),
        }

    def _portfolio_summary(self, recommendations: list[dict[str, Any]]) -> dict[str, Any]:
        approved = sum(1 for row in recommendations if str(row.get("portfolio_status") or "").upper() == "APPROVED")
        reduced = sum(1 for row in recommendations if str(row.get("portfolio_status") or "").upper() == "REDUCED")
        blocked = sum(
            1
            for row in recommendations
            if str(row.get("portfolio_status") or "").upper() in {"BLOCKED", "RESTRICTED"}
        )
        total = len(recommendations)
        total_size = sum(float(row.get("recommended_position_size", 0.0) or 0.0) for row in recommendations)
        efficiency = self._safe_divide(approved + (0.5 * reduced), total if total > 0 else 1)

        health = "HEALTHY"
        if blocked > 0 and blocked >= max(1, total // 2):
            health = "STRESSED"
        elif reduced > 0:
            health = "CONSTRAINED"

        return {
            "approved_count": approved,
            "reduced_count": reduced,
            "blocked_count": blocked,
            "total_recommendations": total,
            "total_recommended_size": round(total_size, 8),
            "capital_efficiency": round(efficiency, 8),
            "portfolio_health": health,
        }

    @staticmethod
    def _best_strategy(optimization_package: Mapping[str, Any]) -> str:
        for row in optimization_package.get("recommended_strategy_changes", []):
            if not isinstance(row, Mapping):
                continue
            recommendation = str(row.get("recommendation") or "").upper()
            if recommendation in {"PROMOTE", "EXECUTE", "PREFERRED"}:
                strategy_id = str(row.get("strategy_id") or "").strip()
                if strategy_id:
                    return strategy_id
        return "UNKNOWN"

    @staticmethod
    def _recommended_improvements(
        optimization_package: Mapping[str, Any],
        portfolio_recommendations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        improvements: list[dict[str, Any]] = []

        for row in optimization_package.get("recommended_strategy_changes", []):
            if isinstance(row, Mapping):
                recommendation = str(row.get("recommendation") or "").upper()
                if recommendation in {"PROMOTE", "DEMOTE", "DISABLE"}:
                    improvements.append(dict(row))

        for row in portfolio_recommendations:
            status = str(row.get("portfolio_status") or "").upper()
            if status in {"REDUCED", "BLOCKED", "RESTRICTED"}:
                improvements.append(
                    {
                        "symbol": row.get("symbol"),
                        "recommendation": status,
                        "reason": row.get("optimization_reason"),
                    }
                )

        return improvements

    @staticmethod
    def _dominant_regime(performance_metrics: Mapping[str, Any]) -> str:
        regime_performance = performance_metrics.get("regime_performance", {})
        if not isinstance(regime_performance, Mapping) or not regime_performance:
            return "UNKNOWN"

        def _score(item: tuple[str, Any]) -> tuple[float, float, str]:
            key, payload = item
            if isinstance(payload, Mapping):
                pnl = float(payload.get("realized_pnl", 0.0) or 0.0)
                trades = float(payload.get("trade_count", 0.0) or 0.0)
                return pnl, trades, str(key)
            return 0.0, 0.0, str(key)

        best = sorted(regime_performance.items(), key=_score, reverse=True)[0][0]
        return str(best).upper()

    @staticmethod
    def _optimization_score(*, confidence: Any, profit_factor: Any, capital_efficiency: Any) -> float:
        conf = max(0.0, min(1.0, float(confidence or 0.0)))
        pf = max(0.0, float(profit_factor or 0.0))
        efficiency = max(0.0, min(1.0, float(capital_efficiency or 0.0)))
        return round((conf * 0.4) + (min(2.0, pf) / 2.0 * 0.4) + (efficiency * 0.2), 8)

    @staticmethod
    def _safe_divide(numerator: Any, denominator: Any) -> float:
        try:
            num = float(numerator)
            den = float(denominator)
        except (TypeError, ValueError):
            return 0.0
        if den == 0.0:
            return 0.0
        return round(num / den, 8)
