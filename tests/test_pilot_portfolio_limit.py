from decimal import Decimal

from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG
from backend.runtime.pilot_portfolio_limit import (
    PilotParentExposure,
    evaluate_pilot_portfolio,
)


def parent(parent_id: str, committed: str, pending: str = "0.00") -> PilotParentExposure:
    return PilotParentExposure(
        parent_id=parent_id,
        committed_cad=Decimal(committed),
        pending_cad=Decimal(pending),
    )


def test_default_pilot_limits_are_two_by_twenty_with_forty_total():
    cfg = DEFAULT_ORDER_LIMIT_CONFIG
    assert cfg.live_pilot_max_position_cad == Decimal("20.00")
    assert cfg.live_pilot_max_concurrent_positions == 2
    assert cfg.live_pilot_max_total_cad == Decimal("40.00")


def test_multiple_micro_orders_share_one_cad20_parent_envelope():
    d1 = evaluate_pilot_portfolio([], parent_id="EXP-1", proposed_child_cad="5.00")
    assert d1.approved and d1.projected_parent_cad == Decimal("5.00")

    d2 = evaluate_pilot_portfolio(
        [parent("EXP-1", "5.00")],
        parent_id="EXP-1",
        proposed_child_cad="7.50",
    )
    assert d2.approved and d2.projected_parent_cad == Decimal("12.50")

    d3 = evaluate_pilot_portfolio(
        [parent("EXP-1", "12.50")],
        parent_id="EXP-1",
        proposed_child_cad="7.50",
    )
    assert d3.approved and d3.projected_parent_cad == Decimal("20.00")


def test_parent_envelope_cannot_exceed_cad20():
    decision = evaluate_pilot_portfolio(
        [parent("EXP-1", "18.00")],
        parent_id="EXP-1",
        proposed_child_cad="2.01",
    )
    assert not decision.approved
    assert decision.reason == "PILOT_PARENT_EXPOSURE_CEILING"


def test_two_concurrent_parent_exposures_are_allowed():
    decision = evaluate_pilot_portfolio(
        [parent("EXP-1", "20.00")],
        parent_id="EXP-2",
        proposed_child_cad="20.00",
    )
    assert decision.approved
    assert decision.projected_parent_count == 2
    assert decision.projected_total_cad == Decimal("40.00")


def test_third_concurrent_parent_exposure_is_blocked():
    decision = evaluate_pilot_portfolio(
        [parent("EXP-1", "10.00"), parent("EXP-2", "10.00")],
        parent_id="EXP-3",
        proposed_child_cad="1.00",
    )
    assert not decision.approved
    assert decision.reason == "PILOT_CONCURRENT_EXPOSURE_CEILING"


def test_fees_count_against_the_same_parent_and_total_budget():
    decision = evaluate_pilot_portfolio(
        [parent("EXP-1", "19.50")],
        parent_id="EXP-1",
        proposed_child_cad="0.40",
        estimated_fees_cad="0.11",
    )
    assert not decision.approved
    assert decision.reason == "PILOT_PARENT_EXPOSURE_CEILING"


def test_bad_inputs_fail_closed():
    assert not evaluate_pilot_portfolio([], parent_id="", proposed_child_cad="1").approved
    assert not evaluate_pilot_portfolio([], parent_id="EXP-1", proposed_child_cad="NaN").approved
    assert not evaluate_pilot_portfolio([], parent_id="EXP-1", proposed_child_cad=True).approved


def test_existing_unsafe_state_fails_closed():
    decision = evaluate_pilot_portfolio(
        [parent("EXP-1", "20.01")],
        parent_id="EXP-1",
        proposed_child_cad="0.01",
    )
    assert not decision.approved
    assert decision.reason == "PILOT_PORTFOLIO_EVALUATION_ERROR"
