from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


PAYLOAD_VERSION = "css.rc1_final.live_disable.v1"
SAFE_FLAGS = {
    "paper_only": True,
    "advisory_only": True,
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
}
FORBIDDEN_KEYS = {
    "submit_order",
    "place_order",
    "cancel_order",
    "order_routing",
    "execution_authority",
    "broker_write",
    "credential_mutation",
    "authentication_mutation",
    "enable_live",
    "arm_execution",
}
SENSITIVE_KEY_PARTS = ("credential", "token", "private_key", "pem", "jwt", "api_key", "password", "secret")


class PlatformLiveDisableVerificationError(ValueError):
    """Raised when platform-wide live-disable verification cannot be completed."""


@dataclass(frozen=True)
class PlatformLiveDisableVerification:
    payload_version: str
    status: str
    failures: tuple[str, ...]
    checked_payloads: int
    paper_only: bool = True
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_version": self.payload_version,
            "status": self.status,
            "failures": list(self.failures),
            "checked_payloads": self.checked_payloads,
            **SAFE_FLAGS,
        }


class PlatformLiveDisableVerifier:
    def verify(self, payloads: Sequence[Mapping[str, Any]] | None = None) -> PlatformLiveDisableVerification:
        rows = [dict(row) for row in (payloads or [])]
        failures: list[str] = []
        for index, payload in enumerate(rows):
            _scan(payload, failures, path=f"payload[{index}]")
        return PlatformLiveDisableVerification(
            payload_version=PAYLOAD_VERSION,
            status="FAIL" if failures else "PASS",
            failures=tuple(sorted(set(failures))),
            checked_payloads=len(rows),
        )


def verify_platform_live_disabled(payloads: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    return PlatformLiveDisableVerifier().verify(payloads).to_dict()


def assert_platform_safe(payload: Mapping[str, Any]) -> None:
    failures: list[str] = []
    _scan(dict(payload), failures, path="payload")
    if failures:
        raise PlatformLiveDisableVerificationError("; ".join(sorted(set(failures))))


def _scan(value: Any, failures: list[str], *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, expected in SAFE_FLAGS.items():
            if key in value and value.get(key) is not expected:
                failures.append(f"{path}.{key} unsafe")
        mode = str(value.get("mode", "")).upper()
        if mode and mode not in {"PAPER", "READ_ONLY", "ADVISORY"}:
            failures.append(f"{path}.mode unsafe")
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_KEYS and item:
                failures.append(f"{path}.{key} forbidden")
            if lowered in {"secrets_redacted", "sensitive_fields_excluded", "secrets_present"}:
                pass
            elif any(part in lowered for part in SENSITIVE_KEY_PARTS) and item:
                failures.append(f"{path}.{key} sensitive")
            if lowered in {"order_capable", "broker_write_capable", "supports_order_submission"} and item is True:
                failures.append(f"{path}.{key} forbidden")
            _scan(item, failures, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            _scan(item, failures, path=f"{path}[{index}]")


__all__ = [
    "FORBIDDEN_KEYS",
    "PAYLOAD_VERSION",
    "SAFE_FLAGS",
    "PlatformLiveDisableVerification",
    "PlatformLiveDisableVerificationError",
    "PlatformLiveDisableVerifier",
    "assert_platform_safe",
    "verify_platform_live_disabled",
]
