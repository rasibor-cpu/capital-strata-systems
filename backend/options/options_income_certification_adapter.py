from __future__ import annotations

from typing import Any, Mapping

from backend.certification.readiness_models import SubsystemReadiness
from backend.options.options_income_enterprise_adapter import (
    ENTERPRISE_SAFE_FLAGS,
    PAYLOAD_VERSION,
    SUBSYSTEM_ID,
    SUBSYSTEM_NAME,
    assert_enterprise_safe,
    normalize_timestamp,
)


class OptionsIncomeCertificationAdapter:
    def adapt(self, certification: Mapping[str, Any], *, timestamp: str | None = None) -> dict[str, Any]:
        payload = dict(certification)
        assert_enterprise_safe(payload)
        readiness = dict(payload.get("readiness", {})) if isinstance(payload.get("readiness"), Mapping) else {}
        generated_at = normalize_timestamp(timestamp or payload.get("timestamp") or payload.get("generated_at"))
        status = str(payload.get("certification_status", "FAIL")).upper()
        result = {
            "payload_version": PAYLOAD_VERSION,
            "subsystem_id": SUBSYSTEM_ID,
            "subsystem_name": SUBSYSTEM_NAME,
            "certification_version": "OI-010-to-EI-001",
            "certification_timestamp": generated_at,
            "module_results": list(payload.get("subsystems", [])),
            "integration_score": _score(readiness.get("integration_score", readiness.get("overall_score", payload.get("certification_score", 0.0)))),
            "determinism_score": _score(readiness.get("determinism_score", 100.0 if payload.get("replay_validation", {}).get("status") == "PASS" else 0.0)),
            "paper_safety_score": _score(readiness.get("paper_safety_score", 100.0 if payload.get("paper_only") is True else 0.0)),
            "dashboard_score": _score(readiness.get("dashboard_score", 0.0)),
            "broker_abstraction_score": _score(readiness.get("broker_abstraction_score", 0.0)),
            "documentation_score": _score(readiness.get("documentation_score", 0.0)),
            "overall_readiness": str(payload.get("overall_readiness", readiness.get("overall_readiness", "NOT_READY"))),
            "warnings": list(payload.get("warnings", [])),
            "failures": list(payload.get("blockers", [])),
            "unsupported_features": [
                "live_options_execution",
                "live_broker_activation",
                "assignment_execution",
                "roll_order_execution",
                "production_deployment_certification",
            ],
            "enterprise_certification_status": "REGISTERED_PENDING_CERTIFICATION" if status != "FAIL" else "INTEGRATION_FAILED",
            "marks_platform_rc1_certified": False,
            **ENTERPRISE_SAFE_FLAGS,
        }
        assert_enterprise_safe(result)
        return result

    def readiness_model(self, certification: Mapping[str, Any]) -> SubsystemReadiness:
        adapted = self.adapt(certification)
        return SubsystemReadiness(
            name=SUBSYSTEM_NAME,
            score=adapted["integration_score"],
            status="PASS" if adapted["enterprise_certification_status"] != "INTEGRATION_FAILED" else "FAIL",
            details=adapted,
        )


def adapt_options_income_certification(certification: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    return OptionsIncomeCertificationAdapter().adapt(certification, **kwargs)


def _score(value: Any) -> float:
    try:
        return round(max(0.0, min(100.0, float(value))), 8)
    except (TypeError, ValueError):
        return 0.0


__all__ = ["OptionsIncomeCertificationAdapter", "adapt_options_income_certification"]
