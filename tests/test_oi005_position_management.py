from __future__ import annotations

import inspect
import json
from dataclasses import replace
from datetime import date, timedelta

import pytest

import backend.options.options_position_manager as manager_module
from backend.options.options_income_opportunity_scanner import IncomeOpportunityScanner
from backend.options.options_position_manager import OptionsPositionManager
from backend.options.paper_income_lifecycle import PaperIncomeLifecycleEngine
from backend.options.paper_position_repository import PaperIncomePosition, PaperPositionRepository, PaperPositionRepositoryError
from backend.options.position_health import PositionHealthAnalyzer, PositionHealthError
from backend.options.position_state_machine import ACTIVE, COMPLETED
from backend.options.roll_decision_engine import RollDecisionEngine, RollDecisionError
from backend.options.rolling_candidates import RollingCandidateError, RollingCandidateGenerator
from backend.options.rolling_engine import RollingEngine, RollingEngineError
from backend.trading.option_contract import CanonicalOptionContract


AS_OF = date(2026, 7, 14)
ENTRY_DATE = AS_OF.isoformat()
EXPIRY = (AS_OF + timedelta(days=30)).isoformat()
NEAR_EXPIRY = (AS_OF + timedelta(days=25)).isoformat()
NOW = "2026-07-14T00:00:00+00:00"


def _clock() -> str:
    return NOW


def _contract(option_type: str, *, strike: float | None = None, symbol: str | None = None) -> CanonicalOptionContract:
    option_type = option_type.upper()
    strike = 105.0 if strike is None and option_type == "CALL" else (95.0 if strike is None else strike)
    return CanonicalOptionContract.from_dict(
        {
            "underlying_symbol": "SPY",
            "option_symbol": symbol or f"SPY-{EXPIRY}-{option_type[0]}-{int(strike)}",
            "expiration_date": EXPIRY,
            "strike": strike,
            "option_type": option_type,
            "bid": 1.9,
            "ask": 2.1,
            "midpoint": 2.0,
            "last": 2.0,
            "volume": 100,
            "open_interest": 500,
            "implied_volatility": 0.20,
            "delta": 0.30 if option_type == "CALL" else -0.30,
            "gamma": 0.02,
            "theta": -0.01,
            "vega": 0.10,
            "rho": 0.01,
            "intrinsic_value": 0.0,
            "extrinsic_value": 2.0,
            "probability_itm": 0.30,
            "exchange": "CBOE",
            "multiplier": 100,
            "currency": "USD",
            "timestamp": NOW,
        }
    )


def _call_candidate():
    return IncomeOpportunityScanner().scan_covered_calls(
        [_contract("CALL")],
        underlying_symbol="SPY",
        underlying_price=100.0,
        underlying_quantity=100,
        as_of=AS_OF,
    )[0]


def _put_candidate():
    return IncomeOpportunityScanner().scan_cash_secured_puts(
        [_contract("PUT")],
        underlying_symbol="SPY",
        cash_collateral_available=9500.0,
        underlying_price=100.0,
        as_of=AS_OF,
    )[0]


def _lifecycle(repository: PaperPositionRepository) -> PaperIncomeLifecycleEngine:
    return PaperIncomeLifecycleEngine(repository=repository, clock=_clock)


def _active_position(repository: PaperPositionRepository, candidate=None) -> PaperIncomePosition:
    return _active_context(repository, candidate)[1]


def _active_context(repository: PaperPositionRepository, candidate=None) -> tuple[PaperIncomeLifecycleEngine, PaperIncomePosition]:
    engine = _lifecycle(repository)
    position = engine.create_position(candidate or _call_candidate(), entry_date=ENTRY_DATE)
    engine.approve_position(position.position_id)
    engine.open_position(position.position_id)
    return engine, engine.activate_position(position.position_id)


def _completed_position(repository: PaperPositionRepository) -> PaperIncomePosition:
    engine, active = _active_context(repository, _put_candidate())
    return engine.process_expiration(active.position_id, underlying_price=100.0, as_of=EXPIRY)


def test_position_manager_lists_active_expiring_and_completed_positions():
    repository = PaperPositionRepository()
    active = _active_position(repository)
    completed = _completed_position(repository)
    manager = OptionsPositionManager(paper_repository=repository)

    all_positions = manager.list_paper_income_positions()
    active_positions = manager.list_paper_income_positions(states=[ACTIVE])
    completed_positions = manager.list_paper_income_positions(states=[COMPLETED])

    assert {item["position_id"] for item in all_positions} == {active.position_id, completed.position_id}
    assert [item["position_id"] for item in active_positions] == [active.position_id]
    assert [item["position_id"] for item in completed_positions] == [completed.position_id]


def test_position_health_scores_active_position():
    repository = PaperPositionRepository()
    active = _active_position(repository)

    health = PositionHealthAnalyzer().calculate(active, as_of=NEAR_EXPIRY, underlying_price=104.0, delta=0.42, moneyness="OTM")

    assert health.position_id == active.position_id
    assert health.days_remaining == 5
    assert health.premium_retained == 0.0
    assert health.collateral_utilization == 1.0
    assert health.roll_eligible is True
    assert 0.0 <= health.health_score <= 100.0
    assert health.to_dict()["execution_allowed"] is False


def test_position_health_detects_itm_assignment_exposure():
    repository = PaperPositionRepository()
    active = _active_position(repository)

    health = PositionHealthAnalyzer().calculate(active, as_of=NEAR_EXPIRY, underlying_price=110.0, delta=0.55, moneyness="ITM")

    assert health.assignment_exposure == "ITM"
    assert health.roll_eligible is True
    assert health.health_score < 70.0


def test_position_health_supports_completed_position_without_roll():
    repository = PaperPositionRepository()
    completed = _completed_position(repository)

    health = PositionHealthAnalyzer().calculate(completed, as_of=EXPIRY, underlying_price=100.0)

    assert health.current_state == COMPLETED
    assert health.assignment_exposure == "NONE"
    assert health.roll_eligible is False
    assert health.health_score == 100.0


def test_position_health_rejects_negative_premium():
    repository = PaperPositionRepository()
    active = _active_position(repository)
    bad = replace(active, premium_remaining=-0.01)

    with pytest.raises(PositionHealthError):
        PositionHealthAnalyzer().calculate(bad, as_of=NEAR_EXPIRY, underlying_price=100.0)


def test_roll_candidates_include_roll_out_near_expiry():
    repository = PaperPositionRepository()
    active = _active_position(repository)

    candidates = RollingCandidateGenerator().generate(
        active,
        as_of=NEAR_EXPIRY,
        underlying_price=104.0,
        delta=0.44,
        moneyness="OTM",
        strategy_quality=0.80,
    )

    assert candidates[0].recommendation in {"Roll Out", "Roll Forward"}
    assert any(item.recommendation == "Roll Out" for item in candidates)
    assert all(item.execution_allowed is False for item in candidates)


def test_roll_candidates_include_roll_up_for_itm_covered_call():
    repository = PaperPositionRepository()
    active = _active_position(repository)

    candidates = RollingCandidateGenerator().generate(
        active,
        as_of=NEAR_EXPIRY,
        underlying_price=110.0,
        delta=0.60,
        moneyness="ITM",
    )

    roll_up = [item for item in candidates if item.recommendation == "Roll Up"][0]
    assert roll_up.target_strike > active.strike
    assert roll_up.risk_impact == "REDUCES_CALL_AWAY_PRESSURE"


def test_roll_candidates_include_roll_down_for_itm_cash_secured_put():
    repository = PaperPositionRepository()
    active = _active_position(repository, _put_candidate())

    candidates = RollingCandidateGenerator().generate(
        active,
        as_of=NEAR_EXPIRY,
        underlying_price=90.0,
        delta=-0.58,
        moneyness="ITM",
    )

    roll_down = [item for item in candidates if item.recommendation == "Roll Down"][0]
    assert roll_down.target_strike < active.strike
    assert roll_down.capital_impact < 0.0
    assert roll_down.risk_impact == "REDUCES_ASSIGNMENT_PRESSURE"


def test_no_roll_recommendation_when_thresholds_not_met():
    repository = PaperPositionRepository()
    active = _active_position(repository)

    candidates = RollingCandidateGenerator().generate(
        active,
        as_of=ENTRY_DATE,
        underlying_price=100.0,
        delta=0.20,
        moneyness="OTM",
    )

    assert [item.recommendation for item in candidates] == ["No Roll"]


def test_roll_decision_selects_highest_confidence_advisory_candidate():
    repository = PaperPositionRepository()
    active = _active_position(repository)
    candidates = RollingCandidateGenerator().generate(active, as_of=NEAR_EXPIRY, underlying_price=110.0, delta=0.60, moneyness="ITM")

    decision = RollDecisionEngine().decide(candidates)

    assert decision.recommendation == candidates[0].recommendation
    assert decision.candidate_count == len(candidates)
    assert decision.to_dict()["advisory_only"] is True


def test_roll_decision_rejects_missing_candidates():
    with pytest.raises(RollDecisionError):
        RollDecisionEngine().decide([])


def test_rolling_engine_rejects_completed_positions():
    repository = PaperPositionRepository()
    completed = _completed_position(repository)

    with pytest.raises(RollingEngineError):
        RollingEngine(repository=repository).recommend(
            completed.position_id,
            as_of=EXPIRY,
            underlying_price=100.0,
            delta=0.10,
            moneyness="OTM",
        )


def test_manager_records_roll_recommendation_idempotently():
    repository = PaperPositionRepository()
    engine, active = _active_context(repository)
    manager = OptionsPositionManager(paper_repository=repository)

    first = manager.recommend_paper_income_roll(
        active.position_id,
        as_of=NEAR_EXPIRY,
        underlying_price=110.0,
        delta=0.60,
        moneyness="ITM",
        record=True,
    )
    manager.recommend_paper_income_roll(
        active.position_id,
        as_of=NEAR_EXPIRY,
        underlying_price=110.0,
        delta=0.60,
        moneyness="ITM",
        record=True,
    )
    stored = repository.get(active.position_id)

    assert first["execution_allowed"] is False
    assert [event["event_type"] for event in stored.lifecycle_events].count("Roll Recommendation") == 1


def test_manager_metrics_include_rolling_and_assignment_history():
    repository = PaperPositionRepository()
    engine, active = _active_context(repository)
    manager = OptionsPositionManager(paper_repository=repository)
    manager.recommend_paper_income_roll(
        active.position_id,
        as_of=NEAR_EXPIRY,
        underlying_price=110.0,
        delta=0.60,
        moneyness="ITM",
        record=True,
    )
    completed = engine.process_expiration(active.position_id, underlying_price=110.0, as_of=EXPIRY)

    metrics = manager.get_paper_income_metrics(completed.position_id, as_of=EXPIRY)

    assert metrics["lifetime_premium"] == 200.0
    assert metrics["premium_capture_pct"] == 1.0
    assert len(metrics["rolling_history"]) == 1
    assert [event["event_type"] for event in metrics["assignment_history"]] == ["Assigned"]


def test_manager_rejects_missing_position():
    manager = OptionsPositionManager(paper_repository=PaperPositionRepository())

    with pytest.raises(PaperPositionRepositoryError):
        manager.get_paper_income_position("missing")


def test_duplicate_position_identifiers_fail_closed():
    repository = PaperPositionRepository()
    engine = _lifecycle(repository)
    candidate = _call_candidate()
    engine.create_position(candidate, entry_date=ENTRY_DATE)

    with pytest.raises(PaperPositionRepositoryError):
        engine.create_position(candidate, entry_date=ENTRY_DATE)


def test_repository_recovery_preserves_roll_history(tmp_path):
    path = tmp_path / "paper_positions.json"
    repository = PaperPositionRepository(path)
    active = _active_position(repository)
    manager = OptionsPositionManager(paper_repository=repository)
    manager.recommend_paper_income_roll(
        active.position_id,
        as_of=NEAR_EXPIRY,
        underlying_price=110.0,
        delta=0.60,
        moneyness="ITM",
        record=True,
    )

    recovered = PaperPositionRepository(path).get(active.position_id)

    assert [event["event_type"] for event in recovered.lifecycle_events].count("Roll Recommendation") == 1


def test_repository_corruption_fails_closed(tmp_path):
    path = tmp_path / "paper_positions.json"
    path.write_text("{bad-json", encoding="utf-8")

    with pytest.raises(PaperPositionRepositoryError):
        PaperPositionRepository(path)


def test_oi004_oi003_oi002_integration_path():
    repository = PaperPositionRepository()
    candidate = _call_candidate()
    active = _active_position(repository, candidate)

    assert candidate.strategy_summary["valid"] is True
    assert active.current_state == ACTIVE
    assert active.strategy_type == "COVERED_CALL"


def test_invalid_state_fails_closed():
    repository = PaperPositionRepository()
    active = _active_position(repository)
    bad = PaperIncomePosition.from_dict({**active.to_dict(), "current_state": "BAD_STATE"})
    repository.update(bad)
    manager = OptionsPositionManager(paper_repository=repository)

    with pytest.raises(ValueError):
        manager.get_paper_income_position(active.position_id)


def test_invalid_expiry_fails_closed():
    repository = PaperPositionRepository()
    active = _active_position(repository)

    with pytest.raises(PaperPositionRepositoryError):
        PaperIncomePosition.from_dict({**active.to_dict(), "expiry": "not-a-date"})


def test_unsupported_strategy_fails_closed():
    repository = PaperPositionRepository()
    active = _active_position(repository)
    bad = PaperIncomePosition.from_dict({**active.to_dict(), "strategy_type": "IRON_CONDOR"})

    with pytest.raises(PositionHealthError):
        PositionHealthAnalyzer().calculate(bad, as_of=NEAR_EXPIRY, underlying_price=100.0)


def test_completed_position_roll_record_fails_closed():
    repository = PaperPositionRepository()
    completed = _completed_position(repository)
    manager = OptionsPositionManager(paper_repository=repository)

    with pytest.raises(RollingEngineError):
        manager.recommend_paper_income_roll(
            completed.position_id,
            as_of=EXPIRY,
            underlying_price=100.0,
            delta=0.10,
            moneyness="OTM",
            record=True,
        )


def test_json_payloads_are_serializable():
    repository = PaperPositionRepository()
    active = _active_position(repository)
    manager = OptionsPositionManager(paper_repository=repository)

    payload = {
        "position": manager.get_paper_income_position(active.position_id),
        "health": manager.get_paper_income_health(active.position_id, as_of=NEAR_EXPIRY, underlying_price=104.0),
        "roll": manager.recommend_paper_income_roll(
            active.position_id,
            as_of=NEAR_EXPIRY,
            underlying_price=104.0,
            delta=0.44,
            moneyness="OTM",
        ),
    }

    assert json.loads(json.dumps(payload, sort_keys=True))["roll"]["execution_allowed"] is False


def test_existing_long_option_manager_behavior_remains_unchanged():
    manager = OptionsPositionManager()
    opened = manager.open_long_option(
        option_symbol="SPY-20260821-C-105",
        underlying_symbol="SPY",
        option_type="CALL",
        strike=105.0,
        expiry=EXPIRY,
        entry_price=2.0,
        current_cycle=1,
    )

    assert opened["status"] == "OPENED"
    assert manager.update_positions({"SPY-20260821-C-105": 2.6}, current_cycle=2) == []
    assert manager.close_position("SPY-20260821-C-105", exit_price=2.7, reason="TEST", closed_cycle=3)["status"] == "CLOSED"


def test_no_broker_or_execution_calls_added_to_position_manager():
    source = inspect.getsource(manager_module)

    assert "broker" not in source.lower()
    assert "submit_order" not in source
    assert "place_order" not in source
    assert "execute_trade" not in source
    assert "enable_live" not in source
