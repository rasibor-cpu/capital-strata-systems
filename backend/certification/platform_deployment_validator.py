from __future__ import annotations

from typing import Any, Mapping

from backend.certification.platform_live_disable_verification import SAFE_FLAGS


PAYLOAD_VERSION = "css.rc1_final.deployment.v1"


class PlatformDeploymentValidator:
    def validate(self, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(evidence or {})
        checks = {
            "deployment_package": bool(payload.get("deployment_package", True)),
            "rollback": bool(payload.get("rollback", True)),
            "operator_guidance": bool(payload.get("operator_guidance", True)),
            "release_notes": bool(payload.get("release_notes", True)),
            "production_config_unchanged": bool(payload.get("production_config_unchanged", True)),
            "live_disabled": bool(payload.get("live_disabled", True)),
        }
        failures = [key for key, passed in checks.items() if not passed]
        return {
            "payload_version": PAYLOAD_VERSION,
            "status": "FAIL" if failures else "PASS",
            "checks": checks,
            "failures": failures,
            "production_deployment_authorized": False,
            "live_trading_authorized": False,
            **SAFE_FLAGS,
        }


def validate_platform_deployment(evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return PlatformDeploymentValidator().validate(evidence)


__all__ = ["PAYLOAD_VERSION", "PlatformDeploymentValidator", "validate_platform_deployment"]
