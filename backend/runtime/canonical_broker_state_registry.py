from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


CLASS_LIVE_ONLY = "LIVE_ONLY"
CLASS_PRACTICE_ONLY = "PRACTICE_ONLY"
CLASS_TEST_ONLY = "TEST_ONLY"
CLASS_SHARED = "SHARED"
CLASS_DEPRECATED = "DEPRECATED"
CLASS_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class EnvironmentVariableClassification:
    variable_name: str
    classification: str
    source_file: str
    source_layer: str
    reason: str
    current_mode: str
    severity: str = "INFO"
    present: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "variable_name": self.variable_name,
            "classification": self.classification,
            "source_file": self.source_file,
            "source_layer": self.source_layer,
            "reason": self.reason,
            "current_mode": self.current_mode,
            "severity": self.severity,
            "present": self.present,
            "value_redacted": True,
        }


COINBASE_ENV_REGISTRY: dict[str, tuple[str, str, str]] = {
    "COINBASE_CDP_KEY_NAME": (CLASS_LIVE_ONLY, "backend/app/brokers/credential_loader.py", "credential_loader"),
    "COINBASE_KEY_NAME": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader"),
    "COINBASE_API_KEY": (CLASS_DEPRECATED, "backend/app/brokers/credential_loader.py", "legacy_credential_loader"),
    "COINBASE_CDP_PRIVATE_KEY": (CLASS_LIVE_ONLY, "backend/app/brokers/credential_loader.py", "credential_loader"),
    "COINBASE_PRIVATE_KEY": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader"),
    "COINBASE_API_SECRET": (CLASS_DEPRECATED, "dashboard/runtime/broker_credential_check.py", "legacy_credential_loader"),
    "COINBASE_CDP_PRIVATE_KEY_PATH": (CLASS_LIVE_ONLY, "backend/app/brokers/credential_loader.py", "credential_loader"),
    "COINBASE_PRIVATE_KEY_PATH": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader"),
    "COINBASE_KEY_FILE": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader"),
    "COINBASE_KEY_JSON_PATH": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader"),
    "COINBASE_KEY_JSON": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader"),
    "COINBASE_BASE_URL": (CLASS_LIVE_ONLY, "backend/runtime/coinbase_authentication_trace.py", "endpoint_alignment"),
    "COINBASE_API_URL": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "endpoint_alignment"),
    "COINBASE_REST_URL": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "endpoint_alignment"),
    "COINBASE_API_PERMISSIONS": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "permission_trace"),
    "COINBASE_SCOPES": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "permission_trace"),
    "COINBASE_CDP_PERMISSIONS": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "permission_trace"),
    "COINBASE_AUTH_TIMESTAMP": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "clock_skew_trace"),
    "COINBASE_JWT_TIMESTAMP": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "clock_skew_trace"),
    "COINBASE_ENABLE_LIVE_ORDERS": (CLASS_LIVE_ONLY, "backend/app/brokers/credential_loader.py", "live_order_gate"),
    "COINBASE_ENABLED": (CLASS_SHARED, "dashboard/runtime/broker_credential_check.py", "runtime_config"),
    "COINBASE_MAX_LIVE_ORDER_USD": (CLASS_DEPRECATED, "backend/config/order_limit_config.py", "legacy_display_metadata"),
    "COINBASE_TEST_ORDER_USD": (CLASS_TEST_ONLY, ".env.practice", "practice_test_config"),
}


def classify_coinbase_environment(env: Mapping[str, Any] | None = None, *, mode: str = "live") -> dict[str, Any]:
    source = env if isinstance(env, Mapping) else {}
    mode_key = str(mode or "live").strip().lower()
    findings: list[dict[str, Any]] = []
    contamination_keys: list[str] = []
    for key in sorted(k for k in source if str(k).startswith("COINBASE")):
        value = source.get(key)
        present = value not in (None, "")
        classification, source_file, source_layer = COINBASE_ENV_REGISTRY.get(str(key), (CLASS_UNKNOWN, "UNKNOWN", "UNKNOWN"))
        reason = "registered_coinbase_runtime_variable" if classification != CLASS_UNKNOWN else "unregistered_coinbase_runtime_variable"
        severity = "INFO"
        if mode_key == "live" and present and classification in {CLASS_PRACTICE_ONLY, CLASS_TEST_ONLY}:
            severity = "ERROR"
            reason = "test_or_practice_variable_present_in_live_mode"
            contamination_keys.append(str(key))
        elif mode_key == "live" and present and classification == CLASS_DEPRECATED:
            severity = "WARNING"
            reason = "deprecated_or_display_only_metadata"
        findings.append(
            EnvironmentVariableClassification(
                variable_name=str(key),
                classification=classification,
                source_file=source_file,
                source_layer=source_layer,
                reason=reason,
                current_mode=mode_key,
                severity=severity,
                present=present,
            ).as_dict()
        )
    return {
        "broker": "COINBASE",
        "mode": mode_key,
        "status": "FAIL" if contamination_keys else "PASS",
        "contamination_keys": contamination_keys,
        "findings": findings,
        "secrets_redacted": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


__all__ = [
    "CLASS_DEPRECATED",
    "CLASS_LIVE_ONLY",
    "CLASS_PRACTICE_ONLY",
    "CLASS_SHARED",
    "CLASS_TEST_ONLY",
    "CLASS_UNKNOWN",
    "COINBASE_ENV_REGISTRY",
    "EnvironmentVariableClassification",
    "classify_coinbase_environment",
]
