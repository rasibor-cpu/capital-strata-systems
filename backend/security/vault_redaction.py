"""Deep, fail-closed redaction for credential-bearing payloads."""

from __future__ import annotations

import re
from typing import Any, Mapping

REDACTED = "[REDACTED]"
_SENSITIVE_KEY = re.compile(
    r"(api[_-]?key|oauth[_-]?code|refresh[_-]?token|access[_-]?token|client[_-]?secret|"
    r"private[_-]?key|password|passphrase|certificate|account[_-]?(number|id)|"
    r"authorization|cookie|secret)",
    re.IGNORECASE,
)
_INLINE = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"-----BEGIN [^-]+-----[\s\S]*?-----END [^-]+-----"),
    re.compile(r"(?i)(client_secret|refresh_token|access_token|api_key|password)=([^&\s]+)"),
)
_METADATA_CONTAINER_KEYS = {
    "enterprise_secrets",
    "secret_inventory",
    "secret_authority",
    "orphaned_secrets",
}
_METADATA_LABEL_KEYS = {"secret_type", "secret_uuid", "secret_count"}


def redact_text(value: Any) -> str:
    text = str(value)
    for pattern in _INLINE:
        text = pattern.sub(REDACTED, text)
    return text


def redact_value(value: Any, *, key: str | None = None) -> Any:
    normalized_key = str(key or "").lower()
    if normalized_key in _METADATA_CONTAINER_KEYS and isinstance(value, (Mapping, list, tuple)):
        return redact_value(value)
    if normalized_key in _METADATA_LABEL_KEYS and isinstance(value, (str, int)):
        return value
    if key and _SENSITIVE_KEY.search(str(key)):
        if isinstance(value, bool):
            return value
        return REDACTED
    if isinstance(value, Mapping):
        return {str(k): redact_value(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact_value(item) for item in value]
    if isinstance(value, bytes):
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    return value


def contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            _SENSITIVE_KEY.search(str(key)) is not None or contains_sensitive_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set)):
        return any(contains_sensitive_key(item) for item in value)
    return False


__all__ = ["REDACTED", "contains_sensitive_key", "redact_text", "redact_value"]
