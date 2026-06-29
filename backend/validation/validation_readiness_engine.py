from __future__ import annotations

from typing import Any, Iterable, Mapping


class ValidationReadinessEngineError(RuntimeError):
    """Fail-closed exception for paper validation readiness checks."""


class ValidationReadinessEngine:
    """Determine readiness to begin or continue controlled paper validation."""

    def evaluate(
        self,
        *,
        runtime_health: Mapping[str, Any] | None,
        session_validation: Mapping[str, Any] | None,
        portfolio_decision: Mapping[str, Any] | None,
        operational_telemetry: Mapping[str, Any] | None = None,
        stale_artifacts: Iterable[Any] | None = None,
        recent_errors: Iterable[Any] | None = None,
    ) -> dict[str, Any]:
        blockers: list[str] = []
        warnings: list[str] = []
        actions: list[str] = []

        runtime_status = self._status(runtime_health, "runtime_health", "overall_status")
        session_status = self._status(session_validation, "session_status")
        decision_status = self._status(portfolio_decision, "overall_status", "status")
        telemetry_status = self._status(operational_telemetry, "overall_status", "status")
        stale_count = self._count(stale_artifacts)
        error_count = self._count(recent_errors)

        if runtime_status in {"RED", "FAILED", "FAIL", "STOPPED", "DATA UNAVAILABLE"}:
            blockers.append("runtime_health_not_green")
            actions.append("Restore runtime health before beginning paper validation.")
        elif runtime_status in {"AMBER", "WARNING", "DEGRADED"}:
            warnings.append("runtime_health_degraded")
            actions.append("Monitor degraded runtime health during paper validation.")

        if session_status in {"RED", "FAILED", "FAIL", "DATA UNAVAILABLE"}:
            blockers.append("session_validation_not_green")
            actions.append("Resolve session validation blockers before continuing.")
        elif session_status in {"AMBER", "WARNING", "DEGRADED"}:
            warnings.append("session_validation_degraded")
            actions.append("Continue only with explicit monitoring of session warnings.")

        if decision_status in {"RED", "FAILED", "FAIL", "DATA UNAVAILABLE"}:
            blockers.append("portfolio_decision_not_green")
            actions.append("Restore portfolio decision advisory health before validation.")
        elif decision_status in {"AMBER", "WARNING", "DEGRADED"}:
            warnings.append("portfolio_decision_degraded")
            actions.append("Record portfolio decision degradation in validation notes.")

        if telemetry_status in {"RED", "FAILED", "FAIL"}:
            blockers.append("operational_telemetry_red")
            actions.append("Resolve operational telemetry faults before validation.")
        elif telemetry_status in {"AMBER", "WARNING", "DEGRADED"}:
            warnings.append("operational_telemetry_degraded")

        if stale_count >= 3:
            blockers.append("stale_artifacts_exceed_limit")
            actions.append("Refresh stale validation artifacts before starting.")
        elif stale_count > 0:
            warnings.append("stale_artifacts_present")
            actions.append("Review stale artifacts during the paper validation run.")

        if error_count >= 3:
            blockers.append("recent_errors_exceed_limit")
            actions.append("Resolve recent runtime errors before paper validation.")
        elif error_count > 0:
            warnings.append("recent_errors_present")
            actions.append("Track recent errors as validation warnings.")

        confidence = self._confidence(len(blockers), len(warnings))
        if blockers:
            readiness_status = "NOT_READY"
        elif warnings:
            readiness_status = "READY_WITH_CAUTION"
        else:
            readiness_status = "READY"
            actions.append("Proceed with controlled paper validation monitoring.")

        return {
            "status": "OK",
            "readiness_status": readiness_status,
            "confidence": confidence,
            "blockers": sorted(set(blockers)),
            "warnings": sorted(set(warnings)),
            "recommended_actions": list(dict.fromkeys(actions)),
            "advisory_only": True,
            "paper_validation_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _status(payload: Mapping[str, Any] | None, *keys: str) -> str:
        if not isinstance(payload, Mapping):
            return "DATA UNAVAILABLE"
        for key in keys:
            value = payload.get(key)
            if value:
                return str(value).strip().upper()
        return "DATA UNAVAILABLE"

    @staticmethod
    def _count(values: Iterable[Any] | None) -> int:
        if values is None or isinstance(values, (str, bytes)):
            return 0
        try:
            return len(list(values))
        except TypeError:
            return 0

    @staticmethod
    def _confidence(blocker_count: int, warning_count: int) -> int:
        return max(0, min(100, 100 - (blocker_count * 25) - (warning_count * 10)))
