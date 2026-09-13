from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .readiness import ReadinessAssessment
from .replay import ReplayScore


@dataclass(frozen=True)
class Debrief:
    headline: str
    strengths: tuple[str, ...]
    improvements: tuple[str, ...]
    next_actions: tuple[str, ...]
    replay_score_pct: Decimal
    readiness_level: str


class DebriefEngine:
    @staticmethod
    def build(replay_score: ReplayScore, readiness: ReadinessAssessment) -> Debrief:
        strengths: list[str] = []
        improvements: list[str] = []
        next_actions: list[str] = []

        if replay_score.score_pct >= Decimal("0.80"):
            strengths.append("Strong decision alignment across scenario checkpoints.")
        else:
            improvements.append("Review the checkpoints where actions differed from the scenario evidence.")

        if replay_score.pending:
            improvements.append("Complete all pending scenario decisions.")

        if readiness.decision_quality_pct >= Decimal("0.80"):
            strengths.append("Decision-quality discipline is at or above the advisory training threshold.")
        else:
            next_actions.append("Raise decision quality through additional replay scenarios.")

        if readiness.max_drawdown_pct > Decimal("0.10"):
            improvements.append("Drawdown control needs improvement.")
            next_actions.append("Repeat capital-preservation and drawdown-control scenarios.")

        next_actions.extend(readiness.reasons[:2])

        headline = (
            "Scenario complete — strong training result."
            if replay_score.score_pct >= Decimal("0.80")
            else "Scenario complete — review the decision path before advancing."
        )

        return Debrief(
            headline=headline,
            strengths=tuple(strengths),
            improvements=tuple(dict.fromkeys(improvements)),
            next_actions=tuple(dict.fromkeys(next_actions)),
            replay_score_pct=replay_score.score_pct,
            readiness_level=readiness.level.value,
        )
