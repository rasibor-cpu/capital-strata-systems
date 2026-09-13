from datetime import datetime, timezone
from decimal import Decimal

from backend.simulator import AcademyScorer, ChallengeDefinition, ChallengeType, SimulationEngine
from backend.simulator.academy import (
    AcademyProgression,
    DecisionAction,
    DecisionOutcome,
    Lesson,
    LessonStatus,
    RecommendationDecision,
    default_challenge_catalog,
)
from backend.simulator.projection import build_simulator_projection


NOW = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)


def test_lesson_progression_locks_and_unlocks_prerequisites():
    lessons = (
        Lesson("risk-101", "Risk foundations", 1),
        Lesson("drawdown-201", "Drawdown control", 2, ("risk-101",)),
        Lesson("discipline-301", "Decision discipline", 3, ("drawdown-201",)),
    )

    states = AcademyProgression.lesson_states(lessons, {"risk-101"})

    assert [state.status for state in states] == [
        LessonStatus.COMPLETED,
        LessonStatus.AVAILABLE,
        LessonStatus.LOCKED,
    ]


def test_decision_journal_generates_quality_inputs_without_execution():
    decisions = (
        RecommendationDecision(
            "d1", "r1", DecisionAction.ACCEPT, NOW, DecisionOutcome.GOOD
        ),
        RecommendationDecision(
            "d2", "r2", DecisionAction.REJECT, NOW, DecisionOutcome.BAD
        ),
        RecommendationDecision(
            "d3", "r3", DecisionAction.MODIFY, NOW, DecisionOutcome.UNKNOWN
        ),
    )

    assert AcademyProgression.decision_quality(decisions) == (1, 1, 3)


def test_default_challenge_catalog_contains_four_training_dimensions():
    catalog = default_challenge_catalog()
    assert {item.challenge_type for item in catalog} == {
        ChallengeType.CAPITAL_PRESERVATION,
        ChallengeType.BENCHMARK_OUTPERFORMANCE,
        ChallengeType.DRAWDOWN_CONTROL,
        ChallengeType.DECISION_DISCIPLINE,
    }


def test_completed_challenge_creates_achievement_history():
    portfolio = SimulationEngine.create(Decimal("1000"), NOW)
    score = AcademyScorer.score(portfolio)
    challenge = ChallengeDefinition(
        "preserve-capital",
        ChallengeType.CAPITAL_PRESERVATION,
        Decimal("1"),
        minimum_observations=1,
    )
    progress = AcademyScorer.evaluate_challenge(challenge, score, observations=1)

    achievements = AcademyProgression.achievements_from_challenges([progress], NOW)

    assert len(achievements) == 1
    assert achievements[0].achievement_id == "preserve-capital"
    assert achievements[0].source == "CHALLENGE"


def test_projection_is_read_only_and_explicitly_simulation_mode():
    portfolio = SimulationEngine.create(Decimal("1000"), NOW)
    score = AcademyScorer.score(portfolio)
    payload = build_simulator_projection(portfolio=portfolio, score=score)

    assert payload["mode"] == "SIMULATION"
    assert payload["execution_allowed"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["portfolio"]["cash"] == "1000"
    assert "place_order" not in payload
    assert "submit_order" not in payload


def test_projection_serializes_decisions_and_lesson_state():
    portfolio = SimulationEngine.create(Decimal("500"), NOW)
    score = AcademyScorer.score(portfolio)
    lesson = AcademyProgression.lesson_states(
        (Lesson("risk-101", "Risk foundations", 1),),
        set(),
    )
    decision = RecommendationDecision(
        "d1", "r1", DecisionAction.REJECT, NOW, DecisionOutcome.BAD, "Avoided risk"
    )

    payload = build_simulator_projection(
        portfolio=portfolio,
        score=score,
        lessons=lesson,
        decisions=(decision,),
    )

    assert payload["lessons"][0]["status"] == "AVAILABLE"
    assert payload["decisions"][0]["action"] == "REJECT"
    assert payload["decisions"][0]["outcome"] == "BAD"
