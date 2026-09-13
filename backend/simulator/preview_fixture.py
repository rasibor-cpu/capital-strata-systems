from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from .academy import DecisionAction, DecisionOutcome, RecommendationDecision
from .mobile_contract import build_phone_preview_contract
from .profile import LearnerProfile
from .readiness import ReadinessEngine
from .replay import RecommendationCheckpoint, RecommendationReplayEngine
from .scenarios import get_scenario
from .session import SimulatorSession


def build_demo_phone_preview() -> dict:
    now = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)
    profile = LearnerProfile(
        "demo-learner",
        completed_lesson_ids=("risk-101", "drawdown-201", "discipline-301", "benchmark-401"),
        decisions=(
            RecommendationDecision(
                "demo-d1",
                "demo-r1",
                DecisionAction.REJECT,
                now,
                DecisionOutcome.BAD,
                "Rejected a false breakout after invalidation.",
            ),
        ),
        challenge_observations=(("decision-quality-80pct", 12),),
        updated_at_utc=now,
    )
    scenario = get_scenario("range-false-breakout")
    session = SimulatorSession.build_state(
        profile=profile,
        scenario=scenario,
        step_index=2,
        as_of_utc=now,
        starting_equity=Decimal("10000"),
        current_equity=Decimal("10150"),
    )
    readiness = ReadinessEngine.assess(
        completed_lessons=4,
        completed_scenarios=2,
        decision_quality_pct=Decimal("0.82"),
        max_drawdown_pct=Decimal("0.07"),
    )
    checkpoint = RecommendationCheckpoint(
        "demo-cp1",
        "demo-r1",
        "Respect the false-breakout invalidation",
        DecisionAction.REJECT,
        DecisionOutcome.BAD,
    )
    results, replay_score = RecommendationReplayEngine.evaluate(
        (checkpoint,), profile.decisions
    )
    return build_phone_preview_contract(
        session=session,
        readiness=readiness,
        checkpoint_results=results,
        replay_score=replay_score,
    )
