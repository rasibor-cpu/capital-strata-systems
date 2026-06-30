from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ContinuousValidationMonitorError(RuntimeError):
    """Fail-closed exception for continuous validation monitoring."""


class ContinuousValidationMonitor:
    """Combine runtime validation signals into a paper-only validation state."""

    ORDER = {"GREEN": 0, "AMBER": 1, "RED": 2}

    def __init__(self, *, artifacts_dir: str | Path | None = None) -> None:
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else None

    def evaluate(
        self,
        *,
        runtime_health: Mapping[str, Any] | None,
        validation_readiness: Mapping[str, Any] | None,
        session_continuity: Mapping[str, Any] | None,
        artifact_freshness: Mapping[str, Any] | None,
        supervisor_state: Mapping[str, Any] | None = None,
        portfolio_lifecycle: Mapping[str, Any] | None = None,
        portfolio_decision: Mapping[str, Any] | None = None,
        advisory_snapshot: Mapping[str, Any] | None = None,
        timestamp: str | None = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        statuses = [
            self._runtime_status(runtime_health),
            self._readiness_status(validation_readiness),
            self._session_status(session_continuity),
            self._freshness_status(artifact_freshness),
            self._supervisor_status(supervisor_state),
            self._portfolio_status(portfolio_lifecycle, portfolio_decision, advisory_snapshot),
        ]
        validation_state = max(statuses, key=lambda item: self.ORDER.get(item, 2))
        warnings = self._list_values((runtime_health or {}).get("warnings", []))
        warnings.extend(self._list_values((validation_readiness or {}).get("warnings", [])))
        warnings.extend(self._list_values((session_continuity or {}).get("warnings", [])))
        warnings.extend(self._list_values((artifact_freshness or {}).get("warnings", [])))
        blockers = self._list_values((validation_readiness or {}).get("blockers", []))
        if validation_state == "RED" and not blockers:
            blockers.append("continuous_validation_red")

        payload = {
            "status": "OK",
            "validation_state": validation_state,
            "runtime_health": self._value(runtime_health, "runtime_health", "overall_operational_health"),
            "validation_readiness": self._value(validation_readiness, "readiness_status"),
            "session_continuity": self._value(session_continuity, "session_continuity_status"),
            "artifact_freshness": self._value(artifact_freshness, "freshness_status"),
            "portfolio_decision_status": self._value(portfolio_decision, "overall_status", "status"),
            "advisory_snapshot_status": self._value(advisory_snapshot, "snapshot_status", "status"),
            "warnings": sorted(set(warnings)),
            "blockers": sorted(set(blockers)),
            "recommendation": self._recommendation(validation_state),
            "timestamp": ts,
            "advisory_only": True,
            "execution_allowed": False,
        }
        if persist:
            self._persist(payload)
        return payload

    @staticmethod
    def _runtime_status(payload: Mapping[str, Any] | None) -> str:
        status = str(ContinuousValidationMonitor._value(payload, "runtime_health", "overall_operational_health", default="RED")).upper()
        return status if status in {"GREEN", "AMBER"} else "RED"

    @staticmethod
    def _readiness_status(payload: Mapping[str, Any] | None) -> str:
        status = str(ContinuousValidationMonitor._value(payload, "readiness_status", default="NOT_READY")).upper()
        if status == "READY":
            return "GREEN"
        if status == "READY_WITH_CAUTION":
            return "AMBER"
        return "RED"

    @staticmethod
    def _session_status(payload: Mapping[str, Any] | None) -> str:
        status = str(ContinuousValidationMonitor._value(payload, "session_continuity_status", default="UNKNOWN")).upper()
        if status in {"ACTIVE", "RESUMED"}:
            return "GREEN"
        if status == "EXPIRING_SOON":
            return "AMBER"
        return "RED"

    @staticmethod
    def _freshness_status(payload: Mapping[str, Any] | None) -> str:
        status = str(ContinuousValidationMonitor._value(payload, "freshness_status", default="RED")).upper()
        return status if status in {"GREEN", "AMBER"} else "RED"

    @staticmethod
    def _supervisor_status(payload: Mapping[str, Any] | None) -> str:
        status = str(ContinuousValidationMonitor._value(payload, "status", default="UNKNOWN")).upper()
        if status in {"RUNNING", "ONLINE", "HEALTHY", "GREEN"}:
            return "GREEN"
        if status in {"DEGRADED", "RECOVERING", "AMBER"}:
            return "AMBER"
        return "RED"

    @staticmethod
    def _portfolio_status(
        lifecycle: Mapping[str, Any] | None,
        decision: Mapping[str, Any] | None,
        snapshot: Mapping[str, Any] | None,
    ) -> str:
        life = str(ContinuousValidationMonitor._value(lifecycle, "portfolio_state", "lifecycle_status", default="UNKNOWN")).upper()
        decision_status = str(ContinuousValidationMonitor._value(decision, "overall_status", "status", default="RED")).upper()
        snapshot_status = str(ContinuousValidationMonitor._value(snapshot, "snapshot_status", "status", default="DATA UNAVAILABLE")).upper()
        if life == "BROKEN_PIPELINE" or decision_status in {"RED", "FAIL", "FAILED", "DATA UNAVAILABLE"}:
            return "RED"
        if snapshot_status in {"PARTIAL", "LIMITED"} or decision_status in {"AMBER", "WARNING", "DEGRADED"}:
            return "AMBER"
        return "GREEN"

    @staticmethod
    def _value(payload: Mapping[str, Any] | None, *keys: str, default: Any = "UNKNOWN") -> Any:
        if not isinstance(payload, Mapping):
            return default
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return value
        return default

    @staticmethod
    def _list_values(values: Any) -> list[str]:
        if isinstance(values, str):
            return [values]
        if isinstance(values, list):
            return [str(item) for item in values if str(item).strip()]
        return []

    @staticmethod
    def _recommendation(status: str) -> str:
        if status == "GREEN":
            return "Continuous paper validation can continue."
        if status == "AMBER":
            return "Continuous paper validation can continue with operator review."
        return "Pause validation progression until blockers are resolved."

    def _persist(self, payload: Mapping[str, Any]) -> None:
        if self.artifacts_dir is None:
            return
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (self.artifacts_dir / "runtime_validation_monitor.json").write_text(
            json.dumps(dict(payload), indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
