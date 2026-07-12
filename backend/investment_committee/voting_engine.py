from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.investment_committee.committee_members import (
    AdvisoryCommitteeMember,
    default_committee_members,
)
from backend.investment_committee.committee_models import CommitteeOpportunity, CommitteeVote


class CommitteeVotingEngine:
    """Runs independent advisory committee votes for one opportunity."""

    def __init__(self, members: Sequence[AdvisoryCommitteeMember] | None = None) -> None:
        self.members = list(members) if members is not None else default_committee_members()

    def vote(
        self,
        opportunity: CommitteeOpportunity,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> list[CommitteeVote]:
        return [member.evaluate(opportunity, context=context) for member in self.members]


__all__ = ["CommitteeVotingEngine"]
