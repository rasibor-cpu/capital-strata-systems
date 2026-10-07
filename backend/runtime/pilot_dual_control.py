"""Dual-control approval for a governed pilot profile. No execution side effects.

Owner decisions (2026-10-07):
- two independently attributable approvals are required:
  ``PILOT_SPONSOR`` (Business Owner / Pilot Sponsor) and
  ``RELEASE_SECURITY_APPROVER`` (a different human with a different key);
- secrets come only from the approved Windows-native external secret interface
  (Windows Credential Manager / DPAPI, ``backend/security/windows_credential_provider.py``).

Signatures are Ed25519. Each approver's *private* signing key lives only in that
approver's own Credential Manager (DPAPI-protected, per user). The runtime and
this repository hold only verification metadata: key id, role, holder, status,
validity window and the *public* key. The verifier therefore cannot forge an
approval, and neither approver can sign for the other.

- RETIRED / REVOKED / unknown / out-of-window / wrong-role / wrong-holder keys fail closed;
- each approval signs the exact profile digest (account, broker, instrument,
  asset class, ceiling, currency, validity window, session, release SHA);
- replay is prevented by the one-time ledger;
- production activation additionally requires ``production_enrollment_status``
  to report ready (both roles designated to distinct humans and enrolled).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

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
SEED_BYTES = 32
_PUBLIC_KEY_HEX = re.compile(r"^[0-9a-f]{64}$")
_SIGNATURE_HEX = re.compile(r"^[0-9a-f]{128}$")
ENROLLMENT_SCHEMA = "css.pilot_approver_enrollment.v1"
DEFAULT_ENROLLMENT_PATH = Path(__file__).resolve().parents[2] / "config" / "governance" / "pilot_approver_enrollment.json"


class PilotSigningKeyProvider(Protocol):
    """Approved external secret interface, used only on the approver's own machine/profile."""

    def get_signing_seed(self, key_id: str) -> bytes:  # pragma: no cover - protocol
        ...


@dataclass(frozen=True)
class PilotKeyRecord:
    key_id: str
    role: str
    holder_id: str
    status: str
    not_before: datetime
    not_after: datetime
    public_key_hex: str

    def public_key(self) -> Ed25519PublicKey:
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.public_key_hex))


class PilotKeyRegistry:
    """Verification metadata only (never private material). Rotation = multiple versions per role."""

    FIELDS = frozenset({"key_id", "role", "holder_id", "status", "not_before", "not_after", "public_key_hex"})

    def __init__(self, records: Iterable[PilotKeyRecord]) -> None:
        self._records: dict[str, PilotKeyRecord] = {}
        owners: dict[str, tuple[str, str]] = {}
        for record in records:
            if type(record) is not PilotKeyRecord or record.key_id in self._records:
                raise PilotConfigurationError("invalid or duplicate key record")
            owner = (record.role, record.holder_id)
            if owners.setdefault(record.public_key_hex, owner) != owner:
                raise PilotConfigurationError("one public key registered to two roles or holders")
            record.public_key()  # must parse
            self._records[record.key_id] = record

    @classmethod
    def from_mapping(cls, entries: Iterable[Mapping[str, Any]]) -> "PilotKeyRegistry":
        records = []
        for entry in entries:
            if not isinstance(entry, Mapping) or set(entry) != cls.FIELDS:
                raise PilotConfigurationError("key record must have exactly the approved metadata fields")
            role = str(entry["role"]).strip()
            status = str(entry["status"]).strip().upper()
            public_key_hex = str(entry["public_key_hex"]).strip()
            if role not in REQUIRED_ROLES or status not in KEY_STATUSES:
                raise PilotConfigurationError("unknown key role or status")
            if not _PUBLIC_KEY_HEX.fullmatch(public_key_hex):
                raise PilotConfigurationError("public_key_hex must be a 32-byte lowercase hex Ed25519 key")
            not_before = _timestamp(entry["not_before"], "not_before")
            not_after = _timestamp(entry["not_after"], "not_after")
            if not not_before < not_after:
                raise PilotConfigurationError("key validity window invalid")
            records.append(PilotKeyRecord(
                _identifier(entry["key_id"], "key_id"), role, _identifier(entry["holder_id"], "holder_id"),
                status, not_before, not_after, public_key_hex))
        return cls(records)

    def record(self, key_id: str) -> PilotKeyRecord | None:
        return self._records.get(key_id)

    def records(self) -> tuple[PilotKeyRecord, ...]:
        return tuple(self._records.values())

    def usable(self, key_id: str, role: str, holder_id: str, at: datetime) -> bool:
        record = self._records.get(key_id)
        return (record is not None and record.role == role and record.holder_id == holder_id
                and record.status == KEY_STATUS_ACTIVE and record.not_before <= at < record.not_after)


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

    def to_dict(self) -> dict[str, str]:
        return {**self.evidence(), "signature": self.signature}

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "PilotApproval":
        allowed = {"role", "approver_id", "key_id", "approved_at", "profile_digest", "signature"}
        if not isinstance(values, Mapping) or set(values) != allowed:
            raise PilotConfigurationError("approval must have exactly the approved fields")
        signature = str(values["signature"])
        if not _SIGNATURE_HEX.fullmatch(signature):
            raise PilotConfigurationError("signature must be a 64-byte hex Ed25519 signature")
        return cls(str(values["role"]), _identifier(values["approver_id"], "approver_id"),
                   _identifier(values["key_id"], "key_id"), _timestamp(values["approved_at"], "approved_at"),
                   str(values["profile_digest"]), signature)


def _approval_message(role: str, approver_id: str, key_id: str, approved_at: datetime, digest: str) -> bytes:
    return "|".join(("css.pilot_approval.v1", role, approver_id, key_id,
                     approved_at.astimezone(timezone.utc).isoformat(), digest)).encode("utf-8")


def _expected_approver(profile: GovernedPilotProfile, role: str) -> str:
    return profile.sponsor_id if role == ROLE_SPONSOR else profile.release_approver_id


def public_key_hex_from_seed(seed: bytes) -> str:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    key = Ed25519PrivateKey.from_private_bytes(bytes(seed))
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def sign_pilot_approval(
    profile: GovernedPilotProfile,
    *,
    role: str,
    approver_id: str,
    key_id: str,
    provider: PilotSigningKeyProvider,
    approved_at: datetime | None = None,
) -> PilotApproval:
    """Runs on the approver's own Windows profile, where their key is held. Never in the agent."""
    if type(profile) is not GovernedPilotProfile or role not in REQUIRED_ROLES:
        raise PilotConfigurationError("approved profile and known role required")
    if approver_id != _expected_approver(profile, role):
        raise PilotConfigurationError("approver is not the designated holder of this role")
    seed = provider.get_signing_seed(key_id)
    if not isinstance(seed, (bytes, bytearray)) or len(seed) != SEED_BYTES:
        raise PilotConfigurationError("secret provider returned unusable signing key")
    approved_at = _timestamp(approved_at or datetime.now(timezone.utc), "approved_at")
    digest = profile.digest()
    signature = Ed25519PrivateKey.from_private_bytes(bytes(seed)).sign(
        _approval_message(role, approver_id, key_id, approved_at, digest)).hex()
    return PilotApproval(role, approver_id, key_id, approved_at, digest, signature)


def verify_dual_control(profile: Any, approvals: Any, *, registry: Any) -> bool:
    """True only if exactly one valid approval per required role, by distinct humans/keys. Never raises."""
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
        public_keys = set()
        for approval in approvals:
            if approval.profile_digest != digest:
                return False
            if approval.approver_id != _expected_approver(profile, approval.role):
                return False
            if not isinstance(approval.approved_at, datetime) or approval.approved_at.tzinfo is None:
                return False
            if not profile.issued_at <= approval.approved_at < profile.expires_at:
                return False
            if not registry.usable(approval.key_id, approval.role, approval.approver_id, approval.approved_at):
                return False
            record = registry.record(approval.key_id)
            public_keys.add(record.public_key_hex)
            if not isinstance(approval.signature, str) or not _SIGNATURE_HEX.fullmatch(approval.signature):
                return False
            record.public_key().verify(
                bytes.fromhex(approval.signature),
                _approval_message(approval.role, approval.approver_id, approval.key_id, approval.approved_at, digest),
            )
        return len(public_keys) == 2
    except (InvalidSignature, Exception):
        return False


def keys_currently_usable(approvals: Iterable[PilotApproval], registry: PilotKeyRegistry, now: datetime) -> bool:
    """Revocation/retirement after signing must also block use (checked at evaluation/consumption)."""
    return all(registry.usable(a.key_id, a.role, a.approver_id, now) for a in approvals)


# ---- production enrollment gate ----------------------------------------------

def production_enrollment_status(path: str | Path = DEFAULT_ENROLLMENT_PATH, *, now: datetime | None = None) -> dict[str, Any]:
    """Production activation stays blocked until both roles are designated to distinct humans and enrolled.

    Reads the committed enrollment record (designations + public-key metadata only). Never raises.
    """
    blockers: list[str] = []
    now = now or datetime.now(timezone.utc)
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != ENROLLMENT_SCHEMA:
            raise PilotConfigurationError("unknown enrollment schema")
        if set(data) - {"schema", "designations", "keys", "notes"}:
            raise PilotConfigurationError("unapproved enrollment fields")
        designations = data.get("designations") or {}
        registry = PilotKeyRegistry.from_mapping(data.get("keys") or [])
    except Exception as exc:
        return {"ready": False, "blockers": [f"enrollment_unreadable:{type(exc).__name__}"], "designations": {}}
    holders: dict[str, str] = {}
    for role in sorted(REQUIRED_ROLES):
        entry = designations.get(role)
        holder = entry.get("holder_id") if isinstance(entry, Mapping) else None
        if not holder:
            blockers.append(f"{role.lower()}_not_designated")
            continue
        holders[role] = holder
        if not any(registry.usable(r.key_id, role, holder, now) for r in registry.records() if r.role == role):
            blockers.append(f"{role.lower()}_key_not_enrolled")
    if len(holders) == 2 and len(set(holders.values())) != 2:
        blockers.append("roles_not_held_by_distinct_humans")
    return {"ready": not blockers, "blockers": blockers, "designations": holders}
