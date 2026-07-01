from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ValidationConfidenceEngineError(RuntimeError):
    """Fail-closed exception for validation confidence calculation."""


class ValidationConfidenceEngine:
    """Compute deterministic confidence in continued paper validation."""

    def evaluate(
        self,
        *,
        runtime_health: Mapping[str, Any] | None,
        validation_readiness: Mapping[str, Any] | None,
        artifact_freshness: Mapping[str, Any] | None,
        supervisor_stability: Mapping[str, Any] | None = None,
        session_continuity: Mapping[str, Any] | None = None,
        recommendation_stability: Mapping[str, Any] | None = None,
        portfolio_decision: Mapping[str, Any] | None = None,
        runtime_health_trend: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        score = 100
        reasons: list[str] = []
        score -= self._penalty(self._status(runtime_health, "runtime_health", "overall_operational_health"), reasons, "runtime_health")
        readiness = self._status(validation_readiness, "readiness_status")
        if readiness == "READY_WITH_CAUTION":
            score -= 20
            reasons.append("validation_ready_with_caution")
        elif readiness != "READY":
            score -= 35
            reasons.append("validation_not_ready")
        score -= self._penalty(self._status(artifact_freshness, "freshness_status"), reasons, "artifact_freshness")
        score -= self._penalty(self._session_status(session_continuity), reasons, "session_continuity")
        score -= self._penalty(self._status(portfolio_decision, "overall_status", "status"), reasons, "portfolio_decision")

        restarts = self._number(supervisor_stability, "restart_count")
        recoveries = self._number(supervisor_stability, "recovery_count")
        if restarts >= 3:
            score -= 20
            reasons.append("restart_frequency_high")
        if restarts and recoveries < restarts:
            score -= 10
            reasons.append("supervisor_recovery_incomplete")

        rec_status = self._status(recommendation_stability, "recommendation_stability", "recommendation_stability_trend")
        if rec_status in {"LOW", "UNSTABLE", "DEGRADING", "DEGRADED"}:
            score -= 15
            reasons.append("recommendation_stability_degraded")

        trends = runtime_health_trend.get("trends", {}) if isinstance(runtime_health_trend, Mapping) else {}
        if isinstance(trends, Mapping):
            current = trends.get("1h", {})
            if isinstance(current, Mapping) and int(current.get("degradation_count", 0) or 0) > 0:
                score -= 10
                reasons.append("runtime_health_trend_degraded")

        bounded = max(0, min(100, int(round(score))))
        return {
            "status": "OK",
            "confidence_score": bounded,
            "confidence_grade": self._grade(bounded),
            "confidence_reason": "; ".join(sorted(set(reasons))) if reasons else "validation_signals_green",
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _status(payload: Mapping[str, Any] | None, *keys: str) -> str:
        if not isinstance(payload, Mapping):
            return "UNKNOWN"
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return str(value).upper()
        return "UNKNOWN"

    @staticmethod
    def _session_status(payload: Mapping[str, Any] | None) -> str:
        status = ValidationConfidenceEngine._status(payload, "session_continuity_status")
        return {"ACTIVE": "GREEN", "RESUMED": "GREEN", "EXPIRING_SOON": "AMBER", "EXPIRED": "RED", "REAUTH_REQUIRED": "RED"}.get(status, status)

    @staticmethod
    def _penalty(status: str, reasons: list[str], name: str) -> int:
        if status in {"GREEN", "OK"}:
            return 0
        if status in {"AGING"}:
            reasons.append(f"{name}_aging")
            return 10
        if status in {"AMBER", "WARNING", "DEGRADED", "PARTIAL", "LIMITED"}:
            reasons.append(f"{name}_degraded")
            return 20
        reasons.append(f"{name}_red_or_unknown")
        return 35

    @staticmethod
    def _number(payload: Mapping[str, Any] | None, key: str) -> float:
        if not isinstance(payload, Mapping):
            return 0.0
        try:
            return float(payload.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _grade(score: int) -> str:
        if score >= 85:
            return "HIGH"
        if score >= 65:
            return "MEDIUM"
        if score >= 40:
            return "LOW"
        return "FAIL_CLOSED"
