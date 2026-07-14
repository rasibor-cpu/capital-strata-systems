from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from backend.investment_committee.committee_models import (
    ABSTAIN,
    APPROVE,
    APPROVE_WITH_CAUTION,
    APPROVED,
    APPROVED_LOW_PRIORITY,
    CAPITAL_BETTER_DEPLOYED,
    CommitteeVote,
    LIQUIDITY_VETO,
    OPERATIONAL_VETO,
    PORTFOLIO_VETO,
    REJECT,
    RISK_VETO,
    VOTES,
    WAIT,
)


VETO_PRIORITY = (RISK_VETO, PORTFOLIO_VETO, LIQUIDITY_VETO, OPERATIONAL_VETO)
EXPECTED_COMMITTEE_COUNT = 6


class CommitteeConsensusEngine:
    """Aggregates committee votes into one institutional recommendation."""

    def aggregate(self, votes: Sequence[CommitteeVote]) -> dict[str, Any]:
        rows = list(votes)
        if not rows:
            return _payload(WAIT, "NO_VOTES", 0.0, {}, [], "No committee votes were available.")
        invalid_reason = _invalid_vote_reason(rows)
        if invalid_reason:
            return _payload(WAIT, invalid_reason, 0.0, {}, [], "Committee vote evidence was incomplete or malformed.")

        counts: dict[str, int] = {APPROVE: 0, APPROVE_WITH_CAUTION: 0, WAIT: 0, REJECT: 0, ABSTAIN: 0}
        for vote in rows:
            counts[vote.vote] = counts.get(vote.vote, 0) + 1

        vetoes = [vote.veto for vote in rows if vote.veto]
        for veto in VETO_PRIORITY:
            if veto in vetoes:
                return _payload(
                    veto,
                    "VETO",
                    _weighted_confidence(rows),
                    counts,
                    vetoes,
                    f"{veto} applied by independent committee vote.",
                )

        approval_count = counts.get(APPROVE, 0) + counts.get(APPROVE_WITH_CAUTION, 0)
        active_count = max(1, len([vote for vote in rows if vote.vote != ABSTAIN]))
        reject_count = counts.get(REJECT, 0)
        wait_count = counts.get(WAIT, 0)
        confidence = _weighted_confidence(rows)
        if confidence <= 0.0:
            return _payload(
                WAIT,
                "ZERO_CONFIDENCE_COMMITTEE",
                0.0,
                counts,
                vetoes,
                "Committee confidence was zero; advisory approval is withheld.",
            )

        if approval_count == active_count:
            decision = APPROVED if counts.get(APPROVE, 0) == active_count else APPROVED_LOW_PRIORITY
            status = "UNANIMOUS_APPROVAL"
        elif approval_count > active_count / 2 and reject_count == 0:
            decision = APPROVED_LOW_PRIORITY
            status = "MAJORITY_APPROVAL"
        elif approval_count == reject_count and wait_count == 0:
            decision = WAIT
            status = "TIE_RESOLUTION_WAIT"
        elif reject_count > approval_count:
            decision = CAPITAL_BETTER_DEPLOYED if counts.get(APPROVE, 0) > 0 else WAIT
            status = "SPLIT_COMMITTEE"
        else:
            decision = WAIT
            status = "SPLIT_COMMITTEE"

        return _payload(
            decision,
            status,
            confidence,
            counts,
            vetoes,
            f"{status}: approvals={approval_count}, waits={wait_count}, rejects={reject_count}.",
        )


def _weighted_confidence(votes: Sequence[CommitteeVote]) -> float:
    if not votes:
        return 0.0
    total_score = sum(max(0.0, float(vote.committee_score)) * max(0.0, float(vote.confidence)) for vote in votes)
    total_weight = sum(max(0.0, float(vote.committee_score)) for vote in votes)
    if total_weight <= 0.0:
        return 0.0
    return round(total_score / total_weight, 6)


def _payload(
    decision: str,
    consensus: str,
    confidence: float,
    vote_counts: dict[str, int],
    vetoes: list[str],
    reason: str,
) -> dict[str, Any]:
    return {
        "institutional_recommendation": decision,
        "consensus": consensus,
        "consensus_score": round(confidence * 100.0, 6),
        "weighted_committee_confidence": confidence,
        "vote_counts": vote_counts,
        "veto_reasons": sorted(dict.fromkeys(vetoes)),
        "reason": reason,
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
    }


def _invalid_vote_reason(votes: Sequence[CommitteeVote]) -> str:
    committees: set[str] = set()
    for vote in votes:
        if not isinstance(vote, CommitteeVote):
            return "MALFORMED_COMMITTEE_VOTE"
        if not str(vote.committee).strip():
            return "MALFORMED_COMMITTEE_VOTE"
        if vote.vote not in VOTES:
            return "MALFORMED_COMMITTEE_VOTE"
        try:
            float(vote.committee_score)
            float(vote.confidence)
        except (TypeError, ValueError):
            return "MALFORMED_COMMITTEE_VOTE"
        committees.add(str(vote.committee).strip())
    if len(committees) < EXPECTED_COMMITTEE_COUNT:
        return "MISSING_COMMITTEE_VOTE"
    return ""


__all__ = ["CommitteeConsensusEngine", "EXPECTED_COMMITTEE_COUNT", "VETO_PRIORITY"]
