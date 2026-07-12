from __future__ import annotations

from backend.investment_committee.committee_models import CommitteeEvaluation, CommitteeOpportunity, CommitteeScorecard


def build_committee_explanation(
    opportunity: CommitteeOpportunity,
    scorecard: CommitteeScorecard,
    *,
    decision: str,
    capital_rank: int = 0,
) -> str:
    top_strengths = ", ".join(scorecard.strengths[:3]) or "balanced evidence"
    weaknesses = ", ".join(scorecard.weaknesses[:3]) or "no dominant weakness"
    return (
        f"{opportunity.symbol} received committee score {scorecard.committee_score:.1f}. "
        f"Expected return {opportunity.expected_return:.4f}, expected drawdown {opportunity.expected_drawdown:.4f}, "
        f"confidence {opportunity.decision_confidence:.2f}, capital efficiency {opportunity.capital_efficiency:.2f}, "
        f"correlation {opportunity.portfolio_correlation:.2f}. Decision {decision}; "
        f"capital rank {capital_rank or 'pending'}. Strengths: {top_strengths}. Weaknesses: {weaknesses}. "
        "This recommendation is advisory only and does not authorize execution."
    )


def explain_report(evaluations: list[CommitteeEvaluation]) -> list[str]:
    if not evaluations:
        return ["No candidate trades were available for committee review."]
    return [
        f"{item.opportunity.symbol}: {item.decision} at rank {item.capital_rank} with score {item.scorecard.committee_score:.1f}."
        for item in evaluations[:5]
    ]
