from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import combinations
from typing import Any

from backend.portfolio.opportunity_portfolio_ranker import normalize_opportunities
from backend.portfolio.portfolio_resilience_analyzer import PortfolioResilienceAnalyzer
from backend.portfolio.utils import safe_float


class PortfolioScenarioGenerator:
    """Generate 6 distinct institutional portfolio scenarios from approved opportunities."""

    def __init__(self, *, analyzer: PortfolioResilienceAnalyzer | None = None) -> None:
        self.analyzer = analyzer or PortfolioResilienceAnalyzer()

    def generate_scenarios(
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
                "scenarios": {},
                "reasons": ["approved_opportunities_unavailable"],
            }

        upper = min(len(normalized), max_positions or min(len(normalized), 5))
        lower = upper if max_positions is not None else max(1, min(max(3, min_positions), upper))

        # We will collect all combinations
        candidates = []
        for size in range(lower, upper + 1):
            for subset in combinations(normalized, size):
                subset_list = list(subset)
                analysis = self.analyzer.analyze(subset_list)
                if analysis.get("status") != "OK":
                    continue
                candidates.append((subset_list, analysis))

        if not candidates:
            return {
                "status": "DATA UNAVAILABLE",
                "scenarios": {},
                "reasons": ["no_valid_candidates_generated"],
            }

        scenarios = {}
        profiles = ["Conservative", "Balanced", "Growth", "Income", "High Sharpe", "High Sortino"]

        for profile in profiles:
            best_subset = None
            best_analysis = None
            best_score = -1e9

            for subset, analysis in candidates:
                expected_return = safe_float(analysis.get("expected_return"))
                expected_volatility = safe_float(analysis.get("expected_volatility"))
                expected_drawdown = safe_float(analysis.get("expected_drawdown"))
                resilience = safe_float(analysis.get("resilience"))
                portfolio_quality = safe_float(analysis.get("portfolio_quality"))

                if profile == "Conservative":
                    # Maximize resilience and minimize drawdown
                    score = resilience - expected_drawdown * 3.0
                elif profile == "Balanced":
                    # Balanced return vs drawdown and volatility
                    score = portfolio_quality
                elif profile == "Growth":
                    # Maximize expected return
                    score = expected_return - expected_drawdown * 0.1
                elif profile == "Income":
                    # Maximize income score (carry / fixed income exposure)
                    score = self._compute_income_score(subset) * 0.7 + expected_return * 0.3 - expected_drawdown * 0.1
                elif profile == "High Sharpe":
                    score = expected_return / expected_volatility if expected_volatility > 0.0 else 0.0
                elif profile == "High Sortino":
                    score = expected_return / expected_drawdown if expected_drawdown > 0.0 else 0.0
                else:
                    score = 0.0

                if score > best_score:
                    best_score = score
                    best_subset = subset
                    best_analysis = analysis

            if best_subset is not None and best_analysis is not None:
                # Compile portfolio details
                expected_return = safe_float(best_analysis.get("expected_return"))
                expected_volatility = safe_float(best_analysis.get("expected_volatility"))
                expected_drawdown = safe_float(best_analysis.get("expected_drawdown"))
                sharpe = expected_return / expected_volatility if expected_volatility > 0.0 else 0.0
                sortino = expected_return / expected_drawdown if expected_drawdown > 0.0 else 0.0
                beta = safe_float(best_analysis.get("portfolio_beta"))
                diversification = safe_float(best_analysis.get("diversification"))
                resilience = safe_float(best_analysis.get("resilience"))
                concentration = safe_float(best_analysis.get("concentration_score"))
                quality = safe_float(best_analysis.get("portfolio_quality"))
                cap_efficiency = self._compute_capital_efficiency(best_subset, expected_return, expected_drawdown)

                scenarios[profile] = {
                    "name": profile,
                    "expected_return": round(expected_return, 6),
                    "expected_volatility": round(expected_volatility, 6),
                    "expected_drawdown": round(expected_drawdown, 6),
                    "sharpe": round(sharpe, 6),
                    "sortino": round(sortino, 6),
                    "portfolio_beta": round(beta, 6),
                    "diversification_score": round(diversification, 6),
                    "resilience_score": round(resilience, 6),
                    "concentration_score": round(concentration, 6),
                    "portfolio_quality_score": round(quality, 6),
                    "capital_efficiency_score": round(cap_efficiency, 6),
                    "opportunities": [
                        {
                            "opportunity_id": item["opportunity_id"],
                            "symbol": item["symbol"],
                            "asset_class": item["asset_class"],
                            "sector": item["sector"],
                            "currency": item["currency"],
                            "weight": item["weight"],
                            "expected_return": item["expected_return"],
                            "expected_drawdown": item["expected_drawdown"],
                            "advisory_only": True,
                            "execution_allowed": False,
                        }
                        for item in best_subset
                    ],
                    "advisory_only": True,
                    "execution_allowed": False,
                }

        return {
            "status": "OK",
            "scenarios": scenarios,
            "reasons": ["portfolio_scenarios_generated"],
        }

    def _compute_income_score(self, subset: list[dict[str, Any]]) -> float:
        scores = []
        for item in subset:
            base = 10.0
            asset_class = str(item.get("asset_class", "")).upper()
            factors = [str(f).upper() for f in item.get("factor_exposure", [])]
            strategy = str(item.get("strategy", "")).upper()

            if asset_class == "FIXED_INCOME":
                base += 50.0
            elif asset_class == "FX":
                base += 20.0

            if any(f in factors for f in ("CARRY", "INCOME", "YIELD")):
                base += 40.0

            if any(term in strategy for term in ("CARRY", "INCOME", "YIELD")):
                base += 30.0

            scores.append(base)

        return sum(scores) / len(scores) if scores else 0.0

    def _compute_capital_efficiency(self, subset: list[dict[str, Any]], expected_return: float, expected_drawdown: float) -> float:
        effs = []
        for item in subset:
            raw = item.get("raw", item)
            explicit = raw.get("capital_efficiency") or raw.get("capital_efficiency_score")
            if explicit is not None:
                eff = safe_float(explicit)
                if eff > 1.0:
                    eff /= 100.0
                effs.append(eff)
            else:
                requested = abs(safe_float(raw.get("requested_capital", raw.get("capital_at_risk", raw.get("allocation_amount", 1000.0)))))
                reward = max(0.0, safe_float(raw.get("expected_reward", raw.get("expected_value", raw.get("reward", 0.0)))))
                if requested > 0.0:
                    effs.append(max(0.0, min(1.0, reward / requested)))
                else:
                    effs.append(0.5)

        avg_eff = sum(effs) / len(effs) if effs else 0.5
        ratio = expected_return / expected_drawdown if expected_drawdown > 0.0 else expected_return
        score = avg_eff * 70.0 + min(30.0, ratio * 10.0)
        return max(0.0, min(100.0, score))
