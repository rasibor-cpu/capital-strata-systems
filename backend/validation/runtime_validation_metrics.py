from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RuntimeValidationMetricsError(RuntimeError):
    """Fail-closed exception for runtime validation metric calculation."""


class RuntimeValidationMetrics:
    """Calculate operational validation metrics without execution authority."""

    def __init__(self, *, artifacts_dir: str | Path | None = None) -> None:
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else None

    def calculate(
        self,
        *,
        runtime_health: Mapping[str, Any] | None = None,
        performance: Mapping[str, Any] | None = None,
        session_validation: Mapping[str, Any] | None = None,
        artifact_publisher: Mapping[str, Any] | None = None,
        validation_events: Sequence[Mapping[str, Any]] | None = None,
        timestamp: str | None = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        events = [item for item in (validation_events or []) if isinstance(item, Mapping)]
        cycle_durations = [self._float(item.get("cycle_duration_seconds")) for item in events if item.get("cycle_duration_seconds") is not None]
        write_failures = len([item for item in events if item.get("artifact_write_failed") is True])
        write_attempts = len([item for item in events if "artifact_write_failed" in item])
        if isinstance(artifact_publisher, Mapping):
            published = artifact_publisher.get("published_artifacts", {})
            warnings = artifact_publisher.get("warnings", [])
            write_attempts = max(write_attempts, len(published) + len(warnings if isinstance(warnings, list) else []))
            write_failures = max(write_failures, len([item for item in warnings if str(item).startswith("write_failed_")]) if isinstance(warnings, list) else 0)

        payload = {
            "status": "OK",
            "runtime_uptime": self._value(session_validation, "session_duration", default=0),
            "runtime_cycles": len(events) or self._int(self._value(session_validation, "cycle_count", default=0)),
            "average_cycle_duration": self._average(cycle_durations),
            "maximum_cycle_duration": max(cycle_durations) if cycle_durations else 0.0,
            "dashboard_latency": self._value(performance, "dashboard_latency_ms", default=0.0),
            "api_latency": self._value(performance, "api_latency_ms", "average_api_latency_ms", default=0.0),
            "artifact_refresh_latency": self._value(performance, "json_persistence_latency_ms", "artifact_refresh_latency_ms", default=0.0),
            "artifact_write_success_rate": self._success_rate(write_attempts, write_failures),
            "artifact_write_failures": write_failures,
            "cache_efficiency": self._value(performance, "cache_hit_rate", default=0.0),
            "supervisor_recovery_rate": self._recovery_rate(session_validation),
            "restart_frequency": self._value(session_validation, "restart_count", default=0),
            "validation_degradation_events": len([item for item in events if str(item.get("validation_state", "")).upper() in {"AMBER", "RED"}]),
            "recommendation_stability_trend": self._recommendation_stability(events),
            "runtime_health": self._value(runtime_health, "runtime_health", "overall_operational_health", default="UNKNOWN"),
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "advisory_only": True,
            "execution_allowed": False,
        }
        if persist:
            self._persist(payload)
        return payload

    @staticmethod
    def _value(payload: Mapping[str, Any] | None, *keys: str, default: Any = None) -> Any:
        if not isinstance(payload, Mapping):
            return default
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return value
        return default

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _int(cls, value: Any) -> int:
        return int(cls._float(value))

    @staticmethod
    def _average(values: list[float]) -> float:
        return round(sum(values) / len(values), 6) if values else 0.0

    @staticmethod
    def _success_rate(attempts: int, failures: int) -> float:
        if attempts <= 0:
            return 100.0
        return round(max(0.0, (attempts - failures) / attempts * 100.0), 6)

    @classmethod
    def _recovery_rate(cls, session_validation: Mapping[str, Any] | None) -> float:
        restarts = cls._float(cls._value(session_validation, "restart_count", default=0))
        recoveries = cls._float(cls._value(session_validation, "recovery_count", default=0))
        if restarts <= 0:
            return 100.0
        return round(min(100.0, recoveries / restarts * 100.0), 6)

    @classmethod
    def _recommendation_stability(cls, events: list[Mapping[str, Any]]) -> str:
        values = [str(item.get("recommendation_stability", "")).upper() for item in events if item.get("recommendation_stability")]
        if not values:
            return "UNKNOWN"
        unstable = len([item for item in values if item in {"LOW", "UNSTABLE", "DEGRADED"}])
        return "DEGRADING" if unstable > len(values) / 2 else "STABLE"

    def _persist(self, payload: Mapping[str, Any]) -> None:
        if self.artifacts_dir is None:
            return
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (self.artifacts_dir / "runtime_validation_metrics.json").write_text(
            json.dumps(dict(payload), indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
