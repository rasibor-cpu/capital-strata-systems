from datetime import datetime, timezone
from decimal import Decimal

from backend.simulator.academy import (
    DecisionAction,
    DecisionOutcome,
    RecommendationDecision,
)
from backend.simulator.mobile_contract import build_phone_preview_contract
from backend.simulator.profile import LearnerProfile
from backend.simulator.readiness import ReadinessEngine, ReadinessLevel
from backend.simulator.replay import (
    CheckpointState,
    RecommendationCheckpoint,
    RecommendationReplayEngine,
)
from backend.simulator.scenarios import get_scenario
from backend.simulator.session import SimulatorSession


NOW = datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc)


def test_recommendation_replay_scores_correct_partial_and_pending():
    checkpoints = (
        RecommendationCheckpoint(
            "cp1", "r1", "Respect invalidation", DecisionAction.REJECT, DecisionOutcome.BAD
        ),
        RecommendationCheckpoint(
            "cp2", "r2", "Take valid setup", DecisionAction.ACCEPT, DecisionOutcome.GOOD
        ),
        RecommendationCheckpoint(
            "cp3", "r3", "Wait for evidence", DecisionAction.REJECT, DecisionOutcome.BAD
        ),
    )
    decisions = (
        RecommendationDecision(
            "d1", "r1", DecisionAction.REJECT, NOW, DecisionOutcome.BAD
        ),
        RecommendationDecision(
            "d2", "r2", DecisionAction.ACCEPT, NOW, DecisionOutcome.UNKNOWN
        ),
    )

    results, score = RecommendationReplayEngine.evaluate(checkpoints, decisions)

    assert [item.state for item in results] == [
        CheckpointState.CORRECT,
        CheckpointState.PARTIAL,
        CheckpointState.PENDING,
    ]
    assert score.earned_weight == Decimal("1.5")
    assert score.possible_weight == Decimal("3")
    assert score.score_pct == Decimal("0.5")


def test_readiness_never_authorizes_live_execution():
    assessment = ReadinessEngine.assess(
        completed_lessons=10,
        completed_scenarios=8,
        decision_quality_pct=Decimal("0.95"),
        max_drawdown_pct=Decimal("0.03"),
    )

    assert assessment.level == ReadinessLevel.CONTROLLED_LIVE_REVIEW
    assert assessment.live_execution_authorized is False
    assert any("explicit human approval" in reason for reason in assessment.reasons)


def test_lower_readiness_stays_fail_closed():
    assessment = ReadinessEngine.assess(
        completed_lessons=1,
        completed_scenarios=0,
        decision_quality_pct=Decimal("0.4"),
        max_drawdown_pct=Decimal("0.2"),
    )

    assert assessment.level == ReadinessLevel.FOUNDATION
    assert assessment.live_execution_authorized is False


def test_phone_preview_contract_is_stable_and_simulation_only():
    profile = LearnerProfile("learner-mobile")
    scenario = get_scenario("range-false-breakout")
    session = SimulatorSession.build_state(
        profile=profile,
        scenario=scenario,
        step_index=1,
        as_of_utc=NOW,
        starting_equity=Decimal("10000"),
        current_equity=Decimal("9900"),
    )
    readiness = ReadinessEngine.assess(
        completed_lessons=4,
        completed_scenarios=2,
        decision_quality_pct=Decimal("0.75"),
        max_drawdown_pct=Decimal("0.08"),
    )

    payload = build_phone_preview_contract(
        session=session,
        readiness=readiness,
    )

    assert payload["schema_version"] == "simulator-preview.v1"
    assert payload["mode"] == "SIMULATION"
    assert payload["execution_allowed"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["live_execution_authorized"] is False
    assert payload["commercialization_attribution_allowed"] is False
    assert payload["fee_entitlement_allowed"] is False
    assert payload["live_trading_eligible"] is False
    assert payload["readiness"]["level"] == "BROKER_READONLY_READY"
    assert payload["session"]["scenario_id"] == "range-false-breakout"


def test_phase4_surface_contains_no_broker_mutation_methods():
    prohibited = {
        "place_order",
        "submit_order",
        "cancel_order",
        "replace_order",
        "withdraw",
        "transfer",
        "deposit",
        "fund_account",
        "move_money",
    }
    assert prohibited.isdisjoint(set(dir(RecommendationReplayEngine)))
    assert prohibited.isdisjoint(set(dir(ReadinessEngine)))
