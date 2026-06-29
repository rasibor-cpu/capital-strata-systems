from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Any


class SessionValidationEngineError(RuntimeError):
    """Fail-closed exception for session validation."""


class SessionValidationEngine:
    """Validate runtime session freshness and operational stability."""

    def validate(
        self,
        session_state: Mapping[str, Any] | None,
        supervisor_state: Mapping[str, Any] | None = None,
        artifact_status: Mapping[str, Any] | None = None,
        advisory_status: Mapping[str, Any] | None = None,
        now: dt.datetime | None = None,
    ) -> dict[str, Any]:
        if not isinstance(session_state, Mapping):
            return self._unavailable("session_state_unavailable")

        now_utc = now or dt.datetime.now(dt.UTC)
        session = session_state.get("session", session_state)
        session = session if isinstance(session, Mapping) else {}
        supervisor = supervisor_state if isinstance(supervisor_state, Mapping) else {}
        artifacts = artifact_status if isinstance(artifact_status, Mapping) else {}
        advisory = advisory_status if isinstance(advisory_status, Mapping) else {}

        started_at = self._parse_time(session.get("start_time") or session.get("started_at"))
        heartbeat_at = self._parse_time(
            supervisor.get("last_heartbeat") or supervisor.get("last_heartbeat_at") or session.get("last_heartbeat")
        )
        session_duration = max(0.0, (now_utc - started_at).total_seconds()) if started_at else None
        heartbeat_age = max(0.0, (now_utc - heartbeat_at).total_seconds()) if heartbeat_at else None

        stale_artifacts = self._stale_artifacts(artifacts)
        stale_dashboard = bool(artifacts.get("dashboard_stale", False))
        stale_advisory_package = bool(advisory.get("stale_advisory_package", False))
        persistence_health = str(advisory.get("persistence_health", artifacts.get("persistence_health", "OK"))).upper()
        recommendation_stability = self._recommendation_stability(advisory.get("recommendations", []))
        policy_consistency = bool(advisory.get("policy_consistency", True))
        restart_count = int(max(0.0, self._float(supervisor.get("restart_count", session.get("restart_count", 0)))))
        recovery_count = int(max(0.0, self._float(supervisor.get("recovery_count", session.get("recovery_count", 0)))))

        status = "GREEN"
        health = "Operational session is healthy."
        if heartbeat_age is None or heartbeat_age > 300 or persistence_health not in {"OK", "GREEN"} or not policy_consistency:
            status = "RED"
            health = "Operational session requires intervention."
        elif stale_artifacts or stale_dashboard or stale_advisory_package or restart_count > 0 or recovery_count > 0 or heartbeat_age > 120:
            status = "AMBER"
            health = "Operational session is degraded and should be monitored."

        return {
            "status": "OK",
            "session_status": status,
            "session_duration": session_duration,
            "restart_count": restart_count,
            "recovery_count": recovery_count,
            "heartbeat_age": heartbeat_age,
            "stale_artifacts": stale_artifacts,
            "stale_dashboard": stale_dashboard,
            "stale_advisory_package": stale_advisory_package,
            "persistence_health": persistence_health,
            "recommendation_stability": recommendation_stability,
            "policy_consistency": policy_consistency,
            "runtime_heartbeat": heartbeat_at.isoformat() if heartbeat_at else None,
            "overall_operational_health": health,
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _stale_artifacts(artifact_status: Mapping[str, Any]) -> list[str]:
        stale = []
        for name, value in artifact_status.items():
            if name in {"dashboard_stale", "persistence_health"}:
                continue
            if isinstance(value, Mapping):
                is_stale = bool(value.get("stale", False))
                age = value.get("age_seconds")
                if age is not None:
                    try:
                        is_stale = is_stale or float(age) > float(value.get("stale_after_seconds", 300))
                    except (TypeError, ValueError):
                        pass
                if is_stale:
                    stale.append(str(name))
            elif bool(value):
                stale.append(str(name))
        return sorted(stale)

    @staticmethod
    def _recommendation_stability(recommendations: Any) -> str:
        if not isinstance(recommendations, list) or not recommendations:
            return "UNKNOWN"
        normalized = [str(item).upper() for item in recommendations if str(item).strip()]
        if not normalized:
            return "UNKNOWN"
        return "STABLE" if len(set(normalized[-5:])) == 1 else "CHANGING"

    @staticmethod
    def _parse_time(value: Any) -> dt.datetime | None:
        if not value:
            return None
        text = str(value).strip()
        try:
            parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.UTC)
        return parsed.astimezone(dt.UTC)

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "session_status": "RED",
            "session_duration": None,
            "restart_count": 0,
            "recovery_count": 0,
            "heartbeat_age": None,
            "stale_artifacts": [],
            "stale_dashboard": True,
            "stale_advisory_package": True,
            "persistence_health": "UNKNOWN",
            "recommendation_stability": "UNKNOWN",
            "policy_consistency": False,
            "runtime_heartbeat": None,
            "overall_operational_health": f"Session validation unavailable: {reason}.",
            "advisory_only": True,
            "execution_allowed": False,
        }
