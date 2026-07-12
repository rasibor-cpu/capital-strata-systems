from __future__ import annotations

from collections.abc import Mapping

from backend.investment_committee.committee_models import (
    APPROVED,
    APPROVED_LOW_PRIORITY,
    CAPITAL_BETTER_DEPLOYED,
    CommitteeEvaluation,
    INSUFFICIENT_EDGE,
    LIQUIDITY_VETO,
    OPERATIONAL_VETO,
    PORTFOLIO_CONFLICT,
    PORTFOLIO_VETO,
    REJECT,
    RISK_LIMIT_EXCEEDED,
    RISK_VETO,
    WAIT,
)

VETO_DECISIONS = {RISK_VETO, PORTFOLIO_VETO, LIQUIDITY_VETO, OPERATIONAL_VETO}


def apply_capital_competition(
    evaluations: list[CommitteeEvaluation],
    *,
    portfolio_context: Mapping[str, float],
) -> tuple[list[CommitteeEvaluation], list[dict]]:
    deployable = float(portfolio_context.get("deployable_capital", 0.0) or 0.0)
    max_slots = int(portfolio_context.get("max_approved_opportunities", 3) or 3)
    min_score = float(portfolio_context.get("min_committee_score", 60.0) or 60.0)
    approval_score = float(portfolio_context.get("min_approval_score", 75.0) or 75.0)
    low_score = float(portfolio_context.get("min_low_priority_score", 65.0) or 65.0)

    ranked = sorted(
        evaluations,
        key=lambda item: (
            -float(item.scorecard.committee_score),
            -float(item.opportunity.capital_efficiency),
            -float(item.opportunity.expected_return),
            str(item.opportunity.symbol),
        ),
    )
    used = 0.0
    accepted = 0
    capital_plan: list[dict] = []
    resolved: list[CommitteeEvaluation] = []

    for rank, item in enumerate(ranked, start=1):
        score = float(item.scorecard.committee_score)
        requested = _requested_capital(item, deployable)
        blockers = set(item.scorecard.blockers)
        decision = item.decision
        capital = 0.0
        displacement = ""
        recommendation = item.recommendation

        if decision in VETO_DECISIONS:
            recommendation = str(item.consensus.get("reason") or "Independent committee veto prevents allocation.")
        elif PORTFOLIO_CONFLICT in blockers:
            decision = PORTFOLIO_CONFLICT
            recommendation = "Portfolio exposure conflicts with committee constraints."
        elif RISK_LIMIT_EXCEEDED in blockers:
            decision = RISK_LIMIT_EXCEEDED
            recommendation = "Risk budget is consumed faster than the expected edge justifies."
        elif item.opportunity.decision_confidence < 0.35 or item.opportunity.strategy_confidence < 0.35:
            decision = WAIT
            recommendation = "Confidence is too weak for institutional capital allocation."
        elif INSUFFICIENT_EDGE in blockers or score < min_score:
            decision = INSUFFICIENT_EDGE if INSUFFICIENT_EDGE in blockers else REJECT
            recommendation = "The opportunity does not clear institutional edge thresholds."
        elif decision == WAIT:
            recommendation = str(item.consensus.get("reason") or "Committee consensus is not strong enough to allocate capital.")
        elif used + requested > deployable or accepted >= max_slots:
            decision = CAPITAL_BETTER_DEPLOYED
            displacement = "capital_displaced_by_higher_ranked_opportunities"
            recommendation = "Capital is better deployed in higher ranked opportunities."
        elif score >= approval_score:
            decision = APPROVED
            capital = requested
        elif score >= low_score:
            decision = APPROVED_LOW_PRIORITY
            capital = requested
        else:
            decision = WAIT
            recommendation = "Wait for stronger evidence before allocating capital."

        if capital > 0.0:
            used += capital
            accepted += 1
            capital_plan.append(
                {
                    "capital_rank": rank,
                    "opportunity_id": item.opportunity.opportunity_id,
                    "symbol": item.opportunity.symbol,
                    "asset_class": item.opportunity.asset_class,
                    "sector": item.opportunity.sector,
                    "strategy": item.opportunity.strategy,
                    "broker": item.opportunity.broker,
                    "recommended_capital": round(capital, 6),
                    "committee_score": round(score, 6),
                    "consensus": item.consensus.get("consensus", ""),
                    "decision": decision,
                    "advisory_only": True,
                    "execution_allowed": False,
                }
            )

        resolved.append(
            CommitteeEvaluation(
                opportunity=item.opportunity,
                scorecard=item.scorecard,
                decision=decision,
                capital_rank=rank,
                opportunity_rank=rank,
                recommended_capital=round(capital, 6),
                capital_displacement=displacement,
                replacement_candidate=_replacement_candidate(ranked, rank) if decision == CAPITAL_BETTER_DEPLOYED else "",
                recommendation=recommendation,
                explanation=item.explanation,
                committee_votes=item.committee_votes,
                consensus=item.consensus,
            )
        )

    return resolved, capital_plan


def _requested_capital(item: CommitteeEvaluation, deployable: float) -> float:
    explicit = float(item.opportunity.requested_capital or 0.0)
    if explicit > 0.0:
        return min(explicit, max(deployable, 0.0))
    return max(0.0, deployable * min(0.25, max(0.05, item.opportunity.capital_efficiency * 0.25)))


def _replacement_candidate(ranked: list[CommitteeEvaluation], rank: int) -> str:
    if not ranked:
        return ""
    winner = ranked[0]
    if rank == 1 or winner.opportunity.opportunity_id == ranked[rank - 1].opportunity.opportunity_id:
        return ""
    return winner.opportunity.opportunity_id
