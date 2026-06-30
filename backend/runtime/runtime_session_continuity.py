from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RuntimeSessionContinuityError(RuntimeError):
    """Fail-closed exception for runtime session continuity checks."""


class RuntimeSessionContinuityMonitor:
    """Observe session expiry and quiet mode without changing authority."""

    DEFAULT_MAX_SESSION_SECONDS = 24 * 60 * 60
    EXPIRING_SOON_SECONDS = 30 * 60

    def __init__(self, *, session_state_path: str | Path | None = None) -> None:
        self.session_state_path = Path(session_state_path) if session_state_path else None

    def evaluate(
        self,
        session_state: Mapping[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        payload = session_state if isinstance(session_state, Mapping) else self._read_session()
        if not isinstance(payload, Mapping) or not payload:
            return self._unknown("session_state_unavailable")

        session = payload.get("session", payload)
        session = session if isinstance(session, Mapping) else {}
        now_dt = now or datetime.now(timezone.utc)
        started_at = self._parse_time(
            session.get("start_time")
            or session.get("started_at")
            or session.get("session_started_at")
            or session.get("authenticated_at")
        )
        max_seconds = self._max_session_seconds(session)
        age = max(0.0, (now_dt - started_at).total_seconds()) if started_at else None
        seconds_until = max_seconds - age if age is not None else None
        quiet_mode = self._quiet_mode(session)
        explicitly_resumed = str(session.get("session_continuity_status", session.get("auth_status", ""))).upper() == "RESUMED"

        warnings: list[str] = []
        actions: list[str] = []
        if age is None:
            status = "UNKNOWN"
            reauth_required = True
            can_paper = False
            warnings.append("session_start_time_unavailable")
            actions.append("Re-authenticate through the existing login flow before continuing validation.")
        elif explicitly_resumed:
            status = "RESUMED"
            reauth_required = False
            can_paper = True
            actions.append("Continue controlled paper validation monitoring.")
        elif quiet_mode:
            status = "REAUTH_REQUIRED"
            reauth_required = True
            can_paper = False
            warnings.append("quiet_mode_active")
            actions.append("Re-authenticate through the existing login flow to resume paper validation.")
        elif seconds_until is not None and seconds_until <= 0:
            status = "EXPIRED"
            reauth_required = True
            can_paper = False
            warnings.append("session_expired")
            actions.append("Re-authenticate through the existing login flow; do not bypass session expiry.")
        elif seconds_until is not None and seconds_until <= self.EXPIRING_SOON_SECONDS:
            status = "EXPIRING_SOON"
            reauth_required = False
            can_paper = True
            warnings.append("session_expiring_soon")
            actions.append("Plan operator re-authentication before max session age is reached.")
        else:
            status = "ACTIVE"
            reauth_required = False
            can_paper = True
            actions.append("Session continuity is acceptable for paper validation.")

        return {
            "session_continuity_status": status,
            "session_age_seconds": round(age, 6) if age is not None else None,
            "max_session_seconds": max_seconds,
            "seconds_until_expiry": round(seconds_until, 6) if seconds_until is not None else None,
            "quiet_mode_active": quiet_mode,
            "can_paper_execute": can_paper,
            "can_live_execute": False,
            "reauth_required": reauth_required,
            "recommended_actions": actions,
            "warnings": sorted(set(warnings)),
            "advisory_only": True,
            "execution_allowed": False,
        }

    def _read_session(self) -> dict[str, Any]:
        if self.session_state_path is None or not self.session_state_path.exists():
            return {}
        try:
            payload = json.loads(self.session_state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _max_session_seconds(cls, session: Mapping[str, Any]) -> float:
        for key in ("max_session_seconds", "max_session_sec", "max_session_age_seconds", "session_ttl_seconds"):
            value = session.get(key)
            if value is not None:
                try:
                    return max(0.0, float(value))
                except (TypeError, ValueError):
                    pass
        minutes = session.get("session_ttl_minutes")
        if minutes is not None:
            try:
                return max(0.0, float(minutes) * 60.0)
            except (TypeError, ValueError):
                pass
        return float(cls.DEFAULT_MAX_SESSION_SECONDS)

    @staticmethod
    def _quiet_mode(session: Mapping[str, Any]) -> bool:
        for key in ("quiet_mode_active", "session_expired_quiet_mode", "quiet_mode", "trading_quiet_mode"):
            if bool(session.get(key, False)):
                return True
        status = str(session.get("runtime_mode", session.get("status", ""))).upper()
        return "QUIET" in status or "EXPIRED" in status

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _unknown(reason: str) -> dict[str, Any]:
        return {
            "session_continuity_status": "UNKNOWN",
            "session_age_seconds": None,
            "max_session_seconds": None,
            "seconds_until_expiry": None,
            "quiet_mode_active": False,
            "can_paper_execute": False,
            "can_live_execute": False,
            "reauth_required": True,
            "recommended_actions": ["Re-authenticate through the existing login flow before continuing validation."],
            "warnings": [reason],
            "advisory_only": True,
            "execution_allowed": False,
        }
