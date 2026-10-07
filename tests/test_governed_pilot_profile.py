import dataclasses
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.runtime.governed_pilot_profile import (
    GovernedPilotProfile, PilotConfigurationError, evaluate_pilot_preflight, sign_profile,
    verify_profile_signature,
)

KEY = b"k" * 32


def mapping(**overrides):
    now = datetime.now(timezone.utc)
    data = {
        "approval_id": "change-001", "approver_id": "owner-1",
        "scope": "PILOT_PREFLIGHT_ONE_ORDER", "broker_id": "broker-a",
        "account_id": "acct-a", "asset_class": "EQUITY", "instrument": "ABC",
        "currency": "CAD", "max_aggregate_exposure": "20.00",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "session_id": "unique-process-session",
    }
    data.update(overrides)
    return data


def profile(limit="20.00", **overrides):
    return GovernedPilotProfile.from_mapping(mapping(max_aggregate_exposure=limit, **overrides))


def evaluate(p, signature=None, **overrides):
    data = dict(
        signature=sign_profile(p, KEY) if signature is None else signature, signing_key=KEY,
        broker_id="broker-a", account_id="acct-a", asset_class="EQUITY", instrument="ABC",
        currency="CAD", session_id="unique-process-session", current_exposure_cad="2",
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


def test_profile_cannot_raise_canonical_order_limit_cap():
    # projected 19 + 2 = 21 > canonical CAD 20 even though the profile says 40.
    decision = evaluate(profile("40"), proposed_order_cad="17")
    assert not decision.approved and decision.reason == "PILOT_EXPOSURE_CEILING"


def test_fees_pending_and_current_exposure_included():
    assert not evaluate(profile(), proposed_order_cad="17").approved


def test_expiry_and_session_binding():
    assert not evaluate(profile(), session_id="new-session").approved
    assert not evaluate(profile(), now=datetime.now(timezone.utc) + timedelta(hours=1)).approved
    assert not evaluate(profile(), now=datetime.now(timezone.utc) - timedelta(hours=1)).approved


@pytest.mark.parametrize("field,value", [
    ("broker_id", "broker-b"), ("account_id", "acct-b"), ("asset_class", "FX_SPOT"),
    ("instrument", "XYZ"), ("currency", "USD"),
])
def test_scope_mismatch_blocks(field, value):
    decision = evaluate(profile(), **{field: value})
    assert not decision.approved and decision.reason == "PILOT_SCOPE_MISMATCH"


def test_reconciliation_and_one_order_limit():
    assert not evaluate(profile(), reconciled=False).approved
    assert not evaluate(profile(), reconciled="yes").approved
    assert not evaluate(profile(), reconciled_at=datetime.now(timezone.utc) - timedelta(minutes=1)).approved
    assert not evaluate(profile(), orders_already_submitted=1).approved
    assert not evaluate(profile(), orders_already_submitted=False).approved


def test_cost_and_margin_fail_closed():
    assert not evaluate(profile(), expected_net_edge_bps="10").approved
    assert not evaluate(profile(), margin_requested=True).approved
    assert not evaluate(profile(), margin_requested=None).approved
    assert not evaluate(profile(), proposed_order_cad="NaN").approved


def test_malformed_inputs_fail_closed_without_raising():
    decision = evaluate(profile(), instrument=None, now="not-a-datetime")
    assert not decision.approved
    assert not evaluate(profile(), reconciled_at="2026-01-01").approved


def test_invalid_profiles_rejected():
    with pytest.raises(PilotConfigurationError):
        GovernedPilotProfile.from_mapping({"max_aggregate_exposure": "20"})
    for bad in (
        {"currency": "USD"}, {"asset_class": "OPTION"}, {"asset_class": "FUTURE"},
        {"scope": "LIVE_UNLIMITED"}, {"max_aggregate_exposure": "0"},
        {"max_aggregate_exposure": "20.001"}, {"max_aggregate_exposure": True},
        {"max_order_count": 2}, {"max_order_count": True}, {"allow_margin": True},
        {"allow_margin": "false"}, {"broker_id": "bad id with spaces"},
        {"expires_at": "2026-01-01T00:00:00"},
        {"expires_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()},
    ):
        with pytest.raises(PilotConfigurationError):
            GovernedPilotProfile.from_mapping(mapping(**bad))


def test_unknown_fields_fail_closed():
    with pytest.raises(PilotConfigurationError, match="unapproved configuration fields"):
        GovernedPilotProfile.from_mapping(mapping(override_antibleed=True))


def test_direct_construction_and_replace_are_validated():
    good = profile()
    kwargs = {f.name: getattr(good, f.name) for f in dataclasses.fields(good)}
    with pytest.raises(PilotConfigurationError):
        GovernedPilotProfile(**{**kwargs, "currency": "USD"})
    with pytest.raises(PilotConfigurationError):
        GovernedPilotProfile(**{**kwargs, "max_aggregate_exposure": 1e9})
    with pytest.raises(PilotConfigurationError):
        dataclasses.replace(good, max_order_count=5)
    with pytest.raises(PilotConfigurationError):
        dataclasses.replace(good, allow_margin=True)


def test_signature_required_and_tamper_evident():
    p = profile()
    sig = sign_profile(p, KEY)
    assert verify_profile_signature(p, sig, KEY)
    assert not evaluate(p, signature="0" * 64).approved
    assert not evaluate(p, signing_key=b"x" * 32).approved
    assert not evaluate(p, signing_key=b"short").approved
    # Re-issued profile with a larger ceiling does not carry the old signature.
    widened = dataclasses.replace(p, max_aggregate_exposure=Decimal("19.00"))
    assert evaluate(widened, signature=sig).reason == "PILOT_SIGNATURE_INVALID"
    # In-memory mutation of the frozen instance is detected.
    object.__setattr__(p, "max_aggregate_exposure", Decimal("10000.00"))
    assert evaluate(p, signature=sig).reason == "PILOT_SIGNATURE_INVALID"


def test_subclass_or_lookalike_profiles_rejected():
    class Sneaky(GovernedPilotProfile):
        pass
    good = profile()
    sneaky = Sneaky(**{f.name: getattr(good, f.name) for f in dataclasses.fields(good)})
    assert not evaluate(sneaky, signature=sign_profile(good, KEY)).approved
    assert not evaluate(None, signature="x").approved
