from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.runtime.session_renewal import SessionRenewalManager


class RuntimeSessionContinuityError(RuntimeError):
    """Fail-closed exception for runtime session continuity checks."""


class RuntimeSessionContinuityMonitor:
    """Observe session expiry and quiet mode without changing authority."""

    DEFAULT_MAX_SESSION_SECONDS = 24 * 60 * 60
    EXPIRING_SOON_SECONDS = 30 * 60

    def __init__(self, *, session_state_path: str | Path | None = None) -> None:
        self.session_state_path = Path(session_state_path) if session_state_path else None
        self.session_renewal = SessionRenewalManager(session_state_path=self.session_state_path)

    def evaluate(
        self,
        session_state: Mapping[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        payload = session_state if isinstance(session_state, Mapping) else self._read_session()
        if not isinstance(payload, Mapping) or not payload:
            return self._unknown("session_state_unavailable")

        session = self._canonical_session(payload)
        now_dt = now or datetime.now(timezone.utc)
        started_at = self._session_start(session)
        last_activity = self._parse_time(session.get("last_activity"))
        max_seconds = self._max_session_seconds(session)
        idle_timeout = self._idle_timeout_seconds(session)
        age = max(0.0, (now_dt - started_at).total_seconds()) if started_at else None
        idle_age = max(0.0, (now_dt - last_activity).total_seconds()) if last_activity else None
        seconds_until = max_seconds - age if age is not None else None
        seconds_until_idle = idle_timeout - idle_age if idle_timeout is not None and idle_age is not None else None
        idle_expired = seconds_until_idle is not None and seconds_until_idle <= 0
        quiet_mode = self._quiet_mode(session)
        renewal = self.session_renewal.evaluate(
            payload,
            now=now_dt,
            persist=self.session_state_path is not None,
        )
        paper_session_renewed = bool(renewal.get("renewed"))
        explicitly_resumed = str(session.get("session_continuity_status", session.get("auth_status", ""))).upper() == "RESUMED"
        session_active = bool(session.get("active", True))
        role_profile = session.get("role_profile", {})
        role_profile = role_profile if isinstance(role_profile, Mapping) else {}
        role_can_paper = bool(role_profile.get("can_execute_paper_trading", True))
        role_can_live = bool(role_profile.get("can_execute_live_trading", False))
        has_role_paper = "can_execute_paper_trading" in role_profile
        has_role_live = "can_execute_live_trading" in role_profile

        warnings: list[str] = []
        actions: list[str] = []
        if age is None:
            status = "UNKNOWN"
            reauth_required = True
            warnings.append("session_start_time_unavailable")
            actions.append("Re-authenticate through the existing login flow before continuing validation.")
        elif explicitly_resumed:
            status = "RESUMED"
            reauth_required = False
            actions.append("Continue controlled paper validation monitoring.")
        elif not session_active:
            status = "REAUTH_REQUIRED"
            reauth_required = True
            warnings.append("session_inactive")
            actions.append("Re-authenticate through the existing login flow to resume paper validation.")
        elif quiet_mode:
            status = "REAUTH_REQUIRED"
            reauth_required = True
            warnings.append("quiet_mode_active")
            actions.append("Re-authenticate through the existing login flow to resume paper validation.")
        elif paper_session_renewed:
            status = "ACTIVE"
            reauth_required = False
            age = renewal.get("current_session_age_seconds")
            seconds_until = renewal.get("seconds_until_expiry")
            actions.append("Paper session max-age was automatically renewed for broker-disabled paper validation.")
        elif seconds_until is not None and seconds_until <= 0:
            status = "EXPIRED"
            reauth_required = True
            warnings.append("session_expired")
            if idle_expired:
                warnings.append("idle_timeout_exceeded")
            actions.append("Re-authenticate through the existing login flow; do not bypass session expiry.")
        elif idle_expired:
            status = "REAUTH_REQUIRED"
            reauth_required = True
            warnings.append("idle_timeout_exceeded")
            actions.append("Re-authenticate through the existing login flow after idle timeout.")
        elif seconds_until is not None and seconds_until <= self.EXPIRING_SOON_SECONDS:
            status = "EXPIRING_SOON"
            reauth_required = False
            warnings.append("session_expiring_soon")
            actions.append("Plan operator re-authentication before max session age is reached.")
        else:
            status = "ACTIVE"
            reauth_required = False
            actions.append("Session continuity is acceptable for paper validation.")

        status_allows_paper = status in {"ACTIVE", "EXPIRING_SOON", "RESUMED"}
        return {
            "session_continuity_status": status,
            "session_age_seconds": round(age, 6) if age is not None else None,
            "idle_age_seconds": round(idle_age, 6) if idle_age is not None else None,
            "max_session_seconds": max_seconds,
            "idle_timeout_seconds": idle_timeout,
            "seconds_until_expiry": round(seconds_until, 6) if seconds_until is not None else None,
            "seconds_until_idle_timeout": round(seconds_until_idle, 6) if seconds_until_idle is not None else None,
            "quiet_mode_active": quiet_mode,
            "can_paper_execute": role_can_paper if has_role_paper else status_allows_paper,
            "can_live_execute": role_can_live if has_role_live else False,
            "reauth_required": reauth_required,
            "recommended_actions": actions,
            "warnings": sorted(set(warnings)),
            "advisory_only": True,
            "execution_allowed": False,
            "session_renewal_mode": renewal.get("session_renewal_mode"),
            "last_session_renewal_at": renewal.get("last_session_renewal_at"),
            "session_renewal_count": renewal.get("session_renewal_count", 0),
            "session_renewal_reason": renewal.get("session_renewal_reason"),
            "continuous_paper_runtime_enabled": renewal.get("continuous_paper_runtime_enabled", False),
            "renewal_count": renewal.get("renewal_count", 0),
            "renewal_mode": renewal.get("renewal_mode"),
            "renewal_allowed": renewal.get("renewal_allowed", False),
            "next_expiry_or_renewal_time": renewal.get("next_expiry_or_renewal_time"),
            "live_renewal_blocked": renewal.get("live_renewal_blocked", False),
            "broker_execution_enabled": renewal.get("broker_execution_enabled", False),
        }

    @staticmethod
    def _canonical_session(payload: Mapping[str, Any]) -> dict[str, Any]:
        user_ctx = payload.get("session_user_ctx")
        if isinstance(user_ctx, Mapping):
            status = user_ctx.get("session_status", {})
            status = status if isinstance(status, Mapping) else {}
            role_profile = user_ctx.get("role_profile", {})
            role_profile = role_profile if isinstance(role_profile, Mapping) else {}
            return {
                **dict(status),
                "session_created": user_ctx.get("session_created"),
                "role_profile": dict(role_profile),
                "quiet_mode_active": payload.get("quiet_mode_active", payload.get("session_expired_quiet_mode", False)),
                "runtime_mode": payload.get("runtime_mode", payload.get("engine_mode")),
                "status": payload.get("status"),
            }
        session = payload.get("session", payload)
        return dict(session) if isinstance(session, Mapping) else {}

    def _session_start(self, session: Mapping[str, Any]) -> datetime | None:
        return self._parse_time(
            session.get("created")
            or session.get("session_created")
            or session.get("start_time")
            or session.get("started_at")
            or session.get("session_started_at")
            or session.get("authenticated_at")
        )

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
    def _idle_timeout_seconds(session: Mapping[str, Any]) -> float | None:
        value = session.get("idle_timeout_seconds")
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None

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
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                return None
        try:
            text = str(value).strip()
            if text.replace(".", "", 1).isdigit():
                return datetime.fromtimestamp(float(text), tz=timezone.utc)
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
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
            "idle_age_seconds": None,
            "max_session_seconds": None,
            "idle_timeout_seconds": None,
            "seconds_until_expiry": None,
            "seconds_until_idle_timeout": None,
            "quiet_mode_active": False,
            "can_paper_execute": False,
            "can_live_execute": False,
            "reauth_required": True,
            "recommended_actions": ["Re-authenticate through the existing login flow before continuing validation."],
            "warnings": [reason],
            "advisory_only": True,
            "execution_allowed": False,
            "session_renewal_mode": "UNKNOWN",
            "last_session_renewal_at": None,
            "session_renewal_count": 0,
            "session_renewal_reason": None,
            "continuous_paper_runtime_enabled": False,
            "renewal_count": 0,
            "renewal_mode": "UNKNOWN",
            "renewal_allowed": False,
            "next_expiry_or_renewal_time": None,
            "live_renewal_blocked": True,
            "broker_execution_enabled": False,
        }
