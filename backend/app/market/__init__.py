"""Phase 185A — market data and FX conversion framework public surface."""

from __future__ import annotations

from backend.app.market.fx_conversion_contract import (
    FXConversionError,
    FXConversionQuote,
    normalize_currency_code,
)
from backend.app.market.live_market_snapshot import LiveMarketSnapshot, LiveMarketSnapshotError
from backend.app.market.provider_interfaces import (
    DEFAULT_FEE_MODEL_PROVIDER,
    DEFAULT_FX_CONVERSION_PROVIDER,
    DEFAULT_MARKET_SNAPSHOT_PROVIDER,
    DEFAULT_SLIPPAGE_PROVIDER,
    FeeEstimate,
    FeeModelProvider,
    FXConversionProvider,
    MarketSnapshotProvider,
    ProviderMetadata,
    SlippageEstimate,
    SlippageProvider,
    UnavailableFeeModelProvider,
    UnavailableFXConversionProvider,
    UnavailableMarketSnapshotProvider,
    UnavailableSlippageProvider,
    UNAVAILABLE_PROVIDER_METADATA,
)
from backend.app.market.status import FRAMEWORK_VERSION, STATUS_NOT_AVAILABLE, STATUS_UNKNOWN

__all__ = [
    "FRAMEWORK_VERSION",
    "STATUS_NOT_AVAILABLE",
    "STATUS_UNKNOWN",
    "LiveMarketSnapshot",
    "LiveMarketSnapshotError",
    "FXConversionQuote",
    "FXConversionError",
    "normalize_currency_code",
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
