"""Test-only fixtures for governed pilot dual control.

Keys here are ephemeral random bytes generated per test run. They are not, and
must never be used as, a production pilot key; production keys are obtained
only through the owner-controlled external secret interface.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from backend.runtime.governed_pilot_profile import GovernedPilotProfile
from backend.runtime.pilot_dual_control import (
    ROLE_RELEASE_SECURITY, ROLE_SPONSOR, PilotKeyRegistry, sign_pilot_approval,
)

RELEASE_SHA = "a" * 40
SPONSOR = "robert-asibor"
RELEASE_APPROVER = "release-security-1"
SESSION = "unique-process-session"


class EphemeralTestSecretProvider:
    """In-memory stand-in for the external secret interface (tests only)."""

    def __init__(self, key_ids=("sponsor-k1", "release-k1")):
        self._keys = {key_id: secrets.token_bytes(32) for key_id in key_ids}

    def get_key(self, key_id):
        return self._keys[key_id]

    def __repr__(self):
        return f"EphemeralTestSecretProvider(key_ids={sorted(self._keys)})"


def registry(**status_overrides):
    now = datetime.now(timezone.utc)
    entries = [
        {"key_id": "sponsor-k1", "role": ROLE_SPONSOR, "status": "ACTIVE"},
        {"key_id": "release-k1", "role": ROLE_RELEASE_SECURITY, "status": "ACTIVE"},
    ]
    for entry in entries:
        entry["status"] = status_overrides.get(entry["key_id"], entry["status"])
        entry["not_before"] = (now - timedelta(days=1)).isoformat()
        entry["not_after"] = (now + timedelta(days=30)).isoformat()
    return PilotKeyRegistry.from_mapping(entries)


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
