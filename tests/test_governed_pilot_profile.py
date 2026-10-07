from datetime import datetime, timedelta, timezone

import pytest

from backend.runtime.governed_pilot_profile import (
    GovernedPilotProfile, PilotConfigurationError, evaluate_pilot_preflight,
)


def profile(limit="20.00"):
    return GovernedPilotProfile.from_mapping({
        "approval_id": "change-001", "broker_id": "broker-a",
        "account_id": "acct-a", "instrument": "ABC",
        "currency": "CAD", "max_aggregate_exposure": limit,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        "session_id": "unique-process-session",
    })


def evaluate(p, **overrides):
    data = dict(
        broker_id="broker-a", account_id="acct-a", instrument="ABC",
        session_id="unique-process-session", current_exposure_cad="2",
        pending_orders_cad="1", proposed_order_cad="15",
        estimated_fees_cad="1", reconciled=True,
        reconciled_at=datetime.now(timezone.utc),
        expected_net_edge_bps="40", required_net_edge_bps="25",
        orders_already_submitted=0, margin_requested=False,
    )
    data.update(overrides)
    return evaluate_pilot_preflight(p, **data)


def test_ceiling_is_governed_not_hardcoded():
    assert evaluate(profile("20")).approved
    assert not evaluate(profile("18")).approved
    assert evaluate(profile("40")).approved


def test_fees_pending_and_current_exposure_included():
    assert not evaluate(profile(), proposed_order_cad="17").approved


def test_expiry_and_session_binding():
    assert not evaluate(profile(), session_id="new-session").approved
    assert not evaluate(profile(), now=datetime.now(timezone.utc) + timedelta(hours=1)).approved


def test_reconciliation_and_one_order_limit():
    assert not evaluate(profile(), reconciled=False).approved
    assert not evaluate(profile(), reconciled_at=datetime.now(timezone.utc) - timedelta(minutes=1)).approved
    assert not evaluate(profile(), orders_already_submitted=1).approved


def test_cost_and_margin_fail_closed():
    assert not evaluate(profile(), expected_net_edge_bps="10").approved
    assert not evaluate(profile(), margin_requested=True).approved
    assert not evaluate(profile(), proposed_order_cad="NaN").approved


def test_invalid_profiles_rejected():
    with pytest.raises(PilotConfigurationError):
        GovernedPilotProfile.from_mapping({"max_aggregate_exposure": "20"})
    with pytest.raises(PilotConfigurationError):
        GovernedPilotProfile.from_mapping({
            "approval_id": "x", "broker_id": "b", "account_id": "a",
            "instrument": "I", "currency": "USD", "session_id": "s",
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
            "max_aggregate_exposure": "20"
        })
