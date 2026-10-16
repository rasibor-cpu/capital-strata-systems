"""Persistent per-user trading state: the ACTIVE accepted settings and the pause flag.

Settings never become active by selection alone. `activate()` is called only by the
consent transaction (consent.py) after the user accepted the CSS User Operating
Manual for the exact settings; the active record carries the policy hash and the
hash of the acceptance record it was activated under. The store fails closed: an
unreadable, tampered or schema-mismatched file raises instead of falling back.

Migration: v1 files (three-mode selection plus a short disclosure acknowledgement)
are read as a *previous selection* only. Migrated users have no active settings
until they accept the current agreement for the four-mode contract.

Pausing is a risk-reducing action and never requires consent.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.certification.ov002_persistence import PersistenceError, atomic_write_json, read_json_object
from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.trading_profiles.limits import LimitsError, UserRiskLimits
from backend.trading_profiles.operating_modes import OperatingMode
from backend.trading_profiles.risk_personalities import RiskPersonality

PREFERENCES_SCHEMA = "css.trading_profiles.preferences.v2"
LEGACY_SCHEMA_V1 = "css.trading_profiles.preferences.v1"


class PreferencesError(RuntimeError):
    """Fail-closed error for the preferences store."""


@dataclass(frozen=True)
class ActiveSettings:
    operating_mode: OperatingMode
    risk_personality: RiskPersonality | None
    limits: UserRiskLimits
    mandate_id: str | None
    policy_hash: str
    consent_record_hash: str
    activated_at_utc: str

    def to_record(self) -> dict[str, Any]:
        return {
            "operating_mode": self.operating_mode.value,
            "risk_personality": self.risk_personality.value if self.risk_personality else None,
            "limits": self.limits.to_dict(),
            "mandate_id": self.mandate_id,
            "policy_hash": self.policy_hash,
            "consent_record_hash": self.consent_record_hash,
            "activated_at_utc": self.activated_at_utc,
        }

    @classmethod
    def from_record(cls, record: Any) -> "ActiveSettings":
        expected = {"operating_mode", "risk_personality", "limits", "mandate_id", "policy_hash",
                    "consent_record_hash", "activated_at_utc"}
        if not isinstance(record, dict) or set(record) != expected:
            raise PreferencesError("active settings record malformed")
        try:
            return cls(
                operating_mode=OperatingMode.parse(record["operating_mode"]),
                risk_personality=RiskPersonality.parse(record["risk_personality"]) if record["risk_personality"] else None,
                limits=UserRiskLimits.from_mapping(record["limits"]),
                mandate_id=record["mandate_id"],
                policy_hash=str(record["policy_hash"]),
                consent_record_hash=str(record["consent_record_hash"]),
                activated_at_utc=str(record["activated_at_utc"]),
            )
        except (ValueError, LimitsError) as exc:
            raise PreferencesError(f"active settings invalid: {exc}") from exc


@dataclass(frozen=True)
class UserTradingState:
    user_id: str
    active: ActiveSettings | None = None
    paused: bool = False
    paused_at_utc: str | None = None
    previous_selection: dict | None = None  # migrated v1 choice, display only

    def to_record(self) -> dict[str, Any]:
        return {"user_id": self.user_id, "active": self.active.to_record() if self.active else None,
                "paused": self.paused, "paused_at_utc": self.paused_at_utc,
                "previous_selection": self.previous_selection}

    @classmethod
    def from_record(cls, record: Any) -> "UserTradingState":
        expected = {"user_id", "active", "paused", "paused_at_utc", "previous_selection"}
        if not isinstance(record, dict) or set(record) != expected:
            raise PreferencesError("preference record has unexpected or missing fields")
        if not isinstance(record["user_id"], str) or not record["user_id"].strip():
            raise PreferencesError("preference record user_id invalid")
        if not isinstance(record["paused"], bool):
            raise PreferencesError("paused flag invalid")
        active = ActiveSettings.from_record(record["active"]) if record["active"] is not None else None
        return cls(record["user_id"], active, record["paused"], record["paused_at_utc"], record["previous_selection"])


def _now_iso(now: datetime | None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _migrate_v1(users: dict[str, Any]) -> dict[str, Any]:
    migrated = {}
    for user_id, record in users.items():
        if not isinstance(record, dict):
            raise PreferencesError("v1 preference record malformed")
        selection = {"operating_mode": record.get("operating_mode"), "risk_personality": record.get("risk_personality"),
                     "source": LEGACY_SCHEMA_V1}
        migrated[user_id] = UserTradingState(user_id, previous_selection=selection).to_record()
    return migrated


class PreferencesStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.path = self.root / "trading_profile_preferences.json"
        self.lock_path = self.root / "trading_profile_preferences.lock"

    def _read_all(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            document = read_json_object(self.path)
        except PersistenceError as exc:
            raise PreferencesError(f"preferences unreadable: {exc}") from exc
        if not isinstance(document.get("users"), dict):
            raise PreferencesError("preferences schema mismatch")
        if document.get("schema") == LEGACY_SCHEMA_V1:
            return _migrate_v1(document["users"])
        if document.get("schema") != PREFERENCES_SCHEMA:
            raise PreferencesError("preferences schema mismatch")
        return document["users"]

    def get(self, user_id: str) -> UserTradingState:
        record = self._read_all().get(user_id)
        if record is None:
            return UserTradingState(user_id=user_id)
        state = UserTradingState.from_record(record)
        if state.user_id != user_id:
            raise PreferencesError("preference record user mismatch")
        return state

    def user_ids(self) -> list[str]:
        return sorted(self._read_all())

    def _update(self, user_id: str, change) -> UserTradingState:
        """Read-modify-write of one user's state under the store lock."""
        if not isinstance(user_id, str) or not user_id.strip():
            raise PreferencesError("user_id required")
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            users = self._read_all()
            current = UserTradingState.from_record(users[user_id]) if user_id in users else UserTradingState(user_id)
            updated = change(current)
            users[user_id] = updated.to_record()
            atomic_write_json(self.path, {"schema": PREFERENCES_SCHEMA, "users": users}, expected_root=self.root)
        return updated

    def activate(self, user_id: str, active: ActiveSettings) -> UserTradingState:
        """Only the consent transaction may call this."""
        return self._update(user_id, lambda c: UserTradingState(user_id, active, c.paused, c.paused_at_utc, None))

    def pause(self, user_id: str, *, now: datetime | None = None) -> UserTradingState:
        """Risk-reducing: blocks new trades immediately. Never requires consent."""
        return self._update(user_id, lambda c: UserTradingState(user_id, c.active, True, _now_iso(now), c.previous_selection))

    def unpause(self, user_id: str) -> UserTradingState:
        """Caller must verify valid consent first (resuming re-enables risk-taking)."""
        return self._update(user_id, lambda c: UserTradingState(user_id, c.active, False, None, c.previous_selection))


def default_store_root() -> Path:
    """Artifacts location; overridable for tests and isolated runs."""
    return Path(os.environ.get("CSS_TRADING_PROFILES_DIR") or "artifacts/trading_profiles")
