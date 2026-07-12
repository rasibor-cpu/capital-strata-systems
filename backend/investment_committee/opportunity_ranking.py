from __future__ import annotations

from backend.investment_committee.committee_models import CommitteeEvaluation


def rank_committee_evaluations(evaluations: list[CommitteeEvaluation]) -> list[CommitteeEvaluation]:
    ranked = sorted(
        evaluations,
        key=lambda item: (
            -float(item.scorecard.committee_score),
            -float(item.opportunity.capital_efficiency),
            -float(item.opportunity.expected_return),
            str(item.opportunity.symbol),
        ),
    )
    return [
        CommitteeEvaluation(
            opportunity=item.opportunity,
            scorecard=item.scorecard,
            decision=item.decision,
            capital_rank=index,
            opportunity_rank=index,
            recommended_capital=item.recommended_capital,
            capital_displacement=item.capital_displacement,
            replacement_candidate=item.replacement_candidate,
            recommendation=item.recommendation,
            explanation=item.explanation,
        )
        for index, item in enumerate(ranked, start=1)
    ]
