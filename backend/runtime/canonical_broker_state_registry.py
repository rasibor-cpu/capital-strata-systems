from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


CLASS_LIVE = "LIVE"
CLASS_PRACTICE = "PRACTICE"
CLASS_TEST = "TEST"
CLASS_SANDBOX = "SANDBOX"
CLASS_SHARED = "SHARED"
CLASS_DEPRECATED = "DEPRECATED"
CLASS_UNKNOWN = "UNKNOWN"
CLASS_LIVE_ONLY = CLASS_LIVE
CLASS_PRACTICE_ONLY = CLASS_PRACTICE
CLASS_TEST_ONLY = CLASS_TEST


@dataclass(frozen=True)
class EnvironmentVariableClassification:
    variable_name: str
    classification: str
    source_file: str
    source_layer: str
    consumer: str
    purpose: str
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
            "consumer": self.consumer,
            "purpose": self.purpose,
            "reason": self.reason,
            "current_mode": self.current_mode,
            "severity": self.severity,
            "present": self.present,
            "value_redacted": True,
        }


COINBASE_ENV_REGISTRY: dict[str, tuple[str, str, str, str, str]] = {
    "COINBASE_CDP_KEY_NAME": (CLASS_LIVE, "backend/app/brokers/credential_loader.py", "credential_loader", "coinbase_bootstrap", "live credential key name"),
    "COINBASE_KEY_NAME": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader", "coinbase_bootstrap", "credential key name compatibility"),
    "COINBASE_API_KEY": (CLASS_DEPRECATED, "backend/app/brokers/credential_loader.py", "legacy_credential_loader", "coinbase_bootstrap", "legacy credential key"),
    "COINBASE_CDP_PRIVATE_KEY": (CLASS_LIVE, "backend/app/brokers/credential_loader.py", "credential_loader", "coinbase_bootstrap", "live private key material"),
    "COINBASE_PRIVATE_KEY": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader", "coinbase_bootstrap", "private key compatibility"),
    "COINBASE_API_SECRET": (CLASS_DEPRECATED, "dashboard/runtime/broker_credential_check.py", "legacy_credential_loader", "broker_diagnostics", "legacy secret compatibility"),
    "COINBASE_CDP_PRIVATE_KEY_PATH": (CLASS_LIVE, "backend/app/brokers/credential_loader.py", "credential_loader", "coinbase_bootstrap", "live private key path"),
    "COINBASE_PRIVATE_KEY_PATH": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader", "coinbase_bootstrap", "private key path compatibility"),
    "COINBASE_KEY_FILE": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader", "coinbase_bootstrap", "json key file"),
    "COINBASE_KEY_JSON_PATH": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader", "coinbase_bootstrap", "json key path"),
    "COINBASE_KEY_JSON": (CLASS_SHARED, "backend/app/brokers/credential_loader.py", "credential_loader", "coinbase_bootstrap", "inline json key material"),
    "COINBASE_BASE_URL": (CLASS_LIVE, "backend/runtime/coinbase_authentication_trace.py", "endpoint_alignment", "coinbase_authentication_trace", "configured REST endpoint"),
    "COINBASE_API_URL": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "endpoint_alignment", "coinbase_authentication_trace", "REST endpoint compatibility"),
    "COINBASE_REST_URL": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "endpoint_alignment", "coinbase_authentication_trace", "REST endpoint compatibility"),
    "COINBASE_SANDBOX_URL": (CLASS_SANDBOX, ".env.practice", "sandbox_endpoint", "coinbase_authentication_trace", "sandbox endpoint"),
    "COINBASE_API_PERMISSIONS": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "permission_trace", "coinbase_authentication_trace", "declared API permissions"),
    "COINBASE_SCOPES": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "permission_trace", "coinbase_authentication_trace", "declared API scopes"),
    "COINBASE_CDP_PERMISSIONS": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "permission_trace", "coinbase_authentication_trace", "declared CDP permissions"),
    "COINBASE_AUTH_TIMESTAMP": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "clock_skew_trace", "coinbase_authentication_trace", "authentication timestamp"),
    "COINBASE_JWT_TIMESTAMP": (CLASS_SHARED, "backend/runtime/coinbase_authentication_trace.py", "clock_skew_trace", "coinbase_authentication_trace", "JWT timestamp"),
    "COINBASE_ENABLE_LIVE_ORDERS": (CLASS_LIVE, "backend/app/brokers/credential_loader.py", "live_order_gate", "execution_firewall", "live execution safety gate"),
    "COINBASE_ENABLED": (CLASS_SHARED, "dashboard/runtime/broker_credential_check.py", "runtime_config", "broker_diagnostics", "broker enabled flag"),
    "COINBASE_MAX_LIVE_ORDER_USD": (CLASS_DEPRECATED, "backend/config/order_limit_config.py", "legacy_display_metadata", "order_limit_config", "display-only legacy order limit metadata"),
    "COINBASE_TEST_ORDER_USD": (CLASS_TEST, ".env.practice", "practice_test_config", "paper_broker", "practice test order notional"),
}

LEGACY_EXECUTION_VARIABLES = frozenset(
    {
        "COINBASE_LEGACY_ENABLE_LIVE_ORDERS",
        "COINBASE_LEGACY_EXECUTION_ENABLED",
        "COINBASE_LIVE_TRADING_ENABLED_LEGACY",
    }
)


def classify_coinbase_environment(env: Mapping[str, Any] | None = None, *, mode: str = "live") -> dict[str, Any]:
    source = env if isinstance(env, Mapping) else {}
    mode_key = str(mode or "live").strip().lower()
    findings: list[dict[str, Any]] = []
    contamination_keys: list[str] = []
    for key in sorted(k for k in source if str(k).startswith("COINBASE")):
        value = source.get(key)
        present = value not in (None, "")
        classification, source_file, source_layer, consumer, purpose = COINBASE_ENV_REGISTRY.get(
            str(key), (CLASS_UNKNOWN, "UNKNOWN", "UNKNOWN", "UNKNOWN", "unregistered Coinbase variable")
        )
        reason = "registered_coinbase_runtime_variable" if classification != CLASS_UNKNOWN else "unregistered_coinbase_runtime_variable"
        severity = "INFO"
        value_text = str(value or "").strip().lower()
        if mode_key == "live" and present and classification in {CLASS_PRACTICE, CLASS_TEST, CLASS_SANDBOX}:
            severity = "ERROR"
            reason = "non_live_variable_present_in_live_mode"
            contamination_keys.append(str(key))
        elif mode_key == "live" and present and str(key) in LEGACY_EXECUTION_VARIABLES and value_text in {"1", "true", "yes", "on", "enabled", "armed"}:
            severity = "ERROR"
            reason = "legacy_execution_variable_truthy_in_live_mode"
            contamination_keys.append(str(key))
        elif mode_key == "live" and present and "sandbox" in value_text:
            severity = "ERROR"
            reason = "sandbox_endpoint_selected_in_live_mode"
            contamination_keys.append(str(key))
        elif mode_key == "live" and present and "demo" in value_text:
            severity = "ERROR"
            reason = "demo_endpoint_selected_in_live_mode"
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
                consumer=consumer,
                purpose=purpose,
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
    "CLASS_LIVE",
    "CLASS_LIVE_ONLY",
    "CLASS_PRACTICE",
    "CLASS_PRACTICE_ONLY",
    "CLASS_SANDBOX",
    "CLASS_SHARED",
    "CLASS_TEST",
    "CLASS_TEST_ONLY",
    "CLASS_UNKNOWN",
    "COINBASE_ENV_REGISTRY",
    "EnvironmentVariableClassification",
    "classify_coinbase_environment",
]
