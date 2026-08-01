"""Phase 184A — live microstructure provider interface (fail-closed).

Live paths must not invent fee/spread/slippage/expected-move values.
If no provider is configured or the provider returns None, ExecutionGate
keeps the existing missing-input fail-closed rejection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol


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


DEFAULT_LIVE_MICROSTRUCTURE_PROVIDER = UnavailableLiveMicrostructureProvider()


__all__ = [
    "LiveMicrostructureInputs",
    "LiveMicrostructureProvider",
    "UnavailableLiveMicrostructureProvider",
    "DEFAULT_LIVE_MICROSTRUCTURE_PROVIDER",
]
