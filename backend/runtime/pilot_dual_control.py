"""Dual-control approval for a governed pilot profile. No execution side effects.

Owner decision (2026-10-07): a pilot authorization requires two independently
attributable approvals before it can become executable:

- ``PILOT_SPONSOR``              -- Business Owner / Pilot Sponsor
- ``RELEASE_SECURITY_APPROVER``  -- independent release/security role

Key custody:
- key material is owner-controlled and is obtained only through a
  ``PilotSecretProvider`` (the approved external secret interface). This module
  holds no key, generates no key, and never logs or serialises key material;
- evidence carries the key *identifier/version* only;
- the key registry (metadata only: key_id, role, status, validity) supports
  rotation; RETIRED / REVOKED / out-of-window / unknown keys fail closed;
- each role must sign with a key registered to that role, and the two approvals
  must use distinct approvers and distinct keys;
- each approval is an HMAC-SHA256 over the exact profile digest, which binds
  account, broker, instrument, asset class, ceiling, currency, validity window,
  session and release/candidate SHA. Replay is prevented by the one-time ledger.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Protocol

from backend.runtime.governed_pilot_profile import (
    GovernedPilotProfile,
    PilotConfigurationError,
    _identifier,
    _timestamp,
)


ROLE_SPONSOR = "PILOT_SPONSOR"
ROLE_RELEASE_SECURITY = "RELEASE_SECURITY_APPROVER"
REQUIRED_ROLES = frozenset({ROLE_SPONSOR, ROLE_RELEASE_SECURITY})
KEY_STATUS_ACTIVE = "ACTIVE"
KEY_STATUSES = frozenset({KEY_STATUS_ACTIVE, "RETIRED", "REVOKED"})
MIN_KEY_BYTES = 32


class PilotSecretProvider(Protocol):
    """Approved external secret interface. Implementations live outside this repo's custody."""

    def get_key(self, key_id: str) -> bytes:  # pragma: no cover - protocol
        ...


@dataclass(frozen=True)
class PilotKeyRecord:
    key_id: str
    role: str
    status: str
    not_before: datetime
    not_after: datetime


class PilotKeyRegistry:
    """Key metadata only (never material). Supports rotation via multiple versions per role."""

    def __init__(self, records: Iterable[PilotKeyRecord]) -> None:
        self._records: dict[str, PilotKeyRecord] = {}
        for record in records:
            if type(record) is not PilotKeyRecord or record.key_id in self._records:
                raise PilotConfigurationError("invalid or duplicate key record")
            self._records[record.key_id] = record

    @classmethod
    def from_mapping(cls, entries: Iterable[Mapping[str, Any]]) -> "PilotKeyRegistry":
        allowed = {"key_id", "role", "status", "not_before", "not_after"}
        records = []
        for entry in entries:
            if not isinstance(entry, Mapping) or set(entry) != allowed:
                raise PilotConfigurationError("key record must have exactly the approved fields")
            role = str(entry["role"]).strip()
            status = str(entry["status"]).strip().upper()
            if role not in REQUIRED_ROLES or status not in KEY_STATUSES:
                raise PilotConfigurationError("unknown key role or status")
            not_before = _timestamp(entry["not_before"], "not_before")
            not_after = _timestamp(entry["not_after"], "not_after")
            if not not_before < not_after:
                raise PilotConfigurationError("key validity window invalid")
            records.append(PilotKeyRecord(_identifier(entry["key_id"], "key_id"), role, status, not_before, not_after))
        return cls(records)

    def usable(self, key_id: str, role: str, at: datetime) -> bool:
        record = self._records.get(key_id)
        return (record is not None and record.role == role and record.status == KEY_STATUS_ACTIVE
                and record.not_before <= at < record.not_after)


@dataclass(frozen=True)
class PilotApproval:
    role: str
    approver_id: str
    key_id: str
    approved_at: datetime
    profile_digest: str
    signature: str

    def evidence(self) -> dict[str, str]:
        """Attributable, key-material-free evidence record."""
        return {
            "role": self.role, "approver_id": self.approver_id, "key_id": self.key_id,
            "approved_at": self.approved_at.astimezone(timezone.utc).isoformat(),
            "profile_digest": self.profile_digest,
        }


def _approval_message(role: str, approver_id: str, key_id: str, approved_at: datetime, digest: str) -> bytes:
    return "|".join((role, approver_id, key_id, approved_at.astimezone(timezone.utc).isoformat(), digest)).encode("utf-8")


def _fetch_key(provider: Any, key_id: str) -> bytes:
    key = provider.get_key(key_id)
    if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES:
        raise PilotConfigurationError("secret provider returned unusable key")
    return bytes(key)


def _expected_approver(profile: GovernedPilotProfile, role: str) -> str:
    return profile.sponsor_id if role == ROLE_SPONSOR else profile.release_approver_id


def sign_pilot_approval(
    profile: GovernedPilotProfile,
    *,
    role: str,
    approver_id: str,
    key_id: str,
    provider: PilotSecretProvider,
    approved_at: datetime | None = None,
) -> PilotApproval:
    """Approval-side signing; runs where the approver's key is available, never in the agent."""
    if type(profile) is not GovernedPilotProfile or role not in REQUIRED_ROLES:
        raise PilotConfigurationError("approved profile and known role required")
    if approver_id != _expected_approver(profile, role):
        raise PilotConfigurationError("approver is not the designated holder of this role")
    approved_at = _timestamp(approved_at or datetime.now(timezone.utc), "approved_at")
    digest = profile.digest()
    signature = hmac.new(_fetch_key(provider, key_id),
                         _approval_message(role, approver_id, key_id, approved_at, digest),
                         hashlib.sha256).hexdigest()
    return PilotApproval(role, approver_id, key_id, approved_at, digest, signature)


def verify_dual_control(
    profile: Any,
    approvals: Any,
    *,
    provider: Any,
    registry: Any,
) -> bool:
    """True only if exactly one valid approval per required role. Never raises."""
    try:
        if type(profile) is not GovernedPilotProfile or type(registry) is not PilotKeyRegistry:
            return False
        profile.__post_init__()  # catches object.__setattr__ tampering
        approvals = tuple(approvals)
        if len(approvals) != 2 or any(type(a) is not PilotApproval for a in approvals):
            return False
        if {a.role for a in approvals} != REQUIRED_ROLES:
            return False
        if len({a.approver_id for a in approvals}) != 2 or len({a.key_id for a in approvals}) != 2:
            return False
        digest = profile.digest()
        for approval in approvals:
            if approval.profile_digest != digest:
                return False
            if approval.approver_id != _expected_approver(profile, approval.role):
                return False
            if not isinstance(approval.approved_at, datetime) or approval.approved_at.tzinfo is None:
                return False
            if not profile.issued_at <= approval.approved_at < profile.expires_at:
                return False
            if not registry.usable(approval.key_id, approval.role, approval.approved_at):
                return False
            expected = hmac.new(_fetch_key(provider, approval.key_id),
                                _approval_message(approval.role, approval.approver_id, approval.key_id,
                                                  approval.approved_at, digest),
                                hashlib.sha256).hexdigest()
            if not isinstance(approval.signature, str) or not hmac.compare_digest(expected, approval.signature):
                return False
        return True
    except Exception:
        return False


def keys_currently_usable(approvals: Iterable[PilotApproval], registry: PilotKeyRegistry, now: datetime) -> bool:
    """Revocation/retirement after signing must also block use (checked at evaluation/consumption)."""
    return all(registry.usable(a.key_id, a.role, now) for a in approvals)
