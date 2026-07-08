from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.portfolio.utils import advisory_response, safe_float
from backend.intelligence.committee_member_models import (
    ChiefInvestmentOfficer,
    ChiefRiskOfficer,
    PortfolioManager,
    HeadOfTrading,
    QuantitativeResearchLead,
    GovernanceCompliance,
)
from backend.intelligence.committee_consensus_engine import CommitteeConsensusEngine
from backend.intelligence.committee_explainability import CommitteeExplainability


class InvestmentCommitteeEngine:
    """Evaluate advisory portfolio scenarios using multiple independent institutional viewpoints."""

    def __init__(
        self,
        *,
        consensus_engine: CommitteeConsensusEngine | None = None,
        explainability: CommitteeExplainability | None = None,
    ) -> None:
        self.consensus_engine = consensus_engine or CommitteeConsensusEngine()
        self.explainability = explainability or CommitteeExplainability()
        self.members = [
            ChiefInvestmentOfficer(),
            ChiefRiskOfficer(),
            PortfolioManager(),
            HeadOfTrading(),
            QuantitativeResearchLead(),
            GovernanceCompliance(),
        ]

    def evaluate_portfolio(
        self,
        approved_opportunities: Iterable[Mapping[str, Any]] | None,
        *,
        max_positions: int | None = None,
        decision_confidence: Mapping[str, Any] | None = None,
        adaptive_strategy_intelligence: Mapping[str, Any] | None = None,
        opportunity_intelligence: Mapping[str, Any] | None = None,
        dashboard_context: Mapping[str, Any] | None = None,
        broker_health: Mapping[str, Any] | None = None,
        institutional_optimization: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            if not approved_opportunities or not institutional_optimization:
                return self._fail_closed(["approved_opportunities_or_optimization_unavailable"])

            if institutional_optimization.get("status") == "DATA UNAVAILABLE":
                return self._fail_closed(institutional_optimization.get("reasons", ["optimization_data_unavailable"]))

            recommended_portfolios = institutional_optimization.get("recommended_portfolios", [])
            best_overall = institutional_optimization.get("best_overall")

            # Find the portfolio to evaluate (the best_overall portfolio)
            target_portfolio = None
            for p in recommended_portfolios:
                if p.get("name") == best_overall:
                    target_portfolio = p
                    break

            if not target_portfolio:
                if recommended_portfolios:
                    target_portfolio = recommended_portfolios[0]
                else:
                    return self._fail_closed(["no_recommended_portfolios_found"])

            # Construct evaluation context from consumed components
            ctx = {}
            if isinstance(decision_confidence, Mapping):
                ctx["confidence"] = safe_float(decision_confidence.get("confidence", decision_confidence.get("confidence_score", 80.0)))
            else:
                ctx["confidence"] = 80.0

            if isinstance(broker_health, Mapping):
                ctx["broker_health"] = str(broker_health.get("broker_health", broker_health.get("status", "GREEN"))).upper()
            else:
                ctx["broker_health"] = "GREEN"

            # Run scoring and voting for all members
            member_scores = {}
            votes = {}
            for member in self.members:
                scores = member.score_portfolio(target_portfolio, context=ctx)
                member_scores[member.role] = scores
                votes[member.role] = member.vote(scores)

            # Compile consensus
            consensus = self.consensus_engine.compile_consensus(votes)

            # Generate natural language comments
            comments = self.explainability.generate_comments(target_portfolio, member_scores, context=ctx)

            # Build return dict
            res = advisory_response(
                "OK",
                recommended_portfolio=target_portfolio.get("name", "Balanced"),
                committee_vote=consensus["committee_vote"],
                overall_recommendation=consensus["overall_recommendation"],
                member_comments=comments,
                member_votes=votes,
                member_scores=member_scores,
                reasons=["investment_committee_evaluation_completed"],
                live_trading_blocked=True,
                broker_execution_armed=False,
                integration={
                    "phase157a_consumed": isinstance(adaptive_strategy_intelligence, Mapping),
                    "phase157b_consumed": True,
                    "phase157c_consumed": True,
                    "decision_confidence_consumed": isinstance(decision_confidence, Mapping),
                    "broker_health_consumed": isinstance(broker_health, Mapping),
                },
            )
            return res

        except Exception as exc:  # noqa: BLE001 - must fail closed
            return self._fail_closed([f"investment_committee_exception:{exc.__class__.__name__}"])

    @staticmethod
    def _fail_closed(reasons: list[str]) -> dict[str, Any]:
        return advisory_response(
            "DATA UNAVAILABLE",
            recommended_portfolio="DATA UNAVAILABLE",
            committee_vote={"approve": 0, "conditional": 0, "reject": 6},
            overall_recommendation="REJECT",
            member_comments=[f"Fail closed: Investment committee evaluation unavailable. Reasons: {', '.join(reasons)}."],
            member_votes={},
            member_scores={},
            reasons=reasons,
            live_trading_blocked=True,
            broker_execution_armed=False,
            integration={
                "phase157a_consumed": False,
                "phase157b_consumed": False,
                "phase157c_consumed": False,
                "decision_confidence_consumed": False,
                "broker_health_consumed": False,
            },
        )
