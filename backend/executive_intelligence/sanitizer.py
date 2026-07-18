"""Secret sanitizer for ExecutiveMorningBrief payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.executive_intelligence.constants import SECRET_KEY_TOKENS


SAFE_SECRET_PLACEHOLDERS = {
    "PRESENT",
    "ABSENT",
    "CONFIGURED",
    "NOT_CONFIGURED",
    "REDACTED",
    "UNAVAILABLE",
    "TRUE",
    "FALSE",
}


def sanitize_payload(payload: Any) -> Any:
    """Return a deep-copied payload with secret-bearing keys redacted."""
    return _sanitize(payload)


def contains_secrets(payload: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    _scan(payload, path="", reasons=reasons)
    return bool(reasons), sorted(set(reasons))


def _sanitize(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            key_text = str(key).lower()
            if any(token in key_text for token in SECRET_KEY_TOKENS):
                label = str(value).upper() if value is not None else "REDACTED"
                out[str(key)] = label if label in SAFE_SECRET_PLACEHOLDERS else "REDACTED"
            else:
                out[str(key)] = _sanitize(value)
        return out
    if isinstance(payload, list):
        return [_sanitize(item) for item in payload]
    if isinstance(payload, tuple):
        return [_sanitize(item) for item in payload]
    return payload


def _scan(payload: Any, *, path: str, reasons: list[str]) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key).lower()
            next_path = f"{path}.{key}" if path else str(key)
            if any(token in key_text for token in SECRET_KEY_TOKENS):
                label = str(value).upper() if value is not None else ""
                if label not in SAFE_SECRET_PLACEHOLDERS:
                    reasons.append(f"secret_field:{next_path}")
            _scan(value, path=next_path, reasons=reasons)
    elif isinstance(payload, (list, tuple)):
        for idx, item in enumerate(payload):
            _scan(item, path=f"{path}[{idx}]", reasons=reasons)
