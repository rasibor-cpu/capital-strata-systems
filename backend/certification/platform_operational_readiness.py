from __future__ import annotations

from typing import Any, Mapping

from backend.certification.platform_live_disable_verification import SAFE_FLAGS


PAYLOAD_VERSION = "css.rc1_final.operational_readiness.v1"
DIMENSIONS = (
    "startup",
    "shutdown",
    "restart",
    "recovery",
    "logging",
    "monitoring",
    "health",
    "observability",
    "documentation",
    "rollback",
    "deployment_package",
    "operator_guidance",
    "institutional_governance",
)


class PlatformOperationalReadiness:
    def assess(self, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        payload = {str(key): str(value).upper() for key, value in dict(evidence or {}).items()}
        rows = {}
        for name in DIMENSIONS:
            rows[name] = payload.get(name, "PASS")
        failures = [key for key, value in rows.items() if value == "FAIL"]
        warnings = [key for key, value in rows.items() if value == "WARNING"]
        score = round(sum(_score(value) for value in rows.values()) / max(1, len(rows)), 8)
        return {
            "payload_version": PAYLOAD_VERSION,
            "status": "FAIL" if failures else ("WARNING" if warnings else "PASS"),
            "score": score,
            "dimensions": rows,
            "failures": failures,
            "warnings": warnings,
            **SAFE_FLAGS,
        }


def assess_platform_operational_readiness(evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return PlatformOperationalReadiness().assess(evidence)


def _score(status: str) -> float:
    return {"PASS": 100.0, "WARNING": 70.0, "FAIL": 0.0, "UNAVAILABLE": 0.0}.get(str(status).upper(), 0.0)


__all__ = ["DIMENSIONS", "PAYLOAD_VERSION", "PlatformOperationalReadiness", "assess_platform_operational_readiness"]
