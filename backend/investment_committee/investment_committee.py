from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from backend.investment_committee.capital_competition import apply_capital_competition
from backend.investment_committee.committee_consensus import CommitteeConsensusEngine
from backend.investment_committee.committee_explainability import (
    build_committee_explanation,
    explain_report,
)
from backend.investment_committee.committee_history import CommitteeHistoryStore
from backend.investment_committee.committee_models import (
    CommitteeEvaluation,
    CommitteeReport,
)
from backend.investment_committee.committee_scorecard import (
    CommitteeScorecardEngine,
    normalize_opportunity,
)
from backend.investment_committee.portfolio_context import build_portfolio_context
from backend.investment_committee.voting_engine import CommitteeVotingEngine


class InstitutionalInvestmentCommittee:
    """Highest-level advisory trade selection and capital allocation committee."""

    def __init__(
        self,
        scorecard_engine: CommitteeScorecardEngine | None = None,
        voting_engine: CommitteeVotingEngine | None = None,
        consensus_engine: CommitteeConsensusEngine | None = None,
        history_store: CommitteeHistoryStore | None = None,
    ) -> None:
        self.scorecard_engine = scorecard_engine or CommitteeScorecardEngine()
        self.voting_engine = voting_engine or CommitteeVotingEngine()
        self.consensus_engine = consensus_engine or CommitteeConsensusEngine()
        self.history_store = history_store or CommitteeHistoryStore()

    def evaluate(
        self,
        opportunities: Sequence[Mapping[str, Any]] | None,
        *,
        portfolio_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if opportunities is None:
            return CommitteeReport.empty().as_dict()
        if not isinstance(opportunities, Sequence) or isinstance(opportunities, (str, bytes)):
            raise ValueError("committee opportunities must be a sequence")

        context = dict(portfolio_context or {})
        prelim: list[CommitteeEvaluation] = []
        for index, row in enumerate(opportunities):
            if not isinstance(row, Mapping):
                raise ValueError("committee opportunity rows must be mappings")
            opportunity = normalize_opportunity(row, index=index, portfolio_context=context)
            scorecard = self.scorecard_engine.score(opportunity, portfolio_context=context)
            votes = self.voting_engine.vote(opportunity, context=context)
            consensus = self.consensus_engine.aggregate(votes)
            decision = str(consensus.get("institutional_recommendation"))
            explanation = build_committee_explanation(opportunity, scorecard, decision=decision)
            prelim.append(
                CommitteeEvaluation(
                    opportunity=opportunity,
                    scorecard=scorecard,
                    decision=decision,
                    capital_rank=0,
                    opportunity_rank=0,
                    recommended_capital=0.0,
                    capital_displacement="",
                    replacement_candidate="",
                    recommendation=str(consensus.get("reason", "Pending capital competition.")),
                    explanation=explanation,
                    committee_votes=votes,
                    consensus=consensus,
                )
            )

        if not prelim:
            return CommitteeReport.empty().as_dict()

        resolved, capital_plan = apply_capital_competition(prelim, portfolio_context=context)
        explained = [
            CommitteeEvaluation(
                opportunity=item.opportunity,
                scorecard=item.scorecard,
                decision=item.decision,
                capital_rank=item.capital_rank,
                opportunity_rank=item.opportunity_rank,
                recommended_capital=item.recommended_capital,
                capital_displacement=item.capital_displacement,
                replacement_candidate=item.replacement_candidate,
                recommendation=item.recommendation,
                explanation=build_committee_explanation(
                    item.opportunity,
                    item.scorecard,
                    decision=item.decision,
                    capital_rank=item.capital_rank,
                ),
                committee_votes=item.committee_votes,
                consensus=item.consensus,
            )
            for item in resolved
        ]
        top = explained[0]
        blockers = sorted({blocker for item in explained for blocker in item.scorecard.blockers})
        history = [
            self.history_store.record(
                opportunity_id=item.opportunity.opportunity_id,
                votes=[vote.as_dict() for vote in item.committee_votes],
                recommendation=item.decision,
                confidence=float(item.consensus.get("weighted_committee_confidence", 0.0)),
                consensus=item.consensus,
                explanations=[vote.reason for vote in item.committee_votes],
            )
            for item in explained
        ]
        report = CommitteeReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            committee_score=round(float(top.scorecard.committee_score), 6),
            decision=top.decision,
            evaluations=explained,
            capital_plan=capital_plan,
            recommendations=explain_report(explained),
            blockers=blockers,
            consensus_summary=top.consensus,
            committee_history=history,
        )
        return report.as_dict()


def build_institutional_investment_committee_report(
    dashboard_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = _mapping(dashboard_payload)
    explicit = _mapping(payload.get("institutional_investment_committee"))
    if explicit:
        return {
            **explicit,
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
        }
    opportunities = _list(payload.get("opportunities"))
    context = build_portfolio_context(payload)
    return InstitutionalInvestmentCommittee().evaluate(opportunities, portfolio_context=context)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
