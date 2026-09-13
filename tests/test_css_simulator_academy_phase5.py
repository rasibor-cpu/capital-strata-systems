import json
from datetime import datetime, timezone
from decimal import Decimal

from backend.simulator.academy import DecisionAction, DecisionOutcome
from backend.simulator.debrief import DebriefEngine
from backend.simulator.interactive import InteractiveScenarioEngine, InteractiveStatus
from backend.simulator.preview_fixture import build_demo_phone_preview
from backend.simulator.profile import LearnerProfile
from backend.simulator.readiness import ReadinessEngine
from backend.simulator.replay import RecommendationCheckpoint, RecommendationReplayEngine
from backend.simulator.scenarios import get_scenario
from backend.simulator.session_store import InteractiveSessionStore


NOW = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)


def test_interactive_session_can_persist_and_resume(tmp_path):
    scenario = get_scenario("steady-uptrend")
    session = InteractiveScenarioEngine.start("learner-1", scenario, NOW)
    session = session.advance(scenario, NOW)

    store = InteractiveSessionStore(tmp_path / "session.json")
    store.save(session)
    restored = store.load()

    assert restored == session
    assert restored.step_index == 1
    assert restored.status == InteractiveStatus.IN_PROGRESS


def test_checkpoint_prompt_and_decision_update_profile():
    scenario = get_scenario("range-false-breakout")
    profile = LearnerProfile("learner-1")
    session = InteractiveScenarioEngine.start("learner-1", scenario, NOW)
    checkpoint = RecommendationCheckpoint(
        "cp1",
        "r1",
        "Respect invalidation",
        DecisionAction.REJECT,
        DecisionOutcome.BAD,
    )

    prompt = InteractiveScenarioEngine.prompt_for_checkpoint(checkpoint)
    updated_profile, updated_session = InteractiveScenarioEngine.record_prompt_decision(
        profile,
        session,
        checkpoint=checkpoint,
        decision_id="d1",
        action=DecisionAction.REJECT,
        at_utc=NOW,
    )

    assert prompt.choices == ("ACCEPT", "REJECT", "MODIFY")
    assert len(updated_profile.decisions) == 1
    assert updated_session.decision_ids == ("d1",)


def test_debrief_turns_replay_and_readiness_into_next_actions():
    checkpoint = RecommendationCheckpoint(
        "cp1",
        "r1",
        "Respect invalidation",
        DecisionAction.REJECT,
        DecisionOutcome.BAD,
    )
    profile_decision = InteractiveScenarioEngine.record_prompt_decision(
        LearnerProfile("learner-1"),
        InteractiveScenarioEngine.start("learner-1", get_scenario("range-false-breakout"), NOW),
        checkpoint=checkpoint,
        decision_id="d1",
        action=DecisionAction.REJECT,
        at_utc=NOW,
    )[0].decisions[0]
    profile_decision = profile_decision.__class__(
        profile_decision.decision_id,
        profile_decision.recommendation_id,
        profile_decision.action,
        profile_decision.recorded_at_utc,
        DecisionOutcome.BAD,
        profile_decision.note,
    )
    _, replay_score = RecommendationReplayEngine.evaluate((checkpoint,), (profile_decision,))
    readiness = ReadinessEngine.assess(
        completed_lessons=4,
        completed_scenarios=2,
        decision_quality_pct=Decimal("0.82"),
        max_drawdown_pct=Decimal("0.07"),
    )

    debrief = DebriefEngine.build(replay_score, readiness)

    assert debrief.replay_score_pct == Decimal("1")
    assert "strong training result" in debrief.headline.lower()


def test_demo_phone_preview_fixture_is_json_serializable_and_fail_closed():
    payload = build_demo_phone_preview()
    encoded = json.dumps(payload)

    assert encoded
    assert payload["schema_version"] == "simulator-preview.v1"
    assert payload["mode"] == "SIMULATION"
    assert payload["execution_allowed"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["live_execution_authorized"] is False
    assert payload["replay_score"]["score_pct"] == "1"
