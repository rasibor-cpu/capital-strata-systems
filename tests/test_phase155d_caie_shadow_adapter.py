from datetime import datetime, timezone
from decimal import Decimal

from backend.allocation import OpportunityProposal
from backend.allocation.caie_shadow_adapter import CAIEShadowAdapter
from dashboard.runtime.caie_shadow_bridge import build_caie_shadow_runtime_projection


NOW = datetime(2026, 9, 15, 0, 5, tzinfo=timezone.utc)


def proposal():
    return OpportunityProposal(
        proposal_id="opp-1",
        source="runtime-shadow-test",
        broker="PAPER",
        symbol="AAPL",
        asset_class="EQUITY",
        side="BUY",
        probability_win=Decimal("0.85"),
        confidence=Decimal("0.80"),
        capital_required=Decimal("500"),
        max_drawdown_pct=Decimal("0.03"),
        expected_return_pct=Decimal("0.10"),
        liquidity_score=Decimal("0.95"),
        regime_alignment=Decimal("0.95"),
        observed_at_utc=NOW,
    )


def kwargs():
    return {
        "available_capital": Decimal("1000"),
        "asset_class_caps": {"EQUITY": Decimal("1")},
        "broker_caps": {"PAPER": Decimal("1")},
        "concentration_cap": Decimal("0.50"),
    }


def test_existing_eligibility_gate_remains_authoritative():
    result = CAIEShadowAdapter.evaluate([proposal()], trade_eligible=False, **kwargs())
    assert result.status == "NOT_ELIGIBLE"
    assert result.plan is None
    assert result.execution_allowed is False
    assert result.broker_execution_armed is False


def test_shadow_recommendation_generated_for_eligible_opportunity():
    result = CAIEShadowAdapter.evaluate([proposal()], trade_eligible=True, **kwargs())
    assert result.status == "AVAILABLE"
    assert result.plan is not None
    assert len(result.plan.allocations) == 1
    assert result.plan.status == "SHADOW_ONLY"


def test_no_opportunities_returns_safe_empty_output():
    result = CAIEShadowAdapter.evaluate([], trade_eligible=True, **kwargs())
    assert result.status == "NO_OPPORTUNITIES"
    assert result.plan is not None
    assert result.plan.allocations == ()


def test_caie_failure_does_not_crash_runtime():
    bad = kwargs()
    bad["available_capital"] = Decimal("-1")
    result = CAIEShadowAdapter.evaluate([proposal()], trade_eligible=True, **bad)
    assert result.status == "UNAVAILABLE"
    assert result.reason.startswith("CAIE_SHADOW_ERROR:")
    assert result.plan is None


def test_runtime_projection_is_read_only_and_fail_closed():
    payload = build_caie_shadow_runtime_projection(
        [proposal()],
        trade_eligible=True,
        **kwargs(),
    )
    assert payload["status"] == "AVAILABLE"
    assert payload["mode"] == "SHADOW_ONLY"
    assert payload["execution_allowed"] is False
    assert payload["broker_execution_armed"] is False
    assert payload["money_movement_allowed"] is False
    assert payload["live_trading_authorized"] is False
    assert len(payload["allocations"]) == 1


def test_adapter_surface_contains_no_broker_mutation_methods():
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
    assert prohibited.isdisjoint(set(dir(CAIEShadowAdapter)))
