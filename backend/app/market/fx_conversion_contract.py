"""Phase 185A — deterministic FX conversion contract (no online lookup).

Interface / immutable quote only. UNKNOWN and NOT_AVAILABLE remain fail-closed.

Phase 185A-R1 — schema_id / schema_version for auditability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional

from backend.app.market.status import (
    FRAMEWORK_VERSION,
    QUALITY_UNKNOWN,
    SCHEMA_ID_FX_CONVERSION,
    SCHEMA_VERSION_185A,
    STATUS_AVAILABLE,
    STATUS_NOT_AVAILABLE,
    STATUS_UNKNOWN,
    UNAVAILABLE_PROVIDER_NAME,
    UNAVAILABLE_PROVIDER_VERSION,
)


class FXConversionError(ValueError):
    """Raised when FX conversion construction or use fails closed."""


@dataclass(frozen=True)
class FXConversionQuote:
    """Immutable FX conversion quote. Deterministic; never fetched online here."""

    base_currency: str
    quote_currency: str
    rate: Optional[float]
    timestamp: Optional[str]
    provider: str
    provider_version: str
    quality: str
    status: str
    schema_id: str = SCHEMA_ID_FX_CONVERSION
    schema_version: str = SCHEMA_VERSION_185A
    conversion_path: tuple[str, ...] = ()
    path_type: str = "NONE"
    contributing_rate_ids: tuple[str, ...] = ()
    contributing_provider_ids: tuple[str, ...] = ()
    contributing_timestamps: tuple[str, ...] = ()
    evidence_hash: str = ""
    fail_reason: str = ""

    def __post_init__(self) -> None:
        if not str(self.base_currency or "").strip():
            raise FXConversionError("base_currency is required")
        if not str(self.quote_currency or "").strip():
            raise FXConversionError("quote_currency is required")
        if not str(self.provider or "").strip():
            raise FXConversionError("provider is required")
        if not str(self.provider_version or "").strip():
            raise FXConversionError("provider_version is required")
        if not str(self.quality or "").strip():
            raise FXConversionError("quality is required")
        if not str(self.status or "").strip():
            raise FXConversionError("status is required")
        if not str(self.schema_id or "").strip():
            raise FXConversionError("schema_id is required")
        if not str(self.schema_version or "").strip():
            raise FXConversionError("schema_version is required")
        if self.status == STATUS_AVAILABLE:
            if self.rate is None or not isinstance(self.rate, (int, float)):
                raise FXConversionError("AVAILABLE quote requires finite rate")
            if float(self.rate) <= 0.0:
                raise FXConversionError("AVAILABLE quote rate must be positive")

    def is_usable(self) -> bool:
        return (
            self.status == STATUS_AVAILABLE
            and self.quality != QUALITY_UNKNOWN
            and self.rate is not None
            and float(self.rate) > 0.0
        )

    def convert(self, amount: float) -> Optional[float]:
        """Deterministic convert. Returns None when fail-closed."""
        if not self.is_usable():
            return None
        try:
            value = float(amount)
        except (TypeError, ValueError):
            return None
        if value != value:  # NaN
            return None
        return value * float(self.rate)

    def normalize_currency_pair(self) -> tuple[str, str]:
        """Return uppercased (base, quote). Fail-closed empty tokens raise."""
        base = str(self.base_currency).strip().upper()
        quote = str(self.quote_currency).strip().upper()
        if not base or not quote:
            raise FXConversionError("currency pair tokens must be non-empty")
        return base, quote

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def identity(self) -> Mapping[str, str]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "base_currency": str(self.base_currency).upper(),
            "quote_currency": str(self.quote_currency).upper(),
            "provider_name": self.provider,
            "provider_version": self.provider_version,
            "provider": self.provider,
            "quality": self.quality,
            "status": self.status,
            "path_type": self.path_type,
            "conversion_path": ",".join(self.conversion_path),
            "evidence_hash": self.evidence_hash,
            "framework_version": FRAMEWORK_VERSION,
        }

    @classmethod
    def not_available(
        cls,
        *,
        base_currency: str = "UNKNOWN",
        quote_currency: str = "UNKNOWN",
        provider: str = UNAVAILABLE_PROVIDER_NAME,
        provider_version: str = UNAVAILABLE_PROVIDER_VERSION,
    ) -> "FXConversionQuote":
        return cls(
            base_currency=base_currency,
            quote_currency=quote_currency,
            rate=None,
            timestamp=None,
            provider=provider,
            provider_version=provider_version,
            quality=QUALITY_UNKNOWN,
            status=STATUS_NOT_AVAILABLE,
            schema_id=SCHEMA_ID_FX_CONVERSION,
            schema_version=SCHEMA_VERSION_185A,
        )

    @classmethod
    def unknown(
        cls,
        *,
        base_currency: str = "UNKNOWN",
        quote_currency: str = "UNKNOWN",
        provider: str = UNAVAILABLE_PROVIDER_NAME,
        provider_version: str = UNAVAILABLE_PROVIDER_VERSION,
    ) -> "FXConversionQuote":
        return cls(
            base_currency=base_currency,
            quote_currency=quote_currency,
            rate=None,
            timestamp=None,
            provider=provider,
            provider_version=provider_version,
            quality=QUALITY_UNKNOWN,
            status=STATUS_UNKNOWN,
            schema_id=SCHEMA_ID_FX_CONVERSION,
            schema_version=SCHEMA_VERSION_185A,
        )


def normalize_currency_code(code: Any) -> Optional[str]:
    """Normalize a currency code. Returns None for missing/UNKNOWN (fail-closed)."""
    if code is None:
        return None
    token = str(code).strip().upper()
    if not token or token == STATUS_UNKNOWN:
        return None
    return token


__all__ = [
    "FXConversionQuote",
    "FXConversionError",
    "normalize_currency_code",
]
