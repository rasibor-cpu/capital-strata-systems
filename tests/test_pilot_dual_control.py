import dataclasses
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.runtime.governed_pilot_profile import PilotConfigurationError
from backend.runtime.pilot_dual_control import (
    DEFAULT_ENROLLMENT_PATH, ROLE_RELEASE_SECURITY, ROLE_SPONSOR, PilotApproval, PilotKeyRegistry,
    keys_currently_usable, production_enrollment_status, sign_pilot_approval, verify_dual_control,
)
from backend.security.windows_credential_provider import (
    TARGET_PREFIX, PilotSecretUnavailable, WindowsCredentialSigningKeyProvider,
)
from pilot_dual_control_fixtures import (
    RELEASE_APPROVER, SPONSOR, EphemeralTestSecretProvider, approvals, profile, registry, registry_entries,
)


@pytest.fixture
def provider():
    return EphemeralTestSecretProvider()


def test_both_roles_required(provider):
    p = profile()
    sponsor, release = approvals(p, provider)
    reg = registry(provider)
    assert verify_dual_control(p, (sponsor, release), registry=reg)
    assert not verify_dual_control(p, (sponsor,), registry=reg)
    assert not verify_dual_control(p, (sponsor, sponsor), registry=reg)
    assert not verify_dual_control(p, (sponsor, release, release), registry=reg)


def test_verifier_holds_no_secret_and_cannot_forge(provider):
    """Asymmetric: the registry has only public keys; a different seed cannot produce a valid approval."""
    p = profile()
    _, release = approvals(p, provider)
    forger = EphemeralTestSecretProvider()  # attacker has their own keys, not the sponsor's
    forged = sign_pilot_approval(p, role=ROLE_SPONSOR, approver_id=SPONSOR, key_id="sponsor-k1", provider=forger)
    assert not verify_dual_control(p, (forged, release), registry=registry(provider))
    for entry in registry_entries(provider):
        assert set(entry) == PilotKeyRegistry.FIELDS  # metadata + public key only


def test_approvals_are_independently_attributable(provider):
    evidence = [a.evidence() for a in approvals(profile(), provider)]
    assert {e["role"] for e in evidence} == {ROLE_SPONSOR, ROLE_RELEASE_SECURITY}
    assert {e["approver_id"] for e in evidence} == {SPONSOR, RELEASE_APPROVER}
    assert {e["key_id"] for e in evidence} == {"sponsor-k1", "release-k1"}


def test_key_material_never_in_evidence_or_repr(provider):
    for approval in approvals(profile(), provider):
        rendered = repr(approval) + json.dumps(approval.to_dict()) + repr(provider)
        for key_id in ("sponsor-k1", "release-k1"):
            assert provider.get_signing_seed(key_id).hex() not in rendered


def test_approval_round_trips_through_json(provider):
    p = profile()
    pair = tuple(PilotApproval.from_mapping(json.loads(json.dumps(a.to_dict()))) for a in approvals(p, provider))
    assert verify_dual_control(p, pair, registry=registry(provider))
    with pytest.raises(PilotConfigurationError):
        PilotApproval.from_mapping({**pair[0].to_dict(), "seed": "00"})


def test_same_person_cannot_hold_both_roles():
    with pytest.raises(PilotConfigurationError):
        profile(release_approver_id=SPONSOR)


def test_approver_must_be_designated_role_holder(provider):
    with pytest.raises(PilotConfigurationError):
        sign_pilot_approval(profile(), role=ROLE_SPONSOR, approver_id="someone-else",
                            key_id="sponsor-k1", provider=provider)


def test_key_bound_to_role_and_holder(provider):
    p = profile()
    _, release = approvals(p, provider)
    swapped = sign_pilot_approval(p, role=ROLE_SPONSOR, approver_id=SPONSOR, key_id="release-k1", provider=provider)
    assert not verify_dual_control(p, (swapped, release), registry=registry(provider))


def test_one_public_key_cannot_serve_two_humans(provider):
    entries = registry_entries(provider)
    entries[1]["public_key_hex"] = entries[0]["public_key_hex"]
    with pytest.raises(PilotConfigurationError):
        PilotKeyRegistry.from_mapping(entries)


@pytest.mark.parametrize("status", ["RETIRED", "REVOKED"])
def test_retired_or_revoked_keys_fail_closed(provider, status):
    p = profile()
    pair = approvals(p, provider)
    assert not verify_dual_control(p, pair, registry=registry(provider, **{"release-k1": status}))
    assert not keys_currently_usable(pair, registry(provider, **{"sponsor-k1": status}), datetime.now(timezone.utc))


def test_unknown_key_and_out_of_window_fail_closed(provider):
    p = profile()
    pair = approvals(p, provider)
    only_sponsor = PilotKeyRegistry.from_mapping(registry_entries(provider)[:1])
    assert not verify_dual_control(p, pair, registry=only_sponsor)
    assert not keys_currently_usable(pair, registry(provider), datetime.now(timezone.utc) + timedelta(days=60))


def test_rotation_new_key_version_works(provider):
    p = profile()
    now = datetime.now(timezone.utc)
    entries = registry_entries(provider, **{"sponsor-k1": "RETIRED"})
    entries.append({"key_id": "sponsor-k2", "role": ROLE_SPONSOR, "holder_id": SPONSOR, "status": "ACTIVE",
                    "not_before": (now - timedelta(days=1)).isoformat(),
                    "not_after": (now + timedelta(days=9)).isoformat(),
                    "public_key_hex": provider.public_key_hex("sponsor-k2")})
    rotated = PilotKeyRegistry.from_mapping(entries)
    _, release = approvals(p, provider)
    old = sign_pilot_approval(p, role=ROLE_SPONSOR, approver_id=SPONSOR, key_id="sponsor-k1", provider=provider)
    new = sign_pilot_approval(p, role=ROLE_SPONSOR, approver_id=SPONSOR, key_id="sponsor-k2", provider=provider)
    assert not verify_dual_control(p, (old, release), registry=rotated)
    assert verify_dual_control(p, (new, release), registry=rotated)


def test_registry_rejects_unknown_fields_or_private_material(provider):
    entry = registry_entries(provider)[0]
    with pytest.raises(PilotConfigurationError):
        PilotKeyRegistry.from_mapping([{**entry, "private_seed_hex": "00" * 32}])
    with pytest.raises(PilotConfigurationError):
        PilotKeyRegistry.from_mapping([{**entry, "public_key_hex": "zz"}])


@pytest.mark.parametrize("field,value", [
    ("max_aggregate_exposure", "19.00"), ("account_id", "acct-b"), ("broker_id", "broker-b"),
    ("instrument", "XYZ"), ("asset_class", "ETF"), ("release_sha", "b" * 40),
    ("session_id", "other-session"),
])
def test_approval_bound_to_exact_profile(provider, field, value):
    pair = approvals(profile(), provider)
    assert not verify_dual_control(profile(**{field: value}), pair, registry=registry(provider))


def test_tampered_signature_or_profile_rejected(provider):
    p = profile()
    sponsor, release = approvals(p, provider)
    forged = dataclasses.replace(sponsor, signature="0" * 128)
    assert not verify_dual_control(p, (forged, release), registry=registry(provider))
    object.__setattr__(p, "account_id", "acct-z")
    assert not verify_dual_control(p, (sponsor, release), registry=registry(provider))


def test_release_sha_must_be_exact_commit():
    for bad in ("main", "abc123", "A" * 40, "g" * 40):
        with pytest.raises(PilotConfigurationError):
            profile(release_sha=bad)


def test_bad_provider_fails_to_sign():
    class Weak:
        def get_signing_seed(self, key_id):
            return b"short"
    with pytest.raises(PilotConfigurationError):
        sign_pilot_approval(profile(), role=ROLE_SPONSOR, approver_id=SPONSOR, key_id="sponsor-k1", provider=Weak())


# ---- Windows Credential Manager provider --------------------------------------

class FakeCredentialStore:
    def __init__(self):
        self.store = {}

    def read(self, target):
        return self.store.get(target)

    def write_new(self, target, blob, comment):
        if target in self.store:
            raise PilotSecretUnavailable("PILOT_KEY_ALREADY_ENROLLED")
        self.store[target] = bytes(blob)


def test_windows_provider_enroll_returns_public_key_only_and_signs():
    store = FakeCredentialStore()
    win = WindowsCredentialSigningKeyProvider(backend=store)
    public_hex = win.enroll("sponsor-k1")
    seed = store.store[TARGET_PREFIX + "sponsor-k1"]
    assert len(seed) == 32 and seed.hex() not in public_hex and len(public_hex) == 64
    assert seed.hex() not in repr(win)
    with pytest.raises(PilotSecretUnavailable):
        win.enroll("sponsor-k1")  # never overwrites; rotation uses a new key id
    assert win.get_signing_seed("sponsor-k1") == seed


@pytest.mark.parametrize("blob,code", [(None, "PILOT_KEY_NOT_ENROLLED"), (b"x" * 31, "PILOT_KEY_MALFORMED")])
def test_windows_provider_missing_or_malformed_fails_closed(blob, code):
    store = FakeCredentialStore()
    if blob is not None:
        store.store[TARGET_PREFIX + "k"] = blob
    with pytest.raises(PilotSecretUnavailable) as exc:
        WindowsCredentialSigningKeyProvider(backend=store).get_signing_seed("k")
    assert exc.value.code == code


def test_windows_provider_rejects_bad_key_id():
    with pytest.raises(PilotSecretUnavailable):
        WindowsCredentialSigningKeyProvider(backend=FakeCredentialStore()).get_signing_seed("../x y")


@pytest.mark.skipif(sys.platform == "win32", reason="checks the non-Windows fail-closed path")
def test_windows_provider_fails_closed_off_windows():
    with pytest.raises(PilotSecretUnavailable) as exc:
        WindowsCredentialSigningKeyProvider()
    assert exc.value.code == "WINDOWS_CREDENTIAL_MANAGER_REQUIRED"


# ---- production enrollment gate ----------------------------------------------

def test_committed_enrollment_blocks_production_activation():
    status = production_enrollment_status(DEFAULT_ENROLLMENT_PATH)
    assert status["ready"] is False
    assert status["designations"] == {ROLE_SPONSOR: "robert-asibor"}
    assert set(status["blockers"]) == {"pilot_sponsor_key_not_enrolled", "release_security_approver_not_designated"}
    raw = Path(DEFAULT_ENROLLMENT_PATH).read_text()
    assert "seed" not in raw.lower() and "private" not in json.loads(raw)["keys"].__repr__().lower()


def _enrollment(tmp_path, provider, release_holder, entries):
    data = {"schema": "css.pilot_approver_enrollment.v1",
            "designations": {ROLE_SPONSOR: {"holder_id": SPONSOR},
                             ROLE_RELEASE_SECURITY: {"holder_id": release_holder} if release_holder else None},
            "keys": entries}
    path = tmp_path / "enrollment.json"
    path.write_text(json.dumps(data))
    return path


def test_enrollment_ready_only_with_distinct_designated_enrolled_humans(tmp_path, provider):
    ready = production_enrollment_status(_enrollment(tmp_path, provider, RELEASE_APPROVER, registry_entries(provider)))
    assert ready["ready"] is True
    same = production_enrollment_status(_enrollment(tmp_path, provider, SPONSOR, registry_entries(provider)))
    assert not same["ready"]
    revoked = production_enrollment_status(
        _enrollment(tmp_path, provider, RELEASE_APPROVER, registry_entries(provider, **{"release-k1": "REVOKED"})))
    assert "release_security_approver_key_not_enrolled" in revoked["blockers"]


def test_enrollment_unreadable_or_extra_fields_fail_closed(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "css.pilot_approver_enrollment.v1", "designations": {}, "keys": [],
                               "private_keys": ["00"]}))
    assert production_enrollment_status(bad)["ready"] is False
    assert production_enrollment_status(tmp_path / "missing.json")["ready"] is False
