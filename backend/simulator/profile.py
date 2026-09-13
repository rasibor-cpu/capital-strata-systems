from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable

from .academy import Achievement, RecommendationDecision


SCHEMA_VERSION = 1


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware UTC")


@dataclass(frozen=True)
class LearnerProfile:
    learner_id: str
    completed_lesson_ids: tuple[str, ...] = ()
    achievements: tuple[Achievement, ...] = ()
    decisions: tuple[RecommendationDecision, ...] = ()
    challenge_observations: tuple[tuple[str, int], ...] = ()
    updated_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if not self.learner_id.strip():
            raise ValueError("learner_id is required")
        if self.updated_at_utc is not None:
            _require_utc(self.updated_at_utc, "updated_at_utc")
        for challenge_id, observations in self.challenge_observations:
            if not challenge_id.strip() or observations < 0:
                raise ValueError("challenge observation values are invalid")

    def record_lesson(self, lesson_id: str, at_utc: datetime) -> "LearnerProfile":
        _require_utc(at_utc, "at_utc")
        if not lesson_id.strip():
            raise ValueError("lesson_id is required")
        ids = tuple(sorted(set(self.completed_lesson_ids) | {lesson_id}))
        return replace(self, completed_lesson_ids=ids, updated_at_utc=at_utc)

    def record_decision(self, decision: RecommendationDecision) -> "LearnerProfile":
        by_id = {item.decision_id: item for item in self.decisions}
        existing = by_id.get(decision.decision_id)
        if existing is not None and existing != decision:
            raise ValueError("decision_id already exists with different content")
        by_id[decision.decision_id] = decision
        return replace(
            self,
            decisions=tuple(sorted(by_id.values(), key=lambda item: item.decision_id)),
            updated_at_utc=decision.recorded_at_utc,
        )

    def record_achievements(
        self, achievements: Iterable[Achievement], at_utc: datetime
    ) -> "LearnerProfile":
        _require_utc(at_utc, "at_utc")
        by_id = {item.achievement_id: item for item in self.achievements}
        for item in achievements:
            by_id.setdefault(item.achievement_id, item)
        return replace(
            self,
            achievements=tuple(sorted(by_id.values(), key=lambda item: item.achievement_id)),
            updated_at_utc=at_utc,
        )

    def set_challenge_observations(
        self, challenge_id: str, observations: int, at_utc: datetime
    ) -> "LearnerProfile":
        _require_utc(at_utc, "at_utc")
        if not challenge_id.strip() or observations < 0:
            raise ValueError("invalid challenge observation")
        values = dict(self.challenge_observations)
        values[challenge_id] = max(values.get(challenge_id, 0), observations)
        return replace(
            self,
            challenge_observations=tuple(sorted(values.items())),
            updated_at_utc=at_utc,
        )


class LearnerProfileStore:
    """Atomic JSON persistence for simulation-only learner state."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def save(self, profile: LearnerProfile) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "learner_id": profile.learner_id,
            "completed_lesson_ids": list(profile.completed_lesson_ids),
            "achievements": [
                {
                    "achievement_id": item.achievement_id,
                    "awarded_at_utc": item.awarded_at_utc.isoformat(),
                    "source": item.source,
                }
                for item in profile.achievements
            ],
            "decisions": [
                {
                    "decision_id": item.decision_id,
                    "recommendation_id": item.recommendation_id,
                    "action": item.action.value,
                    "recorded_at_utc": item.recorded_at_utc.isoformat(),
                    "outcome": item.outcome.value,
                    "note": item.note,
                }
                for item in profile.decisions
            ],
            "challenge_observations": dict(profile.challenge_observations),
            "updated_at_utc": profile.updated_at_utc.isoformat()
            if profile.updated_at_utc
            else None,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent, delete=False
        ) as handle:
            handle.write(encoded)
            temp_name = handle.name
        os.replace(temp_name, self.path)

    def load(self) -> LearnerProfile:
        from .academy import Achievement, DecisionAction, DecisionOutcome, RecommendationDecision

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported learner profile schema")

        achievements = tuple(
            Achievement(
                achievement_id=item["achievement_id"],
                awarded_at_utc=datetime.fromisoformat(item["awarded_at_utc"]),
                source=item["source"],
            )
            for item in payload.get("achievements", [])
        )
        decisions = tuple(
            RecommendationDecision(
                decision_id=item["decision_id"],
                recommendation_id=item["recommendation_id"],
                action=DecisionAction(item["action"]),
                recorded_at_utc=datetime.fromisoformat(item["recorded_at_utc"]),
                outcome=DecisionOutcome(item["outcome"]),
                note=item.get("note", ""),
            )
            for item in payload.get("decisions", [])
        )
        updated = payload.get("updated_at_utc")
        return LearnerProfile(
            learner_id=payload["learner_id"],
            completed_lesson_ids=tuple(payload.get("completed_lesson_ids", [])),
            achievements=achievements,
            decisions=decisions,
            challenge_observations=tuple(
                sorted(
                    (key, int(value))
                    for key, value in payload.get("challenge_observations", {}).items()
                )
            ),
            updated_at_utc=datetime.fromisoformat(updated) if updated else None,
        )
