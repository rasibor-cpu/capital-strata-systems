from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.portfolio.diversification_optimizer import DiversificationOptimizer
from backend.portfolio.opportunity_portfolio_ranker import OpportunityPortfolioRanker
from backend.portfolio.portfolio_resilience_analyzer import PortfolioResilienceAnalyzer
from backend.portfolio.institutional_portfolio_optimizer import InstitutionalPortfolioOptimizer
from backend.portfolio.utils import advisory_response


PAYLOAD_VERSION = "css.phase157b.portfolio_construction_intelligence.v1"


class PortfolioConstructionIntelligenceEngine:
    """Construct advisory portfolio intelligence from already-approved opportunities."""

    def __init__(
        self,
        *,
        ranker: OpportunityPortfolioRanker | None = None,
        resilience_analyzer: PortfolioResilienceAnalyzer | None = None,
        diversification_optimizer: DiversificationOptimizer | None = None,
        institutional_optimizer: InstitutionalPortfolioOptimizer | None = None,
    ) -> None:
        self.ranker = ranker or OpportunityPortfolioRanker()
        self.resilience_analyzer = resilience_analyzer or PortfolioResilienceAnalyzer()
        self.diversification_optimizer = diversification_optimizer or DiversificationOptimizer(analyzer=self.resilience_analyzer)
        self.institutional_optimizer = institutional_optimizer or InstitutionalPortfolioOptimizer()

    def analyze(
        self,
        approved_opportunities: Iterable[Mapping[str, Any]] | None,
        *,
        max_positions: int | None = None,
        decision_confidence: Mapping[str, Any] | None = None,
        adaptive_strategy_intelligence: Mapping[str, Any] | None = None,
        opportunity_intelligence: Mapping[str, Any] | None = None,
        dashboard_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            ranking = self.ranker.rank(approved_opportunities)
            resilience = self.resilience_analyzer.analyze(approved_opportunities)
            construction = self.diversification_optimizer.optimize(approved_opportunities, max_positions=max_positions)
            institutional_optimization = self.institutional_optimizer.optimize(approved_opportunities, max_positions=max_positions)

            if ranking.get("status") == "DATA UNAVAILABLE":
                return self._fail_closed("approved_opportunities_unavailable", ranking, resilience, construction, institutional_optimization)

            recommendations = _recommendations(resilience, construction)
            status = _status(resilience, construction)
            return advisory_response(
                status,
                payload_version=PAYLOAD_VERSION,
                portfolio_quality=construction.get("portfolio_quality", resilience.get("portfolio_quality", 0.0)),
                resilience=construction.get("resilience", resilience.get("resilience", 0.0)),
                diversification=construction.get("diversification", resilience.get("diversification", 0.0)),
                expected_return=construction.get("expected_return", resilience.get("expected_return", 0.0)),
                expected_drawdown=construction.get("expected_drawdown", resilience.get("expected_drawdown", 0.0)),
                preferred_portfolio=construction.get("preferred_portfolio", []),
                ranked_opportunities=ranking.get("ranked_opportunities", []),
                replacement_candidates=construction.get("replacement_candidates", []),
                portfolio_resilience=resilience,
                diversification_optimization=construction,
                institutional_portfolio_optimization=institutional_optimization,
                recommendations=recommendations,
                integration={
                    "decision_confidence_consumed": isinstance(decision_confidence, Mapping),
                    "adaptive_strategy_intelligence_consumed": isinstance(adaptive_strategy_intelligence, Mapping),
                    "opportunity_intelligence_consumed": isinstance(opportunity_intelligence, Mapping),
                    "portfolio_dashboard_ready": True,
                    "dashboard_context_consumed": isinstance(dashboard_context, Mapping),
                    "execution_decisions_changed": False,
                    "capital_allocation_changed": False,
                },
                reasons=["portfolio_construction_intelligence_computed"],
                **_safety_flags(),
            )
        except Exception as exc:  # noqa: BLE001 - portfolio construction must fail closed.
            institutional_optimization = self.institutional_optimizer.optimize(None)
            return advisory_response(
                "FAIL_CLOSED",
                payload_version=PAYLOAD_VERSION,
                portfolio_quality=0.0,
                resilience=0.0,
                diversification=0.0,
                expected_return=0.0,
                expected_drawdown=0.0,
                preferred_portfolio=[],
                ranked_opportunities=[],
                replacement_candidates=[],
                institutional_portfolio_optimization=institutional_optimization,
                recommendations=["No advisory portfolio changes while construction intelligence is unavailable."],
                reasons=[f"portfolio_construction_intelligence_failed:{exc.__class__.__name__}"],
                **_safety_flags(),
            )

    @staticmethod
    def _fail_closed(
        reason: str,
        ranking: Mapping[str, Any],
        resilience: Mapping[str, Any],
        construction: Mapping[str, Any],
        institutional_optimization: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return advisory_response(
            "DATA UNAVAILABLE",
            payload_version=PAYLOAD_VERSION,
            portfolio_quality=0.0,
            resilience=0.0,
            diversification=0.0,
            expected_return=0.0,
            expected_drawdown=0.0,
            preferred_portfolio=[],
            ranked_opportunities=[],
            replacement_candidates=[],
            portfolio_resilience=resilience,
            diversification_optimization=construction,
            institutional_portfolio_optimization=institutional_optimization or {},
            recommendations=["No advisory portfolio can be constructed without approved opportunities."],
            reasons=[reason, *ranking.get("reasons", [])],
            **_safety_flags(),
        )


def analyze_portfolio_construction_intelligence(
    approved_opportunities: Iterable[Mapping[str, Any]] | None,
    *,
    max_positions: int | None = None,
    decision_confidence: Mapping[str, Any] | None = None,
    adaptive_strategy_intelligence: Mapping[str, Any] | None = None,
    opportunity_intelligence: Mapping[str, Any] | None = None,
    dashboard_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return PortfolioConstructionIntelligenceEngine().analyze(
        approved_opportunities,
        max_positions=max_positions,
        decision_confidence=decision_confidence,
        adaptive_strategy_intelligence=adaptive_strategy_intelligence,
        opportunity_intelligence=opportunity_intelligence,
        dashboard_context=dashboard_context,
    )


def _status(resilience: Mapping[str, Any], construction: Mapping[str, Any]) -> str:
    if resilience.get("status") == "DATA UNAVAILABLE" or construction.get("status") == "DATA UNAVAILABLE":
        return "DATA UNAVAILABLE"
    quality = float(construction.get("portfolio_quality", resilience.get("portfolio_quality", 0.0)) or 0.0)
    if quality >= 80.0:
        return "OK"
    if quality >= 55.0:
        return "PARTIAL"
    return "DEFENSIVE"


def _recommendations(resilience: Mapping[str, Any], construction: Mapping[str, Any]) -> list[str]:
    recommendations = []
    recommendations.extend(str(item) for item in resilience.get("recommendations", []))
    recommendations.extend(str(item) for item in construction.get("recommendations", []))
    if construction.get("preferred_portfolio"):
        recommendations.append("Preferred portfolio identified")
    return sorted(dict.fromkeys(recommendations)) or ["Increase diversification"]


def _safety_flags() -> dict[str, bool]:
    return {
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "execution_authority_changed": False,
        "capital_allocation_changed": False,
    }
