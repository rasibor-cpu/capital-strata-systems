from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import combinations
from typing import Any

from backend.portfolio.opportunity_portfolio_ranker import normalize_opportunities
from backend.portfolio.portfolio_resilience_analyzer import PortfolioResilienceAnalyzer
from backend.portfolio.utils import safe_float


class PortfolioEfficiencyFrontier:
    """Construct an advisory efficient frontier from approved opportunities and rank portfolios."""

    def __init__(self, *, analyzer: PortfolioResilienceAnalyzer | None = None) -> None:
        self.analyzer = analyzer or PortfolioResilienceAnalyzer()

    def construct_frontier(
        self,
        opportunities: Iterable[Mapping[str, Any]] | None,
        *,
        max_positions: int | None = None,
        min_positions: int = 1,
    ) -> dict[str, Any]:
        normalized = normalize_opportunities(opportunities)
        if not normalized:
            return {
                "status": "DATA UNAVAILABLE",
                "efficient_portfolios": [],
                "rankings": {
                    "by_return": [],
                    "by_risk": [],
                    "by_efficiency": [],
                    "by_resilience": [],
                },
            }

        upper = min(len(normalized), max_positions or min(len(normalized), 5))
        lower = upper if max_positions is not None else max(1, min(max(3, min_positions), upper))

        # Generate all candidates
        candidates = []
        for size in range(lower, upper + 1):
            for subset in combinations(normalized, size):
                subset_list = list(subset)
                analysis = self.analyzer.analyze(subset_list)
                if analysis.get("status") != "OK":
                    continue

                expected_return = safe_float(analysis.get("expected_return"))
                expected_volatility = safe_float(analysis.get("expected_volatility"))
                expected_drawdown = safe_float(analysis.get("expected_drawdown"))
                resilience = safe_float(analysis.get("resilience"))
                sharpe = expected_return / expected_volatility if expected_volatility > 0.0 else 0.0
                sortino = expected_return / expected_drawdown if expected_drawdown > 0.0 else 0.0
                quality = safe_float(analysis.get("portfolio_quality"))

                candidates.append({
                    "opportunities": [item["opportunity_id"] for item in subset_list],
                    "symbols": [item["symbol"] for item in subset_list],
                    "expected_return": expected_return,
                    "expected_volatility": expected_volatility,
                    "expected_drawdown": expected_drawdown,
                    "resilience": resilience,
                    "sharpe": sharpe,
                    "sortino": sortino,
                    "quality": quality,
                })

        # Identify efficient portfolios (Pareto frontier on return and volatility)
        efficient = []
        for c1 in candidates:
            dominated = False
            for c2 in candidates:
                if c1 is c2:
                    continue
                # c2 dominates c1 if c2 has higher return and lower or equal risk
                # or same return and strictly lower risk.
                if (c2["expected_return"] >= c1["expected_return"] and c2["expected_volatility"] <= c1["expected_volatility"]) and \
                   (c2["expected_return"] > c1["expected_return"] or c2["expected_volatility"] < c1["expected_volatility"]):
                    dominated = True
                    break
            if not dominated:
                efficient.append(c1)

        # Keep unique efficient portfolios
        unique_efficient = []
        seen = set()
        for p in efficient:
            key = tuple(sorted(p["opportunities"]))
            if key not in seen:
                seen.add(key)
                unique_efficient.append(p)

        # Rank the efficient portfolios by the four parameters
        by_return = sorted(unique_efficient, key=lambda item: (-item["expected_return"], tuple(sorted(item["opportunities"]))))
        by_risk = sorted(unique_efficient, key=lambda item: (item["expected_volatility"], tuple(sorted(item["opportunities"]))))
        by_efficiency = sorted(unique_efficient, key=lambda item: (-item["sharpe"], tuple(sorted(item["opportunities"]))))
        by_resilience = sorted(unique_efficient, key=lambda item: (-item["resilience"], tuple(sorted(item["opportunities"]))))

        # Format items
        def format_portfolio_item(p):
            return {
                "constituents": p["opportunities"],
                "symbols": p["symbols"],
                "expected_return": round(p["expected_return"], 6),
                "expected_volatility": round(p["expected_volatility"], 6),
                "expected_drawdown": round(p["expected_drawdown"], 6),
                "sharpe": round(p["sharpe"], 6),
                "sortino": round(p["sortino"], 6),
                "resilience": round(p["resilience"], 6),
                "quality": round(p["quality"], 6),
            }

        return {
            "status": "OK",
            "efficient_portfolios": [format_portfolio_item(p) for p in unique_efficient],
            "rankings": {
                "by_return": [format_portfolio_item(p) for p in by_return],
                "by_risk": [format_portfolio_item(p) for p in by_risk],
                "by_efficiency": [format_portfolio_item(p) for p in by_efficiency],
                "by_resilience": [format_portfolio_item(p) for p in by_resilience],
            },
        }
