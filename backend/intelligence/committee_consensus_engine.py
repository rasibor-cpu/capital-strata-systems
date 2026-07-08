from __future__ import annotations

from typing import Any


class CommitteeConsensusEngine:
    """Aggregate member votes and establish institutional consensus."""

    def compile_consensus(self, votes: dict[str, str]) -> dict[str, Any]:
        tally = {"approve": 0, "conditional": 0, "reject": 0}

        for member_name, vote in votes.items():
            vote_lower = vote.lower()
            if "strong approve" in vote_lower or vote_lower == "approve":
                tally["approve"] += 1
            elif "conditional" in vote_lower or "needs review" in vote_lower:
                tally["conditional"] += 1
            else:
                tally["reject"] += 1

        # Determine overall recommendation string
        if tally["reject"] > 0:
            rec = "REJECT"
        elif tally["conditional"] > 2:
            rec = "NEEDS_REVIEW"
        elif tally["conditional"] > 0:
            rec = "CONDITIONAL"
        else:
            rec = "APPROVE"

        return {
            "committee_vote": tally,
            "overall_recommendation": rec,
        }
