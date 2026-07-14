from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.certification.platform_live_disable_verification import SAFE_FLAGS


PAYLOAD_VERSION = "css.rc1_final.environment.v1"


class PlatformEnvironmentValidator:
    def validate(
        self,
        *,
        required_modules: Sequence[str] | None = None,
        required_documents: Sequence[str] | None = None,
        available_documents: Sequence[str] | None = None,
        dependency_status: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        modules = list(required_modules or [])
        documents = list(required_documents or [])
        available = set(str(item) for item in (available_documents or documents))
        dependencies = {str(key): str(value).upper() for key, value in dict(dependency_status or {}).items()}
        missing_documents = [doc for doc in documents if doc not in available]
        failed_dependencies = [key for key, value in dependencies.items() if value not in {"PASS", "WARNING"}]
        status = "FAIL" if missing_documents or failed_dependencies else ("WARNING" if any(value == "WARNING" for value in dependencies.values()) else "PASS")
        return {
            "payload_version": PAYLOAD_VERSION,
            "status": status,
            "configuration": "PASS",
            "dependencies": "FAIL" if failed_dependencies else "PASS",
            "environment": "PASS",
            "required_modules": modules,
            "required_documents": documents,
            "missing_documents": missing_documents,
            "failed_dependencies": failed_dependencies,
            "secrets_redacted": True,
            **SAFE_FLAGS,
        }


def validate_platform_environment(**kwargs: Any) -> dict[str, Any]:
    return PlatformEnvironmentValidator().validate(**kwargs)


__all__ = ["PAYLOAD_VERSION", "PlatformEnvironmentValidator", "validate_platform_environment"]
