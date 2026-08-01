"""Phase 185A — immutable live market microstructure snapshot contract.

No broker I/O. Snapshots are constructed by certified providers only.
Default posture is NOT_AVAILABLE / UNKNOWN (fail-closed).

Phase 185A-R1 — schema_id / schema_version for auditability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional

from backend.app.market.status import (
    FRAMEWORK_VERSION,
    FRESHNESS_NOT_AVAILABLE,
    QUALITY_UNKNOWN,
    SCHEMA_ID_LIVE_MARKET_SNAPSHOT,
    SCHEMA_VERSION_185A,
    STATUS_AVAILABLE,
    STATUS_NOT_AVAILABLE,
    STATUS_UNKNOWN,
    UNAVAILABLE_PROVIDER_NAME,
    UNAVAILABLE_PROVIDER_VERSION,
)


class LiveMarketSnapshotError(ValueError):
    """Raised when a live market snapshot is constructed unsafely."""


@dataclass(frozen=True)
class LiveMarketSnapshot:
    """Immutable market microstructure snapshot for AntiBleed / gates / reporting."""

    bid: Optional[float]
    ask: Optional[float]
    mid: Optional[float]
    spread: Optional[float]
    spread_bps: Optional[float]
    estimated_slippage: Optional[float]
    estimated_fee: Optional[float]
    currency: Optional[str]
    quote_timestamp: Optional[str]
    provider: str
    provider_version: str
    quality: str
    freshness: str
    status: str
    schema_id: str = SCHEMA_ID_LIVE_MARKET_SNAPSHOT
    schema_version: str = SCHEMA_VERSION_185A
    evidence_hash: str = ""
    fail_reason: str = ""

    def __post_init__(self) -> None:
        if not str(self.provider or "").strip():
            raise LiveMarketSnapshotError("provider is required")
        if not str(self.provider_version or "").strip():
            raise LiveMarketSnapshotError("provider_version is required")
        if not str(self.quality or "").strip():
            raise LiveMarketSnapshotError("quality is required")
        if not str(self.freshness or "").strip():
            raise LiveMarketSnapshotError("freshness is required")
        if not str(self.status or "").strip():
            raise LiveMarketSnapshotError("status is required")
        if not str(self.schema_id or "").strip():
            raise LiveMarketSnapshotError("schema_id is required")
        if not str(self.schema_version or "").strip():
            raise LiveMarketSnapshotError("schema_version is required")
        if self.status == STATUS_AVAILABLE:
            for name in ("bid", "ask", "mid", "spread", "spread_bps"):
                value = getattr(self, name)
                if value is None:
                    raise LiveMarketSnapshotError(
                        f"AVAILABLE snapshot requires {name}"
                    )

    def is_usable(self) -> bool:
        """True only when status is AVAILABLE and quality is not UNKNOWN."""
        return self.status == STATUS_AVAILABLE and self.quality != QUALITY_UNKNOWN

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def identity(self) -> Mapping[str, str]:
        """Audit-safe identity (no secrets, no execution authority)."""
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "provider_name": self.provider,
            "provider_version": self.provider_version,
            "provider": self.provider,
            "quality": self.quality,
            "freshness": self.freshness,
            "status": self.status,
            "framework_version": FRAMEWORK_VERSION,
        }

    @classmethod
    def not_available(
        cls,
        *,
        provider: str = UNAVAILABLE_PROVIDER_NAME,
        provider_version: str = UNAVAILABLE_PROVIDER_VERSION,
        reason: str = STATUS_NOT_AVAILABLE,
    ) -> "LiveMarketSnapshot":
        del reason  # reserved for future audit payloads; status carries posture
        return cls(
            bid=None,
            ask=None,
            mid=None,
            spread=None,
            spread_bps=None,
            estimated_slippage=None,
            estimated_fee=None,
            currency=None,
            quote_timestamp=None,
            provider=provider,
            provider_version=provider_version,
            quality=QUALITY_UNKNOWN,
            freshness=FRESHNESS_NOT_AVAILABLE,
            status=STATUS_NOT_AVAILABLE,
            schema_id=SCHEMA_ID_LIVE_MARKET_SNAPSHOT,
            schema_version=SCHEMA_VERSION_185A,
        )

    @classmethod
    def unknown(
        cls,
        *,
        provider: str = UNAVAILABLE_PROVIDER_NAME,
        provider_version: str = UNAVAILABLE_PROVIDER_VERSION,
    ) -> "LiveMarketSnapshot":
        return cls(
            bid=None,
            ask=None,
            mid=None,
            spread=None,
            spread_bps=None,
            estimated_slippage=None,
            estimated_fee=None,
            currency=None,
            quote_timestamp=None,
            provider=provider,
            provider_version=provider_version,
            quality=QUALITY_UNKNOWN,
            freshness=STATUS_UNKNOWN,
            status=STATUS_UNKNOWN,
            schema_id=SCHEMA_ID_LIVE_MARKET_SNAPSHOT,
            schema_version=SCHEMA_VERSION_185A,
        )


__all__ = [
    "LiveMarketSnapshot",
    "LiveMarketSnapshotError",
]
