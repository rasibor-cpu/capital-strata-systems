from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.portfolio.portfolio_scenario_generator import PortfolioScenarioGenerator
from backend.portfolio.portfolio_tradeoff_analyzer import PortfolioTradeoffAnalyzer
from backend.portfolio.portfolio_efficiency_frontier import PortfolioEfficiencyFrontier
from backend.portfolio.utils import advisory_response


class InstitutionalPortfolioOptimizer:
    """Orchestrate scenario generation, tradeoff analysis, and efficient frontier construction for institutional portfolios."""

    def __init__(
        self,
        *,
        generator: PortfolioScenarioGenerator | None = None,
        analyzer: PortfolioTradeoffAnalyzer | None = None,
        frontier: PortfolioEfficiencyFrontier | None = None,
    ) -> None:
        self.generator = generator or PortfolioScenarioGenerator()
        self.analyzer = analyzer or PortfolioTradeoffAnalyzer()
        self.frontier = frontier or PortfolioEfficiencyFrontier()

    def optimize(
        self,
        opportunities: Iterable[Mapping[str, Any]] | None,
        *,
        max_positions: int | None = None,
        min_positions: int = 1,
    ) -> dict[str, Any]:
        try:
            # Generate scenarios
            scenario_res = self.generator.generate_scenarios(
                opportunities, max_positions=max_positions, min_positions=min_positions
            )
            if scenario_res.get("status") != "OK":
                return self._fail_closed(scenario_res.get("reasons", ["scenario_generation_failed"]))

            scenarios = scenario_res.get("scenarios", {})
            recommended_portfolios = []
            best_overall = None
            best_quality = -1.0

            for name in ["Conservative", "Balanced", "Growth", "Income", "High Sharpe", "High Sortino"]:
                p = scenarios.get(name)
                if not p:
                    continue
                recommended_portfolios.append({
                    "name": p["name"],
                    "quality_score": p["portfolio_quality_score"],
                    "expected_return": p["expected_return"],
                    "expected_volatility": p["expected_volatility"],
                    "expected_drawdown": p["expected_drawdown"],
                    "sharpe": p["sharpe"],
                    "sortino": p["sortino"],
                    "portfolio_beta": p["portfolio_beta"],
                    "diversification_score": p["diversification_score"],
                    "resilience_score": p["resilience_score"],
                    "concentration_score": p["concentration_score"],
                    "capital_efficiency_score": p["capital_efficiency_score"],
                    "opportunities": p["opportunities"],
                    "advisory_only": True,
                    "execution_allowed": False,
                })

                if p["portfolio_quality_score"] > best_quality:
                    best_quality = p["portfolio_quality_score"]
                    best_overall = name

            # Analyze tradeoffs
            tradeoffs = self.analyzer.analyze_tradeoffs(scenarios)

            # Construct frontier
            frontier_res = self.frontier.construct_frontier(
                opportunities, max_positions=max_positions, min_positions=min_positions
            )

            return advisory_response(
                "OK",
                recommended_portfolios=recommended_portfolios,
                best_overall=best_overall or "DATA UNAVAILABLE",
                tradeoffs=tradeoffs,
                efficient_frontier=frontier_res.get("efficient_portfolios", []),
                frontier_rankings=frontier_res.get("rankings", {}),
                reasons=["institutional_portfolio_optimization_completed"],
                live_trading_blocked=True,
                broker_execution_armed=False,
            )

        except Exception as exc:  # noqa: BLE001 - must fail closed
            return self._fail_closed([f"optimization_exception:{exc.__class__.__name__}"])

    @staticmethod
    def _fail_closed(reasons: list[str]) -> dict[str, Any]:
        return advisory_response(
            "DATA UNAVAILABLE",
            recommended_portfolios=[],
            best_overall="DATA UNAVAILABLE",
            tradeoffs=[],
            efficient_frontier=[],
            frontier_rankings={
                "by_return": [],
                "by_risk": [],
                "by_efficiency": [],
                "by_resilience": [],
            },
            reasons=reasons,
            live_trading_blocked=True,
            broker_execution_armed=False,
        )
