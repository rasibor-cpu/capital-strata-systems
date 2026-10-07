"""Test-only fixtures for governed pilot dual control.

Signing seeds here are ephemeral random bytes generated per test run. They are
not, and must never be used as, production pilot keys; production signing keys
live only in each approver's own Windows Credential Manager (DPAPI).
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from backend.runtime.governed_pilot_profile import GovernedPilotProfile
from backend.runtime.pilot_dual_control import (
    ROLE_RELEASE_SECURITY, ROLE_SPONSOR, PilotKeyRegistry, public_key_hex_from_seed, sign_pilot_approval,
)

RELEASE_SHA = "a" * 40
SPONSOR = "robert-asibor"
RELEASE_APPROVER = "test-release-approver"  # test-only placeholder; production approver is NOT designated
SESSION = "unique-process-session"
KEY_ROLES = {"sponsor-k1": (ROLE_SPONSOR, SPONSOR), "sponsor-k2": (ROLE_SPONSOR, SPONSOR),
             "release-k1": (ROLE_RELEASE_SECURITY, RELEASE_APPROVER)}


class EphemeralTestSecretProvider:
    """In-memory stand-in for the Windows Credential Manager provider (tests only)."""

    def __init__(self, key_ids=("sponsor-k1", "release-k1", "sponsor-k2")):
        self._seeds = {key_id: secrets.token_bytes(32) for key_id in key_ids}

    def get_signing_seed(self, key_id):
        return self._seeds[key_id]

    def public_key_hex(self, key_id):
        return public_key_hex_from_seed(self._seeds[key_id])

    def __repr__(self):
        return f"EphemeralTestSecretProvider(key_ids={sorted(self._seeds)})"


def registry_entries(provider, **status_overrides):
    now = datetime.now(timezone.utc)
    entries = []
    for key_id in ("sponsor-k1", "release-k1"):
        role, holder = KEY_ROLES[key_id]
        entries.append({
            "key_id": key_id, "role": role, "holder_id": holder,
            "status": status_overrides.get(key_id, "ACTIVE"),
            "not_before": (now - timedelta(days=1)).isoformat(),
            "not_after": (now + timedelta(days=30)).isoformat(),
            "public_key_hex": provider.public_key_hex(key_id),
        })
    return entries


def registry(provider, **status_overrides):
    return PilotKeyRegistry.from_mapping(registry_entries(provider, **status_overrides))


def mapping(**overrides):
    now = datetime.now(timezone.utc)
    data = {
        "approval_id": "change-001", "sponsor_id": SPONSOR,
        "release_approver_id": RELEASE_APPROVER, "release_sha": RELEASE_SHA,
        "scope": "PILOT_PREFLIGHT_ONE_ORDER", "broker_id": "broker-a",
        "account_id": "acct-a", "asset_class": "EQUITY", "instrument": "ABC",
        "currency": "CAD", "max_aggregate_exposure": "20.00",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "session_id": SESSION,
    }
    data.update(overrides)
    return data


def profile(limit="20.00", **overrides):
    overrides.setdefault("max_aggregate_exposure", limit)
    return GovernedPilotProfile.from_mapping(mapping(**overrides))


def approvals(p, provider):
    return (
        sign_pilot_approval(p, role=ROLE_SPONSOR, approver_id=SPONSOR, key_id="sponsor-k1", provider=provider),
        sign_pilot_approval(p, role=ROLE_RELEASE_SECURITY, approver_id=RELEASE_APPROVER,
                            key_id="release-k1", provider=provider),
    )
