from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from math import isfinite
from typing import Any

from dashboard.mission_control.safety import validate_no_secret_payload


def deterministic_json(payload: Mapping[str, Any], *, indent: int | None = None) -> str:
    safe = safe_serialize(payload)
    return json.dumps(safe, sort_keys=True, separators=None if indent else (",", ":"), indent=indent)


def state_hash(payload: Mapping[str, Any]) -> str:
    encoded = deterministic_json(payload)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def safe_serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(key): safe_serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe_serialize(item) for item in value]
    if isinstance(value, float):
        return value if isfinite(value) else "UNAVAILABLE"
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def validate_serializable_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    try:
        deterministic_json(payload)
    except (TypeError, ValueError) as exc:
        reasons.append(f"serialization_error:{type(exc).__name__}")
    secrets_ok, secret_reasons = validate_no_secret_payload(payload)
    if not secrets_ok:
        reasons.extend(secret_reasons)
    return {
        "valid": not reasons,
        "status": "PASS" if not reasons else "FAIL_CLOSED",
        "reasons": sorted(set(reasons)),
    }


__all__ = [
    "deterministic_json",
    "safe_serialize",
    "state_hash",
    "validate_serializable_payload",
]
