from __future__ import annotations

from typing import Any


class PortfolioTradeoffAnalyzer:
    """Analyze differences and tradeoffs between generated institutional portfolios."""

    def analyze_tradeoffs(self, portfolios: dict[str, dict[str, Any]]) -> list[str]:
        tradeoffs = []
        if not portfolios:
            return tradeoffs

        # Compare profiles if they exist
        balanced = portfolios.get("Balanced")
        conservative = portfolios.get("Conservative")
        growth = portfolios.get("Growth")
        income = portfolios.get("Income")
        sharpe = portfolios.get("High Sharpe")
        sortino = portfolios.get("High Sortino")

        # Growth vs Balanced
        if growth and balanced:
            ret_diff = growth["expected_return"] - balanced["expected_return"]
            dd_diff = growth["expected_drawdown"] - balanced["expected_drawdown"]
            tradeoffs.append(
                f"Growth increases expected return by {ret_diff:.2f}% but increases expected drawdown by {dd_diff:.2f}% compared to Balanced."
            )

        # Conservative vs Balanced
        if conservative and balanced:
            ret_diff = balanced["expected_return"] - conservative["expected_return"]
            dd_diff = balanced["expected_drawdown"] - conservative["expected_drawdown"]
            tradeoffs.append(
                f"Conservative reduces expected drawdown by {dd_diff:.2f}% but decreases expected return by {ret_diff:.2f}% compared to Balanced."
            )

        # Income vs Balanced
        if income and balanced:
            res_diff = income["resilience_score"] - balanced["resilience_score"]
            ret_diff = balanced["expected_return"] - income["expected_return"]
            if res_diff > 0:
                tradeoffs.append(
                    f"Income improves resilience by {res_diff:.2f}% at the expense of expected return (down by {ret_diff:.2f}%)."
                )
            else:
                tradeoffs.append(
                    f"Income prioritizes cash-flow generating assets, yielding an expected return of {income['expected_return']:.2f}%."
                )

        # High Sharpe vs Balanced
        if sharpe and balanced:
            sh_diff = sharpe["sharpe"] - balanced["sharpe"]
            tradeoffs.append(
                f"High Sharpe optimizes risk-adjusted performance, increasing the Sharpe ratio by {sh_diff:.2f} over Balanced."
            )

        # High Sortino vs Balanced
        if sortino and balanced:
            so_diff = sortino["sortino"] - balanced["sortino"]
            tradeoffs.append(
                f"High Sortino maximizes downside-adjusted performance, increasing the Sortino ratio by {so_diff:.2f} over Balanced."
            )

        # General comments on outstanding properties
        for name, p in portfolios.items():
            if p.get("concentration_score", 0.0) < 30.0 and name != "Balanced":
                tradeoffs.append(f"{name} achieves a very low concentration score of {p['concentration_score']:.2f}%.")
            if p.get("diversification_score", 0.0) > 85.0 and name != "Balanced":
                tradeoffs.append(f"{name} exhibits institutional-quality diversification with a score of {p['diversification_score']:.2f}%.")

        return tradeoffs
