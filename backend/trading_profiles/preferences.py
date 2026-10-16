"""Persistent per-user trading-profile selection.

The startup operating mode and risk personality are chosen once and persisted, so
users are not asked to pick a strategy at every start. The store fails closed: an
unreadable, tampered or schema-mismatched file raises instead of falling back to a
default, and a missing selection means "nothing may trade" rather than a guessed mode.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.certification.ov002_persistence import (
    PersistenceError,
    atomic_write_json,
    read_json_object,
)
from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.trading_profiles.disclosures import DISCLOSURE_VERSION
from backend.trading_profiles.operating_modes import OperatingMode, permissions_for
from backend.trading_profiles.risk_personalities import RiskPersonality

PREFERENCES_SCHEMA = "css.trading_profiles.preferences.v1"


class PreferencesError(RuntimeError):
    """Fail-closed error for the preferences store."""


@dataclass(frozen=True)
class UserTradingPreferences:
    user_id: str
    operating_mode: OperatingMode | None = None
    risk_personality: RiskPersonality | None = None
    disclosure_version_acknowledged: str | None = None
    updated_at_utc: str | None = None

    @property
    def disclosure_current(self) -> bool:
        return self.disclosure_version_acknowledged == DISCLOSURE_VERSION

    def missing_requirements(self) -> list[str]:
        """What still has to be chosen before this user's mode may trade (paper)."""
        missing: list[str] = []
        if self.operating_mode is None:
            missing.append("operating_mode")
            return missing
        permissions = permissions_for(self.operating_mode)
        if permissions.requires_risk_personality and self.risk_personality is None:
            missing.append("risk_personality")
        if self.operating_mode is not OperatingMode.SIMULATED_TRADING and not self.disclosure_current:
            missing.append("disclosure_acknowledgement")
        return missing

    def to_record(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "operating_mode": self.operating_mode.value if self.operating_mode else None,
            "risk_personality": self.risk_personality.value if self.risk_personality else None,
            "disclosure_version_acknowledged": self.disclosure_version_acknowledged,
            "updated_at_utc": self.updated_at_utc,
        }

    @classmethod
    def from_record(cls, record: Any) -> "UserTradingPreferences":
        if not isinstance(record, dict):
            raise PreferencesError("preference record must be an object")
        expected = {"user_id", "operating_mode", "risk_personality", "disclosure_version_acknowledged", "updated_at_utc"}
        if set(record) != expected:
            raise PreferencesError("preference record has unexpected or missing fields")
        user_id = record["user_id"]
        if not isinstance(user_id, str) or not user_id.strip():
            raise PreferencesError("preference record user_id invalid")
        try:
            mode = OperatingMode.parse(record["operating_mode"]) if record["operating_mode"] is not None else None
            personality = (
                RiskPersonality.parse(record["risk_personality"]) if record["risk_personality"] is not None else None
            )
        except ValueError as exc:
            raise PreferencesError(str(exc)) from exc
        return cls(
            user_id=user_id,
            operating_mode=mode,
            risk_personality=personality,
            disclosure_version_acknowledged=record["disclosure_version_acknowledged"],
            updated_at_utc=record["updated_at_utc"],
        )


def _now_iso(now: datetime | None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


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
        if document.get("schema") != PREFERENCES_SCHEMA or not isinstance(document.get("users"), dict):
            raise PreferencesError("preferences schema mismatch")
        return document["users"]

    def get(self, user_id: str) -> UserTradingPreferences:
        record = self._read_all().get(user_id)
        if record is None:
            return UserTradingPreferences(user_id=user_id)
        preferences = UserTradingPreferences.from_record(record)
        if preferences.user_id != user_id:
            raise PreferencesError("preference record user mismatch")
        return preferences

    def _update(self, user_id: str, now: datetime | None, **changes: Any) -> UserTradingPreferences:
        if not isinstance(user_id, str) or not user_id.strip():
            raise PreferencesError("user_id required")
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_path, timeout_seconds=10.0):
            users = self._read_all()
            current = (
                UserTradingPreferences.from_record(users[user_id]) if user_id in users else UserTradingPreferences(user_id)
            )
            updated = replace(current, updated_at_utc=_now_iso(now), **changes)
            users[user_id] = updated.to_record()
            atomic_write_json(self.path, {"schema": PREFERENCES_SCHEMA, "users": users}, expected_root=self.root)
        return updated

    def select_operating_mode(self, user_id: str, mode: OperatingMode | str, *, now: datetime | None = None) -> UserTradingPreferences:
        return self._update(user_id, now, operating_mode=OperatingMode.parse(mode.value if isinstance(mode, OperatingMode) else mode))

    def select_risk_personality(
        self, user_id: str, personality: RiskPersonality | str, *, now: datetime | None = None
    ) -> UserTradingPreferences:
        parsed = RiskPersonality.parse(personality.value if isinstance(personality, RiskPersonality) else personality)
        return self._update(user_id, now, risk_personality=parsed)

    def acknowledge_disclosure(self, user_id: str, version: str, *, now: datetime | None = None) -> UserTradingPreferences:
        if version != DISCLOSURE_VERSION:
            raise PreferencesError("disclosure version is not current")
        return self._update(user_id, now, disclosure_version_acknowledged=version)


def default_store_root() -> Path:
    """Artifacts location; overridable for tests and isolated runs."""
    return Path(os.environ.get("CSS_TRADING_PROFILES_DIR") or "artifacts/trading_profiles")
