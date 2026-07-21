"""Token lifecycle metadata and refresh planning; no network transport."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum


class TokenHealth(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    ROTATING = "ROTATING"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class TokenLifecycleMetadata:
    vcid: str
    health: TokenHealth
    created: str
    expiry: str | None
    last_refresh: str | None = None
    rotation_due: str | None = None
    validation_history: tuple[dict, ...] = ()
    refresh_attempted: bool = False
    token_values_returned: bool = False

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["health"] = self.health.value
        return payload


class TokenRefreshPlanner:
    def assess(self, metadata: TokenLifecycleMetadata, *, now: datetime | None = None) -> dict:
        current = now or datetime.now(timezone.utc)
        expiry = datetime.fromisoformat(metadata.expiry.replace("Z", "+00:00")) if metadata.expiry else None
        expired = bool(expiry and current >= expiry)
        due = bool(expiry and current >= expiry - timedelta(minutes=10))
        return {
            "vcid": metadata.vcid,
            "health": TokenHealth.EXPIRED.value if expired else metadata.health.value,
            "refresh_required": due,
            "refresh_allowed": False,
            "network_call_performed": False,
            "token_values_returned": False,
            "execution_allowed": False,
        }

    def mark_revoked(self, metadata: TokenLifecycleMetadata) -> TokenLifecycleMetadata:
        return replace(metadata, health=TokenHealth.REVOKED)


__all__ = ["TokenHealth", "TokenLifecycleMetadata", "TokenRefreshPlanner"]
