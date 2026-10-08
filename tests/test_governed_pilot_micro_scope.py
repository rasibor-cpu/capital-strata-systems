from datetime import datetime, timezone
from decimal import Decimal

from backend.runtime.governed_pilot_profile import (
    PILOT_SCOPE_MICRO,
    GovernedPilotProfile,
    evaluate_pilot_preflight,
)
from pilot_dual_control_fixtures import (
    RELEASE_SHA,
    EphemeralTestSecretProvider,
    approvals,
    mapping,
    registry,
)

PROVIDER = EphemeralTestSecretProvider()


def micro_profile(max_order_count: int = 10) -> GovernedPilotProfile:
    return GovernedPilotProfile.from_mapping(
        mapping(scope=PILOT_SCOPE_MICRO, max_order_count=max_order_count)
    )


def evaluate(p, **overrides):
    data = dict(
        approvals=approvals(p, PROVIDER),
        key_registry=registry(PROVIDER),
        running_release_sha=RELEASE_SHA,
        broker_id="broker-a",
        account_id="acct-a",
        asset_class="EQUITY",
        instrument="ABC",
        currency="CAD",
        session_id="unique-process-session",
        current_exposure_cad="10.00",
        pending_orders_cad="2.00",
        proposed_order_cad="5.00",
        estimated_fees_cad="0.50",
        reconciled=True,
        reconciled_at=datetime.now(timezone.utc),
        expected_net_edge_bps="40",
        required_net_edge_bps="25",
        orders_already_submitted=3,
        margin_requested=False,
    )
    data.update(overrides)
    return evaluate_pilot_preflight(p, **data)


def test_micro_scope_allows_more_than_one_child_order_within_parent_budget():
    decision = evaluate(micro_profile())
    assert decision.approved
    assert decision.projected_exposure_cad == Decimal("17.50")


def test_micro_scope_exhausts_configured_child_order_budget():
    decision = evaluate(micro_profile(max_order_count=4), orders_already_submitted=4)
    assert not decision.approved
    assert decision.reason == "PILOT_ORDER_BUDGET_EXHAUSTED"


def test_micro_scope_still_caps_one_parent_at_cad20():
    decision = evaluate(
        micro_profile(),
        current_exposure_cad="18.00",
        pending_orders_cad="1.00",
        proposed_order_cad="1.00",
        estimated_fees_cad="0.01",
    )
    assert not decision.approved
    assert decision.reason == "PILOT_EXPOSURE_CEILING"


def test_micro_scope_never_allows_more_than_canonical_session_order_count():
    from backend.runtime.governed_pilot_profile import PilotConfigurationError
    import pytest

    with pytest.raises(PilotConfigurationError):
        micro_profile(max_order_count=11)
