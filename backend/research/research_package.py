from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping


SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "authorization",
    "private_key",
    "api_key",
    "credential",
)


def _is_utc(value: datetime) -> bool:
    return (
        value.tzinfo is not None
        and value.utcoffset() is not None
        and value.utcoffset() == timezone.utc.utcoffset(value)
    )


def _normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("non-finite Decimal is not exportable")
        return format(value, "f")
    if isinstance(value, datetime):
        if not _is_utc(value):
            raise ValueError("all exported datetimes must be timezone-aware UTC")
        return value.isoformat()
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key in sorted((str(k) for k in value.keys())):
            original = next(k for k in value.keys() if str(k) == key)
            if any(fragment in key.lower() for fragment in SENSITIVE_KEY_FRAGMENTS):
                out[key] = "REDACTED"
            else:
                out[key] = _normalize(value[original])
        return out
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return _normalize(vars(value))
    raise TypeError(f"unsupported research package value: {type(value).__name__}")


def build_research_package(
    *,
    package_id: str,
    generated_at_utc: datetime,
    sections: Mapping[str, Any],
) -> dict[str, Any]:
    if not package_id.strip():
        raise ValueError("package_id is required")
    if not _is_utc(generated_at_utc):
        raise ValueError("generated_at_utc must be timezone-aware UTC")
    if not sections:
        raise ValueError("at least one evidence section is required")

    normalized_sections = _normalize(sections)
    payload: dict[str, Any] = {
        "schema_version": "css.program_b.research_package.v1",
        "package_id": package_id,
        "generated_at_utc": generated_at_utc.isoformat(),
        "status": "RESEARCH_ONLY",
        "sections": normalized_sections,
        "safety": {
            "approved_for_live": False,
            "execution_allowed": False,
            "broker_execution_armed": False,
            "money_movement_authorized": False,
            "human_approval_required": True,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["package_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def package_to_json(package: Mapping[str, Any]) -> str:
    return json.dumps(package, sort_keys=True, indent=2) + "\n"
