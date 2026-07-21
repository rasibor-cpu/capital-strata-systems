from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
import re
from typing import Any


SAFE_FLAGS = {
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
    "advisory_only": True,
}
SECRET_TOKENS = ("secret", "token", "private", "credential", "password", "pem", "jwt", "api_key", "apikey", "signature")
ORDER_CAPABLE_TOKENS = ("submit_order", "place_order", "cancel_order", "execute_trade", "enable_live", "arm_execution")
_CREDENTIAL_METADATA_KEYS = {
    "credential_type",
    "credential_name",
    "credential_id",
    "credential_count",
    "secret_type",
    "secret_uuid",
    "secret_count",
}
_METADATA_LABEL = re.compile(r"^[A-Z0-9_.:/-]{1,128}$", re.I)


def mission_control_safety_payload(source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(source or {})
    reasons = _safety_reasons(payload)
    status = "PASS" if not reasons else "FAIL_CLOSED"
    return {
        **SAFE_FLAGS,
        "safety_status": status,
        "fail_closed": bool(reasons),
        "reasons": reasons,
        "read_only": True,
        "control_surface": "DISPLAY_ONLY",
        "live_execution_certification": "NOT_GRANTED",
    }


def validate_no_secret_payload(payload: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    _scan_secret_payload(payload, path="", reasons=reasons)
    return not reasons, sorted(set(reasons))


def validate_no_execution_controls(payload: Any) -> tuple[bool, list[str]]:
    text = str(payload).lower()
    reasons = [token for token in ORDER_CAPABLE_TOKENS if token in text]
    return not reasons, reasons


def _safety_reasons(payload: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if payload.get("execution_allowed") is not False:
        reasons.append("execution_allowed_not_false")
    if payload.get("live_trading_blocked") is not True:
        reasons.append("live_trading_blocked_not_true")
    if payload.get("broker_execution_armed") is not False:
        reasons.append("broker_execution_armed_not_false")
    if payload.get("advisory_only") is not True:
        reasons.append("advisory_only_not_true")
    ok, secret_reasons = validate_no_secret_payload(payload)
    if not ok:
        reasons.extend(secret_reasons)
    return sorted(set(reasons))


def normalize_metric(value: Any) -> Any:
    if value in (None, "", "DATA UNAVAILABLE", "UNAVAILABLE"):
        return "UNAVAILABLE"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if not isfinite(number):
        return "UNAVAILABLE"
    return round(number, 6)


def _scan_secret_payload(payload: Any, *, path: str, reasons: list[str]) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key).lower()
            next_path = f"{path}.{key}" if path else str(key)
            if any(token in key_text for token in SECRET_TOKENS):
                if key_text in _CREDENTIAL_METADATA_KEYS and (
                    isinstance(value, int)
                    or (isinstance(value, str) and _METADATA_LABEL.fullmatch(value))
                ):
                    _scan_secret_payload(value, path=next_path, reasons=reasons)
                    continue
                safe_label = str(value).upper() in {
                    "PRESENT",
                    "MISSING",
                    "PASS",
                    "FAIL",
                    "READY",
                    "UNKNOWN",
                    "UNAVAILABLE",
                    "DATA UNAVAILABLE",
                    "NOT_AVAILABLE",
                    "NOT_REQUIRED",
                    "DISABLED_MC001",
                    "READ_ONLY_MC001",
                    "NOT_GRANTED",
                }
                if value not in (None, "", False, "REDACTED", "redacted", "DATA UNAVAILABLE", "UNAVAILABLE"):
                    if not isinstance(value, (bool, Mapping, list, tuple)) and not safe_label:
                        reasons.append(f"secret_bearing_field:{next_path}")
            _scan_secret_payload(value, path=next_path, reasons=reasons)
    elif isinstance(payload, (list, tuple)):
        for index, item in enumerate(payload):
            _scan_secret_payload(item, path=f"{path}[{index}]", reasons=reasons)


__all__ = [
    "SAFE_FLAGS",
    "mission_control_safety_payload",
    "normalize_metric",
    "validate_no_execution_controls",
    "validate_no_secret_payload",
]
