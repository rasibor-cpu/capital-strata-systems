from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import combinations
from typing import Any

from backend.portfolio.opportunity_portfolio_ranker import OpportunityPortfolioRanker, normalize_opportunities
from backend.portfolio.portfolio_resilience_analyzer import PortfolioResilienceAnalyzer
from backend.portfolio.utils import advisory_response, safe_float


class DiversificationOptimizer:
    """Select an advisory preferred portfolio from approved opportunities."""

    def __init__(self, *, analyzer: PortfolioResilienceAnalyzer | None = None) -> None:
        self.analyzer = analyzer or PortfolioResilienceAnalyzer()
        self.ranker = OpportunityPortfolioRanker()

    def optimize(
        self,
        opportunities: Iterable[Mapping[str, Any]] | None,
        *,
        max_positions: int | None = None,
        min_positions: int = 1,
    ) -> dict[str, Any]:
        normalized = normalize_opportunities(opportunities)
        if not normalized:
            return advisory_response(
                "DATA UNAVAILABLE",
                preferred_portfolio=[],
                replacement_candidates=[],
                reasons=["approved_opportunities_unavailable"],
                recommendations=["No advisory portfolio can be constructed without approved opportunities."],
                **_safety_flags(),
            )

        upper = min(len(normalized), max_positions or min(len(normalized), 5))
        lower = upper if max_positions is not None else max(1, min(max(3, min_positions), upper))
        best_subset: list[Mapping[str, Any]] = []
        best_score = -1.0
        best_analysis: dict[str, Any] = {}
        for size in range(lower, upper + 1):
            for subset in combinations(normalized, size):
                analysis = self.analyzer.analyze(subset)
                quality = safe_float(analysis.get("portfolio_quality"))
                expected_return = safe_float(analysis.get("expected_return"))
                drawdown = safe_float(analysis.get("expected_drawdown"))
                score = quality + expected_return * 0.5 - drawdown * 0.25
                if score > best_score:
                    best_score = score
                    best_subset = list(subset)
                    best_analysis = analysis

        selected_ids = {item["opportunity_id"] for item in best_subset}
        excluded = [item for item in normalized if item["opportunity_id"] not in selected_ids]
        ranking = self.ranker.rank(normalized)
        replacements = _replacement_candidates(best_subset, excluded, self.analyzer)
        baseline_replacements = _baseline_replacement_candidates(normalized, best_subset, upper, self.analyzer)
        replacements = sorted(
            [*replacements, *baseline_replacements],
            key=lambda item: (-item["quality_improvement"], item["replace"], item["with"]),
        )[:5]
        recommendations = list(best_analysis.get("recommendations", []))
        recommendations.extend(_replacement_recommendations(replacements))

        return advisory_response(
            "OK",
            preferred_portfolio=[_portfolio_row(item) for item in best_subset],
            excluded_opportunities=[_portfolio_row(item) for item in excluded],
            replacement_candidates=replacements,
            opportunity_ranking=ranking.get("ranked_opportunities", []),
            portfolio_quality=best_analysis.get("portfolio_quality", 0.0),
            resilience=best_analysis.get("resilience", 0.0),
            diversification=best_analysis.get("diversification", 0.0),
            expected_return=best_analysis.get("expected_return", 0.0),
            expected_drawdown=best_analysis.get("expected_drawdown", 0.0),
            recommendations=sorted(dict.fromkeys(recommendations)),
            reasons=["preferred_portfolio_constructed_from_approved_opportunities"],
            **_safety_flags(),
        )


def _replacement_candidates(
    selected: list[Mapping[str, Any]],
    excluded: list[Mapping[str, Any]],
    analyzer: PortfolioResilienceAnalyzer,
) -> list[dict[str, Any]]:
    current_quality = safe_float(analyzer.analyze(selected).get("portfolio_quality"))
    candidates: list[dict[str, Any]] = []
    for old in selected:
        for new in excluded:
            proposed = [item for item in selected if item["opportunity_id"] != old["opportunity_id"]] + [new]
            analysis = analyzer.analyze(proposed)
            quality = safe_float(analysis.get("portfolio_quality"))
            improvement = round(quality - current_quality, 6)
            if improvement > 0.0:
                candidates.append(
                    {
                        "replace": old["opportunity_id"],
                        "with": new["opportunity_id"],
                        "quality_improvement": improvement,
                        "new_portfolio_quality": round(quality, 6),
                        "reason": "replacement_improves_portfolio_quality",
                        "advisory_only": True,
                        "execution_allowed": False,
                    }
                )
    candidates.sort(key=lambda item: (-item["quality_improvement"], item["replace"], item["with"]))
    return candidates[:5]


def _baseline_replacement_candidates(
    opportunities: list[Mapping[str, Any]],
    preferred: list[Mapping[str, Any]],
    max_positions: int,
    analyzer: PortfolioResilienceAnalyzer,
) -> list[dict[str, Any]]:
    baseline = sorted(
        opportunities,
        key=lambda item: (-safe_float(item.get("expected_return")), item["opportunity_id"]),
    )[:max_positions]
    baseline_ids = {item["opportunity_id"] for item in baseline}
    preferred_ids = {item["opportunity_id"] for item in preferred}
    removed = [item for item in baseline if item["opportunity_id"] not in preferred_ids]
    added = [item for item in preferred if item["opportunity_id"] not in baseline_ids]
    if not removed or not added:
        return []

    baseline_quality = safe_float(analyzer.analyze(baseline).get("portfolio_quality"))
    preferred_quality = safe_float(analyzer.analyze(preferred).get("portfolio_quality"))
    improvement = round(preferred_quality - baseline_quality, 6)
    if improvement <= 0.0:
        return []
    candidates = []
    for old, new in zip(removed, added):
        candidates.append(
            {
                "replace": old["opportunity_id"],
                "with": new["opportunity_id"],
                "quality_improvement": improvement,
                "new_portfolio_quality": round(preferred_quality, 6),
                "reason": "preferred_portfolio_improves_high_return_baseline",
                "advisory_only": True,
                "execution_allowed": False,
            }
        )
    return candidates


def _replacement_recommendations(replacements: list[Mapping[str, Any]]) -> list[str]:
    if not replacements:
        return []
    best = replacements[0]
    return [f"Replace {best['replace']} with {best['with']}"]


def _portfolio_row(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "opportunity_id": item["opportunity_id"],
        "symbol": item["symbol"],
        "asset_class": item["asset_class"],
        "sector": item["sector"],
        "currency": item["currency"],
        "expected_return": item["expected_return"],
        "expected_drawdown": item["expected_drawdown"],
        "advisory_only": True,
        "execution_allowed": False,
    }


def _safety_flags() -> dict[str, bool]:
    return {
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "execution_authority_changed": False,
    }
