"""Phase 184A / 185A — live microstructure provider (fail-closed).

Phase 185A replaces ad-hoc placeholders with market framework interfaces.
Default providers return NOT_AVAILABLE; no fabricated microstructure values.
If snapshot / fee / slippage inputs are unavailable, returns None so
ExecutionGate keeps missing-input fail-closed rejection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol

from backend.app.market.live_market_snapshot import LiveMarketSnapshot
from backend.app.market.provider_interfaces import (
    DEFAULT_FEE_MODEL_PROVIDER,
    DEFAULT_MARKET_SNAPSHOT_PROVIDER,
    DEFAULT_SLIPPAGE_PROVIDER,
    FeeEstimate,
    FeeModelProvider,
    MarketSnapshotProvider,
    ProviderMetadata,
    SlippageEstimate,
    SlippageProvider,
    UNAVAILABLE_PROVIDER_METADATA,
)
from backend.app.market.status import (
    SCHEMA_VERSION_185A,
    STATUS_NOT_AVAILABLE,
    UNAVAILABLE_PROVIDER_NAME,
)


@dataclass(frozen=True)
class LiveMicrostructureInputs:
    """Complete microstructure inputs required by AntiBleed evaluation."""

    expected_move_bps: float
    fee_bps: float
    spread_bps: float
    slippage_bps: float


class LiveMicrostructureProvider(Protocol):
    """Governed provider contract for live AntiBleed microstructure inputs."""

    def provide(
        self,
        *,
        symbol: str,
        side: str,
        notional: float,
        context: Mapping[str, Any] | None = None,
    ) -> Optional[LiveMicrostructureInputs]:
        """Return complete inputs, or None to force fail-closed missing-input rejection."""


class UnavailableLiveMicrostructureProvider:
    """Default provider — never fabricates values; always fail-closed."""

    provider_name = UNAVAILABLE_PROVIDER_NAME
    provider_version = SCHEMA_VERSION_185A
    provider_status = STATUS_NOT_AVAILABLE

    def metadata(self) -> ProviderMetadata:
        return UNAVAILABLE_PROVIDER_METADATA

    def provide(
        self,
        *,
        symbol: str,
        side: str,
        notional: float,
        context: Mapping[str, Any] | None = None,
    ) -> Optional[LiveMicrostructureInputs]:
        del symbol, side, notional, context
        return None


class MarketFrameworkMicrostructureProvider:
    """Bridge from Phase 185A market interfaces to AntiBleed inputs.

    Does not invent values. Returns None unless snapshot + fee + slippage are usable.
    Expected-move is never inferred here (remains fail-closed without explicit input).
    """

    provider_name = "MARKET_FRAMEWORK_BRIDGE"
    provider_version = SCHEMA_VERSION_185A
    provider_status = STATUS_NOT_AVAILABLE

    def __init__(
        self,
        *,
        market_snapshot_provider: MarketSnapshotProvider | None = None,
        fee_model_provider: FeeModelProvider | None = None,
        slippage_provider: SlippageProvider | None = None,
    ) -> None:
        self.market_snapshot_provider = (
            market_snapshot_provider or DEFAULT_MARKET_SNAPSHOT_PROVIDER
        )
        self.fee_model_provider = fee_model_provider or DEFAULT_FEE_MODEL_PROVIDER
        self.slippage_provider = slippage_provider or DEFAULT_SLIPPAGE_PROVIDER

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            provider_status=self.provider_status,
        )

    def provide(
        self,
        *,
        symbol: str,
        side: str,
        notional: float,
        context: Mapping[str, Any] | None = None,
    ) -> Optional[LiveMicrostructureInputs]:
        snapshot: LiveMarketSnapshot = self.market_snapshot_provider.get_snapshot(
            symbol=symbol,
            context=context,
        )
        fee: FeeEstimate = self.fee_model_provider.estimate_fee(
            symbol=symbol,
            notional=notional,
            side=side,
            context=context,
        )
        slip: SlippageEstimate = self.slippage_provider.estimate_slippage(
            symbol=symbol,
            notional=notional,
            side=side,
            context=context,
        )
        # Expected move is not part of the snapshot contract; without an explicit
        # certified expected-move source this bridge remains fail-closed.
        if not snapshot.is_usable() or not fee.is_usable() or not slip.is_usable():
            return None
        if snapshot.spread_bps is None or fee.fee_bps is None or slip.slippage_bps is None:
            return None
        expected = None
        if isinstance(context, Mapping):
            expected = context.get("expected_move_bps")
        if expected is None:
            return None
        try:
            expected_move_bps = float(expected)
        except (TypeError, ValueError):
            return None
        return LiveMicrostructureInputs(
            expected_move_bps=expected_move_bps,
            fee_bps=float(fee.fee_bps),
            spread_bps=float(snapshot.spread_bps),
            slippage_bps=float(slip.slippage_bps),
        )


DEFAULT_LIVE_MICROSTRUCTURE_PROVIDER = UnavailableLiveMicrostructureProvider()
DEFAULT_MARKET_FRAMEWORK_MICROSTRUCTURE_PROVIDER = MarketFrameworkMicrostructureProvider()


__all__ = [
    "LiveMicrostructureInputs",
    "LiveMicrostructureProvider",
    "UnavailableLiveMicrostructureProvider",
    "MarketFrameworkMicrostructureProvider",
    "DEFAULT_LIVE_MICROSTRUCTURE_PROVIDER",
    "DEFAULT_MARKET_FRAMEWORK_MICROSTRUCTURE_PROVIDER",
]
