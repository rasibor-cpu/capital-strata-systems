from __future__ import annotations

import copy
import json
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


log = logging.getLogger(__name__)


class SessionRenewalManager:
    """Renew max-age expiry only for broker-disabled paper runtime sessions."""

    DEFAULT_MAX_SESSION_SECONDS = 24 * 60 * 60
    RENEWED_EVENT = "PAPER_SESSION_RENEWED"

    def __init__(self, *, session_state_path: str | Path | None = None) -> None:
        self.session_state_path = Path(session_state_path) if session_state_path else None

    def evaluate(
        self,
        session_state: Mapping[str, Any] | None = None,
        *,
        now: datetime | None = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        payload = dict(session_state) if isinstance(session_state, Mapping) else self._read_session()
        session = self._canonical_session(payload)
        now_dt = now or datetime.now(timezone.utc)
        started_at = self._session_start(session)
        max_seconds = self._max_session_seconds(session)
        age = max(0.0, (now_dt - started_at).total_seconds()) if started_at else None
        seconds_until = max_seconds - age if age is not None else None
        expired_by_max_age = seconds_until is not None and seconds_until <= 0

        broker_mode = self._broker_mode(session, payload)
        runtime_mode = self._runtime_mode(session, payload, broker_mode)
        live_mode_selected = runtime_mode == "LIVE" or broker_mode == "LIVE"
        broker_execution_enabled = self._broker_execution_enabled(session, payload)
        quiet_mode = self._quiet_mode(session, payload)
        continuous_enabled = self._continuous_enabled(session, payload)
        renewal_allowed = (
            continuous_enabled
            and not live_mode_selected
            and broker_mode == "PAPER"
            and not broker_execution_enabled
            and not quiet_mode
        )
        live_renewal_blocked = live_mode_selected or broker_execution_enabled

        renewal_count = self._int_value(session.get("session_renewal_count"))
        last_renewal_at = self._text_value(session.get("last_session_renewal_at"))
        renewal_reason = self._text_value(session.get("session_renewal_reason"))
        renewal_event = None
        updated_payload: dict[str, Any] | None = None

        if expired_by_max_age and renewal_allowed and started_at is not None:
            renewal_count += 1
            last_renewal_at = now_dt.isoformat()
            renewal_reason = self.RENEWED_EVENT
            renewal_event = self.RENEWED_EVENT
            updated_payload = self._renew_payload(payload, now_dt, renewal_count, renewal_reason)
            if persist:
                self._persist_payload(updated_payload)
            log.info(self.RENEWED_EVENT)
            started_at = now_dt
            age = 0.0
            seconds_until = max_seconds
        elif not expired_by_max_age and renewal_allowed:
            renewal_reason = renewal_reason or "paper_session_active"

        next_time = None
        if started_at is not None:
            next_time = datetime.fromtimestamp(started_at.timestamp() + max_seconds, tz=timezone.utc).isoformat()

        renewal_mode = "AUTO_PAPER" if renewal_allowed else "BLOCKED"
        if not continuous_enabled:
            renewal_mode = "DISABLED"

        blockers: list[str] = []
        if live_mode_selected:
            blockers.append("live_mode_selected")
        if broker_execution_enabled:
            blockers.append("broker_execution_enabled")
        if quiet_mode:
            blockers.append("quiet_mode_active")
        if not continuous_enabled:
            blockers.append("continuous_paper_runtime_disabled")

        return {
            "status": "OK",
            "session_renewal_mode": renewal_mode,
            "last_session_renewal_at": last_renewal_at or None,
            "session_renewal_count": renewal_count,
            "session_renewal_reason": renewal_reason or None,
            "continuous_paper_runtime_enabled": continuous_enabled,
            "current_session_age_seconds": round(age, 6) if age is not None else None,
            "max_session_seconds": max_seconds,
            "renewal_count": renewal_count,
            "renewal_mode": renewal_mode,
            "renewal_allowed": renewal_allowed,
            "next_expiry_or_renewal_time": next_time,
            "seconds_until_expiry": round(seconds_until, 6) if seconds_until is not None else None,
            "live_renewal_blocked": live_renewal_blocked,
            "broker_mode": broker_mode,
            "runtime_mode": runtime_mode,
            "broker_execution_enabled": broker_execution_enabled,
            "expired_by_max_age": expired_by_max_age,
            "renewed": renewal_event is not None,
            "renewal_event": renewal_event,
            "renewal_blockers": sorted(set(blockers)),
            "updated_session_state": updated_payload,
            "advisory_only": True,
            "execution_allowed": False,
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
                "broker_mode": payload.get("broker_mode"),
                "runtime_mode": payload.get("runtime_mode", payload.get("engine_mode")),
                "engine_mode": payload.get("engine_mode"),
                "quiet_mode_active": payload.get("quiet_mode_active", payload.get("session_expired_quiet_mode", False)),
            }
        session = payload.get("session", payload)
        return dict(session) if isinstance(session, Mapping) else {}

    def _renew_payload(
        self,
        payload: Mapping[str, Any],
        now: datetime,
        renewal_count: int,
        renewal_reason: str,
    ) -> dict[str, Any]:
        updated = copy.deepcopy(dict(payload))
        audit = {
            "session_renewal_mode": "AUTO_PAPER",
            "last_session_renewal_at": now.isoformat(),
            "session_renewal_count": renewal_count,
            "session_renewal_reason": renewal_reason,
            "continuous_paper_runtime_enabled": True,
        }
        if isinstance(updated.get("session"), dict):
            session = updated["session"]
            session.update(audit)
            session["start_time"] = now.isoformat()
            session["session_started_at"] = now.isoformat()
            session["last_activity"] = now.isoformat()
            session["session_continuity_status"] = "RESUMED"
            session["session_expired_quiet_mode"] = False
        elif isinstance(updated.get("session_user_ctx"), dict):
            updated.update(audit)
            user_ctx = updated["session_user_ctx"]
            status = user_ctx.get("session_status")
            if not isinstance(status, dict):
                status = {}
                user_ctx["session_status"] = status
            status.update(audit)
            status["active"] = True
            status["created"] = now.timestamp()
            status["last_activity"] = now.timestamp()
            user_ctx["session_created"] = now.timestamp()
        else:
            updated["session"] = {
                **audit,
                "engine_mode": "PAPER",
                "broker_mode": "PAPER",
                "start_time": now.isoformat(),
                "session_started_at": now.isoformat(),
                "last_activity": now.isoformat(),
            }
        return updated

    def _persist_payload(self, payload: Mapping[str, Any]) -> None:
        if self.session_state_path is None:
            return
        try:
            self.session_state_path.parent.mkdir(parents=True, exist_ok=True)
            self.session_state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            log.exception("Failed to persist paper session renewal state")

    def _read_session(self) -> dict[str, Any]:
        if self.session_state_path is None or not self.session_state_path.exists():
            return {}
        try:
            payload = json.loads(self.session_state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _session_start(self, session: Mapping[str, Any]) -> datetime | None:
        return self._parse_time(
            session.get("created")
            or session.get("session_created")
            or session.get("start_time")
            or session.get("started_at")
            or session.get("session_started_at")
            or session.get("authenticated_at")
        )

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

    @classmethod
    def _broker_mode(cls, session: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
        normalized = cls._mode_text(session.get("broker_mode") or payload.get("broker_mode"))
        return "LIVE" if normalized == "LIVE" else "PAPER"

    @classmethod
    def _runtime_mode(cls, session: Mapping[str, Any], payload: Mapping[str, Any], broker_mode: str) -> str:
        for value in (
            session.get("engine_mode"),
            session.get("runtime_mode"),
            session.get("mode"),
            payload.get("engine_mode"),
            payload.get("runtime_mode"),
        ):
            normalized = cls._mode_text(value)
            if normalized in {"LIVE", "PAPER"}:
                return normalized
        return broker_mode

    @classmethod
    def _broker_execution_enabled(cls, session: Mapping[str, Any], payload: Mapping[str, Any]) -> bool:
        keys = (
            "broker_execution_enabled",
            "broker_execution_allowed",
            "broker_execution_armed",
            "live_execution_enabled",
            "live_trading_enabled",
            "allow_live_execution",
        )
        for source in (session, payload):
            for key in keys:
                if key in source and cls._bool_value(source.get(key)):
                    return True
        return False

    @classmethod
    def _continuous_enabled(cls, session: Mapping[str, Any], payload: Mapping[str, Any]) -> bool:
        for source in (session, payload):
            if "continuous_paper_runtime_enabled" in source:
                return cls._bool_value(source.get("continuous_paper_runtime_enabled"))
        return True

    @staticmethod
    def _quiet_mode(session: Mapping[str, Any], payload: Mapping[str, Any]) -> bool:
        for source in (session, payload):
            for key in ("quiet_mode_active", "session_expired_quiet_mode", "quiet_mode", "trading_quiet_mode"):
                if bool(source.get(key, False)):
                    return True
        status = str(session.get("runtime_mode", session.get("status", ""))).upper()
        return "QUIET" in status

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
    def _mode_text(value: Any) -> str:
        normalized = str(value or "").strip().upper()
        if normalized in {"LIVE", "REAL", "PROD", "PRODUCTION"}:
            return "LIVE"
        if normalized in {"PAPER", "PRACTICE", "SIM", "SIMULATED", "SANDBOX", "TEST", "SAFE", ""}:
            return "PAPER"
        return normalized

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "armed", "live"}

    @staticmethod
    def _int_value(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _text_value(value: Any) -> str:
        text = str(value or "").strip()
        return "" if text.lower() in {"", "none", "null", "n/a", "na"} else text
