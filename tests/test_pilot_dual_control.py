import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from backend.runtime.governed_pilot_profile import PilotConfigurationError
from backend.runtime.pilot_dual_control import (
    ROLE_RELEASE_SECURITY, ROLE_SPONSOR, PilotKeyRegistry, keys_currently_usable,
    sign_pilot_approval, verify_dual_control,
)
from pilot_dual_control_fixtures import (
    RELEASE_APPROVER, SPONSOR, EphemeralTestSecretProvider, approvals, mapping, profile, registry,
)


@pytest.fixture
def provider():
    return EphemeralTestSecretProvider(("sponsor-k1", "release-k1", "sponsor-k2"))


def test_both_roles_required(provider):
    p = profile()
    sponsor, release = approvals(p, provider)
    assert verify_dual_control(p, (sponsor, release), provider=provider, registry=registry())
    assert not verify_dual_control(p, (sponsor,), provider=provider, registry=registry())
    assert not verify_dual_control(p, (sponsor, sponsor), provider=provider, registry=registry())
    assert not verify_dual_control(p, (sponsor, release, release), provider=provider, registry=registry())


def test_approvals_are_independently_attributable(provider):
    p = profile()
    evidence = [a.evidence() for a in approvals(p, provider)]
    assert {e["role"] for e in evidence} == {ROLE_SPONSOR, ROLE_RELEASE_SECURITY}
    assert {e["approver_id"] for e in evidence} == {SPONSOR, RELEASE_APPROVER}
    assert {e["key_id"] for e in evidence} == {"sponsor-k1", "release-k1"}
    assert all(set(e) == {"role", "approver_id", "key_id", "approved_at", "profile_digest"} for e in evidence)


def test_key_material_never_in_evidence_or_repr(provider):
    p = profile()
    for approval in approvals(p, provider):
        rendered = repr(approval) + repr(approval.evidence()) + repr(provider)
        for key_id in ("sponsor-k1", "release-k1"):
            key = provider.get_key(key_id)
            assert key.hex() not in rendered and repr(key) not in rendered


def test_same_person_cannot_hold_both_roles():
    with pytest.raises(PilotConfigurationError):
        profile(release_approver_id=SPONSOR)


def test_approver_must_be_designated_role_holder(provider):
    p = profile()
    with pytest.raises(PilotConfigurationError):
        sign_pilot_approval(p, role=ROLE_SPONSOR, approver_id="someone-else",
                            key_id="sponsor-k1", provider=provider)


def test_key_must_belong_to_role(provider):
    p = profile()
    sponsor, release = approvals(p, provider)
    swapped = sign_pilot_approval(p, role=ROLE_SPONSOR, approver_id=SPONSOR,
                                  key_id="release-k1", provider=provider)
    assert not verify_dual_control(p, (swapped, release), provider=provider, registry=registry())


@pytest.mark.parametrize("status", ["RETIRED", "REVOKED"])
def test_retired_or_revoked_keys_fail_closed(provider, status):
    p = profile()
    pair = approvals(p, provider)
    assert not verify_dual_control(p, pair, provider=provider, registry=registry(**{"release-k1": status}))
    assert not keys_currently_usable(pair, registry(**{"sponsor-k1": status}), datetime.now(timezone.utc))


def test_unknown_key_and_out_of_window_fail_closed(provider):
    p = profile()
    pair = approvals(p, provider)
    now = datetime.now(timezone.utc)
    only_sponsor = PilotKeyRegistry.from_mapping([{
        "key_id": "sponsor-k1", "role": ROLE_SPONSOR, "status": "ACTIVE",
        "not_before": (now - timedelta(days=1)).isoformat(), "not_after": (now + timedelta(days=1)).isoformat(),
    }])
    assert not verify_dual_control(p, pair, provider=provider, registry=only_sponsor)
    assert not keys_currently_usable(pair, registry(), now + timedelta(days=60))


def test_rotation_new_key_version_works(provider):
    p = profile()
    now = datetime.now(timezone.utc)
    rotated = PilotKeyRegistry.from_mapping([
        {"key_id": "sponsor-k1", "role": ROLE_SPONSOR, "status": "RETIRED",
         "not_before": (now - timedelta(days=9)).isoformat(), "not_after": (now + timedelta(days=9)).isoformat()},
        {"key_id": "sponsor-k2", "role": ROLE_SPONSOR, "status": "ACTIVE",
         "not_before": (now - timedelta(days=1)).isoformat(), "not_after": (now + timedelta(days=9)).isoformat()},
        {"key_id": "release-k1", "role": ROLE_RELEASE_SECURITY, "status": "ACTIVE",
         "not_before": (now - timedelta(days=1)).isoformat(), "not_after": (now + timedelta(days=9)).isoformat()},
    ])
    _, release = approvals(p, provider)
    old = sign_pilot_approval(p, role=ROLE_SPONSOR, approver_id=SPONSOR, key_id="sponsor-k1", provider=provider)
    new = sign_pilot_approval(p, role=ROLE_SPONSOR, approver_id=SPONSOR, key_id="sponsor-k2", provider=provider)
    assert not verify_dual_control(p, (old, release), provider=provider, registry=rotated)
    assert verify_dual_control(p, (new, release), provider=provider, registry=rotated)


def test_registry_rejects_unknown_fields_or_material():
    now = datetime.now(timezone.utc).isoformat()
    with pytest.raises(PilotConfigurationError):
        PilotKeyRegistry.from_mapping([{"key_id": "k", "role": ROLE_SPONSOR, "status": "ACTIVE",
                                        "not_before": now, "not_after": now, "secret": "x"}])


@pytest.mark.parametrize("field,value", [
    ("max_aggregate_exposure", "19.00"), ("account_id", "acct-b"), ("broker_id", "broker-b"),
    ("instrument", "XYZ"), ("asset_class", "ETF"), ("release_sha", "b" * 40),
    ("session_id", "other-session"),
])
def test_approval_bound_to_exact_profile(provider, field, value):
    p = profile()
    pair = approvals(p, provider)
    other = profile(**{field: value})
    assert not verify_dual_control(other, pair, provider=provider, registry=registry())


def test_tampered_signature_or_profile_rejected(provider):
    p = profile()
    sponsor, release = approvals(p, provider)
    forged = dataclasses.replace(sponsor, signature="0" * 64)
    assert not verify_dual_control(p, (forged, release), provider=provider, registry=registry())
    object.__setattr__(p, "account_id", "acct-z")
    assert not verify_dual_control(p, (sponsor, release), provider=provider, registry=registry())


def test_release_sha_must_be_exact_commit():
    for bad in ("main", "abc123", "A" * 40, "g" * 40):
        with pytest.raises(PilotConfigurationError):
            profile(release_sha=bad)


def test_provider_failures_fail_closed():
    p = profile()
    good = EphemeralTestSecretProvider()
    pair = approvals(p, good)

    class Broken:
        def get_key(self, key_id):
            raise RuntimeError("secret store unavailable")

    class Weak:
        def get_key(self, key_id):
            return b"short"

    for bad in (Broken(), Weak(), None):
        assert not verify_dual_control(p, pair, provider=bad, registry=registry())
    assert not verify_dual_control(p, pair, provider=good, registry={"sponsor-k1": "ACTIVE"})
    assert mapping()["sponsor_id"] == SPONSOR
