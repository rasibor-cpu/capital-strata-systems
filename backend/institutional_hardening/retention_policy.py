from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetentionPolicy:
    audit_days: int = 365
    replay_days: int = 180
    alert_days: int = 180
    release_summary_days: int = 730
    max_archive_bytes: int = 2_000_000_000

    def __post_init__(self) -> None:
        if min(self.audit_days, self.replay_days, self.alert_days, self.release_summary_days) <= 0:
            raise ValueError("retention days must be positive")
        if self.max_archive_bytes <= 0:
            raise ValueError("max archive bytes must be positive")


SENSITIVE_PARTS = ("token", "secret", "password", "authorization", "private_key", "api_key")


def redact_export(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            k = str(key)
            out[k] = "REDACTED" if any(part in k.lower() for part in SENSITIVE_PARTS) else redact_export(item)
        return out
    if isinstance(value, list):
        return [redact_export(item) for item in value]
    return value
