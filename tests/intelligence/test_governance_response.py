from backend.intelligence.global_intelligence.event_models import RegimeState
from backend.intelligence.global_intelligence.governance_response_engine import build_governance_response


def test_build_governance_response_mappings():
    normal = build_governance_response(RegimeState.NORMAL)
    assert normal.leverage_multiplier == 1.0
    assert normal.reduce_allocation_pct == 0.0

    caution = build_governance_response(RegimeState.CAUTION)
    assert caution.reduce_allocation_pct == 10.0
    assert caution.leverage_multiplier == 0.85

    defensive = build_governance_response(RegimeState.DEFENSIVE)
    assert defensive.suppress_scalping is True
    assert defensive.leverage_multiplier == 0.50

    panic = build_governance_response(RegimeState.PANIC)
    assert panic.freeze_new_positions is True
    assert panic.leverage_multiplier == 0.10

    crisis = build_governance_response(RegimeState.LIQUIDITY_CRISIS)
    assert crisis.leverage_multiplier == 0.0
    assert crisis.reduce_allocation_pct == 90.0

    opportunity = build_governance_response(RegimeState.OPPORTUNITY_EXPANSION)
    assert opportunity.leverage_multiplier == 1.10
    assert "controlled opportunity expansion only" in " ".join(opportunity.notes).lower()
