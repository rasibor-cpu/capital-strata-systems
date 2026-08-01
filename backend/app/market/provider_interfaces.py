"""Phase 185A — market / FX / fee / slippage provider interfaces (no live I/O).

All default implementations return NOT_AVAILABLE until certified providers exist.

Phase 185A-R1 — immutable provider metadata on every interface implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol

from backend.app.market.fx_conversion_contract import FXConversionQuote
from backend.app.market.live_market_snapshot import LiveMarketSnapshot
from backend.app.market.status import (
    QUALITY_UNKNOWN,
    SCHEMA_VERSION_185A,
    STATUS_NOT_AVAILABLE,
    UNAVAILABLE_PROVIDER_NAME,
    UNAVAILABLE_PROVIDER_VERSION,
)


@dataclass(frozen=True)
class ProviderMetadata:
    """Immutable provider identity for diagnostics (no secrets / no authority)."""

    provider_name: str
    provider_version: str
    provider_status: str

    def as_dict(self) -> dict[str, str]:
        return {
            "provider_name": self.provider_name,
            "provider_version": self.provider_version,
            "provider_status": self.provider_status,
        }


UNAVAILABLE_PROVIDER_METADATA = ProviderMetadata(
    provider_name=UNAVAILABLE_PROVIDER_NAME,
    provider_version=UNAVAILABLE_PROVIDER_VERSION,
    provider_status=STATUS_NOT_AVAILABLE,
)


@dataclass(frozen=True)
class FeeEstimate:
    """Immutable fee estimate. NOT_AVAILABLE until a certified fee model exists."""

    fee_bps: Optional[float]
    fee_absolute: Optional[float]
    currency: Optional[str]
    provider: str
    provider_version: str
    quality: str
    status: str

    def is_usable(self) -> bool:
        return self.status == "AVAILABLE" and self.fee_bps is not None

    @classmethod
    def not_available(cls) -> "FeeEstimate":
        return cls(
            fee_bps=None,
            fee_absolute=None,
            currency=None,
            provider=UNAVAILABLE_PROVIDER_NAME,
            provider_version=UNAVAILABLE_PROVIDER_VERSION,
            quality=QUALITY_UNKNOWN,
            status=STATUS_NOT_AVAILABLE,
        )


@dataclass(frozen=True)
class SlippageEstimate:
    """Immutable slippage estimate. NOT_AVAILABLE until certified provider exists."""

    slippage_bps: Optional[float]
    provider: str
    provider_version: str
    quality: str
    status: str

    def is_usable(self) -> bool:
        return self.status == "AVAILABLE" and self.slippage_bps is not None

    @classmethod
    def not_available(cls) -> "SlippageEstimate":
        return cls(
            slippage_bps=None,
            provider=UNAVAILABLE_PROVIDER_NAME,
            provider_version=UNAVAILABLE_PROVIDER_VERSION,
            quality=QUALITY_UNKNOWN,
            status=STATUS_NOT_AVAILABLE,
        )


class MarketSnapshotProvider(Protocol):
    """Interface-only market snapshot provider."""

    provider_name: str
    provider_version: str
    provider_status: str

    def get_snapshot(
        self,
        *,
        symbol: str,
        context: Mapping[str, Any] | None = None,
    ) -> LiveMarketSnapshot:
        ...

    def metadata(self) -> ProviderMetadata:
        ...


class FXConversionProvider(Protocol):
    """Interface-only deterministic FX conversion provider (no online lookup)."""

    provider_name: str
    provider_version: str
    provider_status: str

    def get_conversion(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        context: Mapping[str, Any] | None = None,
    ) -> FXConversionQuote:
        ...

    def metadata(self) -> ProviderMetadata:
        ...


class FeeModelProvider(Protocol):
    """Interface-only fee model provider."""

    provider_name: str
    provider_version: str
    provider_status: str

    def estimate_fee(
        self,
        *,
        symbol: str,
        notional: float,
        side: str,
        context: Mapping[str, Any] | None = None,
    ) -> FeeEstimate:
        ...

    def metadata(self) -> ProviderMetadata:
        ...


class SlippageProvider(Protocol):
    """Interface-only slippage provider."""

    provider_name: str
    provider_version: str
    provider_status: str

    def estimate_slippage(
        self,
        *,
        symbol: str,
        notional: float,
        side: str,
        context: Mapping[str, Any] | None = None,
    ) -> SlippageEstimate:
        ...

    def metadata(self) -> ProviderMetadata:
        ...


class UnavailableMarketSnapshotProvider:
    """Default MarketSnapshotProvider — always NOT_AVAILABLE."""

    provider_name = UNAVAILABLE_PROVIDER_NAME
    provider_version = SCHEMA_VERSION_185A
    provider_status = STATUS_NOT_AVAILABLE

    def metadata(self) -> ProviderMetadata:
        return UNAVAILABLE_PROVIDER_METADATA

    def get_snapshot(
        self,
        *,
        symbol: str,
        context: Mapping[str, Any] | None = None,
    ) -> LiveMarketSnapshot:
        del symbol, context
        return LiveMarketSnapshot.not_available(
            provider=self.provider_name,
            provider_version=self.provider_version,
        )


class UnavailableFXConversionProvider:
    """Default FXConversionProvider — always NOT_AVAILABLE."""

    provider_name = UNAVAILABLE_PROVIDER_NAME
    provider_version = SCHEMA_VERSION_185A
    provider_status = STATUS_NOT_AVAILABLE

    def metadata(self) -> ProviderMetadata:
        return UNAVAILABLE_PROVIDER_METADATA

    def get_conversion(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        context: Mapping[str, Any] | None = None,
    ) -> FXConversionQuote:
        del context
        return FXConversionQuote.not_available(
            base_currency=base_currency or "UNKNOWN",
            quote_currency=quote_currency or "UNKNOWN",
            provider=self.provider_name,
            provider_version=self.provider_version,
        )


class UnavailableFeeModelProvider:
    """Default FeeModelProvider — always NOT_AVAILABLE."""

    provider_name = UNAVAILABLE_PROVIDER_NAME
    provider_version = SCHEMA_VERSION_185A
    provider_status = STATUS_NOT_AVAILABLE

    def metadata(self) -> ProviderMetadata:
        return UNAVAILABLE_PROVIDER_METADATA

    def estimate_fee(
        self,
        *,
        symbol: str,
        notional: float,
        side: str,
        context: Mapping[str, Any] | None = None,
    ) -> FeeEstimate:
        del symbol, notional, side, context
        return FeeEstimate.not_available()


class UnavailableSlippageProvider:
    """Default SlippageProvider — always NOT_AVAILABLE."""

    provider_name = UNAVAILABLE_PROVIDER_NAME
    provider_version = SCHEMA_VERSION_185A
    provider_status = STATUS_NOT_AVAILABLE

    def metadata(self) -> ProviderMetadata:
        return UNAVAILABLE_PROVIDER_METADATA

    def estimate_slippage(
        self,
        *,
        symbol: str,
        notional: float,
        side: str,
        context: Mapping[str, Any] | None = None,
    ) -> SlippageEstimate:
        del symbol, notional, side, context
        return SlippageEstimate.not_available()


DEFAULT_MARKET_SNAPSHOT_PROVIDER = UnavailableMarketSnapshotProvider()
DEFAULT_FX_CONVERSION_PROVIDER = UnavailableFXConversionProvider()
DEFAULT_FEE_MODEL_PROVIDER = UnavailableFeeModelProvider()
DEFAULT_SLIPPAGE_PROVIDER = UnavailableSlippageProvider()


__all__ = [
    "ProviderMetadata",
    "UNAVAILABLE_PROVIDER_METADATA",
    "FeeEstimate",
    "SlippageEstimate",
    "MarketSnapshotProvider",
    "FXConversionProvider",
    "FeeModelProvider",
    "SlippageProvider",
    "UnavailableMarketSnapshotProvider",
    "UnavailableFXConversionProvider",
    "UnavailableFeeModelProvider",
    "UnavailableSlippageProvider",
    "DEFAULT_MARKET_SNAPSHOT_PROVIDER",
    "DEFAULT_FX_CONVERSION_PROVIDER",
    "DEFAULT_FEE_MODEL_PROVIDER",
    "DEFAULT_SLIPPAGE_PROVIDER",
]
