import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.simulator.academy import (
    Achievement,
    DecisionAction,
    DecisionOutcome,
    RecommendationDecision,
)
from backend.simulator.benchmark import BenchmarkEngine
from backend.simulator.profile import LearnerProfile, LearnerProfileStore
from backend.simulator.scenarios import default_scenario_catalog, get_scenario
from backend.simulator.session import SimulatorSession


NOW = datetime(2026, 9, 13, 16, 30, tzinfo=timezone.utc)


def test_profile_progress_is_idempotent_and_persistent(tmp_path):
    decision = RecommendationDecision(
        "d-1", "r-1", DecisionAction.REJECT, NOW, DecisionOutcome.BAD
    )
    achievement = Achievement("risk-badge", NOW, "CHALLENGE")

    profile = LearnerProfile("learner-1")
    profile = profile.record_lesson("risk-101", NOW)
    profile = profile.record_lesson("risk-101", NOW)
    profile = profile.record_decision(decision)
    profile = profile.record_decision(decision)
    profile = profile.record_achievements((achievement, achievement), NOW)
    profile = profile.set_challenge_observations("drawdown-under-5pct", 20, NOW)

    store = LearnerProfileStore(tmp_path / "learner.json")
    store.save(profile)
    restored = store.load()

    assert restored.completed_lesson_ids == ("risk-101",)
    assert len(restored.decisions) == 1
    assert len(restored.achievements) == 1
    assert dict(restored.challenge_observations)["drawdown-under-5pct"] == 20
    assert restored.updated_at_utc == NOW


def test_profile_store_rejects_unknown_schema(tmp_path):
    path = tmp_path / "learner.json"
    path.write_text(json.dumps({"schema_version": 999, "learner_id": "x"}))
    with pytest.raises(ValueError, match="unsupported"):
        LearnerProfileStore(path).load()


def test_scenario_catalog_is_deterministic_and_has_training_objectives():
    catalog = default_scenario_catalog()
    assert [item.scenario_id for item in catalog] == [
        "steady-uptrend",
        "drawdown-recovery",
        "range-false-breakout",
    ]
    assert all(item.learning_objective for item in catalog)
    assert get_scenario("drawdown-recovery").price_path[1] == Decimal("88")


def test_benchmark_engine_calculates_excess_return():
    result = BenchmarkEngine.compare(
        Decimal("1000"),
        Decimal("1100"),
        (Decimal("100"), Decimal("105")),
    )
    assert result.learner_return_pct == Decimal("0.1")
    assert result.benchmark_return_pct == Decimal("0.05")
    assert result.excess_return_pct == Decimal("0.05")


def test_mobile_session_state_remains_simulation_only():
    profile = LearnerProfile("learner-1")
    scenario = get_scenario("steady-uptrend")

    state = SimulatorSession.build_state(
        profile=profile,
        scenario=scenario,
        step_index=1,
        as_of_utc=NOW,
        starting_equity=Decimal("10000"),
        current_equity=Decimal("10100"),
    )

    assert state.status == "IN_PROGRESS"
    assert state.projection["mode"] == "SIMULATION"
    assert state.projection["execution_allowed"] is False
    assert state.projection["broker_execution_armed"] is False
    assert state.projection["money_movement_allowed"] is False
    assert state.projection["scenario"]["scenario_id"] == "steady-uptrend"
    assert state.projection["learner"]["learner_id"] == "learner-1"


def test_session_has_no_live_broker_mutation_surface():
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
    assert prohibited.isdisjoint(set(dir(SimulatorSession)))
