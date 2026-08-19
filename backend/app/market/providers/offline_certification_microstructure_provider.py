"""Phase 186A-R1 — offline certification composite microstructure provider.

Combines fixture snapshot + fee + slippage for diagnostics/certification.
Not wired into ExecutionGate, AntiBleedGuard, or live authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from backend.app.market.live_market_snapshot import LiveMarketSnapshot
from backend.app.market.provider_interfaces import (
    FeeEstimate,
    FeeModelProvider,
    MarketSnapshotProvider,
    ProviderMetadata,
    SlippageEstimate,
    SlippageProvider,
)
from backend.app.market.providers._common import COMPOSITE_PROVIDER_NAME, PROVIDER_FRAMEWORK_VERSION
from backend.app.market.providers.evidence import canonical_evidence_hash


@dataclass(frozen=True)
class OfflineMicrostructureInputs:
    """Offline composite quote inputs. Diagnostic/certification only — not order authority."""

    expected_move_bps: float
    fee_bps: float
    spread_bps: float
    slippage_bps: float


@dataclass(frozen=True)
class OfflineMicrostructureResult:
    """Detailed offline composite result with immutable evidence custody."""

    available: bool
    inputs: Optional[OfflineMicrostructureInputs]
    reasons: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    market_hash: str = ""
    fee_hash: str = ""
    slippage_hash: str = ""
    expected_move_provenance: str = ""
    composite_hash: str = ""


class OfflineCertificationMicrostructureProvider:
    """Combines snapshot + fee + slippage for offline certification diagnostics."""

    provider_name = COMPOSITE_PROVIDER_NAME
    provider_version = PROVIDER_FRAMEWORK_VERSION
    provider_status = "OFFLINE_CERTIFICATION_ONLY"

    def __init__(
        self,
        *,
        market_snapshot_provider: MarketSnapshotProvider,
        fee_model_provider: FeeModelProvider,
        slippage_provider: SlippageProvider,
    ) -> None:
        self.market_snapshot_provider = market_snapshot_provider
        self.fee_model_provider = fee_model_provider
        self.slippage_provider = slippage_provider

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
    ) -> Optional[OfflineMicrostructureInputs]:
        return self.provide_detailed(
            symbol=symbol, side=side, notional=notional, context=context
        ).inputs

    def provide_detailed(
        self,
        *,
        symbol: str,
        side: str,
        notional: float,
        context: Mapping[str, Any] | None = None,
    ) -> OfflineMicrostructureResult:
        reasons: list[str] = []
        instrument = str(symbol or "").strip().upper()
        snapshot: LiveMarketSnapshot = self.market_snapshot_provider.get_snapshot(
            symbol=instrument, context=context
        )
        fee: FeeEstimate = self.fee_model_provider.estimate_fee(
            symbol=instrument, notional=notional, side=side, context=context
        )
        slip: SlippageEstimate = self.slippage_provider.estimate_slippage(
            symbol=instrument, notional=notional, side=side, context=context
        )

        if not snapshot.evidence_hash:
            reasons.append("market_hash:invalid")
        if not fee.evidence_hash:
            reasons.append("fee_hash:invalid")
        if not slip.evidence_hash:
            reasons.append("slippage_hash:invalid")

        if not snapshot.is_usable():
            reasons.append(f"market_snapshot:{snapshot.status}:{snapshot.fail_reason or 'unavailable'}")
        if snapshot.freshness != "FRESH":
            reasons.append(f"market_freshness:{snapshot.freshness}")
        if not fee.is_usable():
            reasons.append(f"fee:{fee.status}:{fee.fail_reason or 'unavailable'}")
        if not slip.is_usable():
            reasons.append(f"slippage:{slip.status}:{slip.fail_reason or 'unavailable'}")

        if fee.instrument and fee.instrument != instrument:
            reasons.append("instrument_scope_mismatch:fee")
        if slip.instrument and slip.instrument != instrument:
            reasons.append("instrument_scope_mismatch:slippage")

        expected = None
        expected_provenance = ""
        if isinstance(context, Mapping):
            expected = context.get("expected_move_bps")
            expected_provenance = str(context.get("expected_move_provenance") or "").strip()
        if expected is None:
            reasons.append("expected_move_bps:missing")
            expected_move_bps = None
        else:
            try:
                expected_move_bps = float(expected)
            except (TypeError, ValueError):
                reasons.append("expected_move_bps:invalid")
                expected_move_bps = None
        if not expected_provenance:
            reasons.append("expected_move_provenance:missing")

        diagnostics = {
            "provider_name": self.provider_name,
            "provider_version": self.provider_version,
            "provider_status": self.provider_status,
            "market_schema_id": snapshot.schema_id,
            "market_schema_version": snapshot.schema_version,
            "market_provider": snapshot.provider,
            "market_provider_version": snapshot.provider_version,
            "market_status": snapshot.status,
            "market_quality": snapshot.quality,
            "market_freshness": snapshot.freshness,
            "market_hash": snapshot.evidence_hash,
            "fee_model": fee.provider,
            "fee_model_version": fee.provider_version,
            "fee_status": fee.status,
            "fee_hash": fee.evidence_hash,
            "slippage_model": slip.provider,
            "slippage_model_version": slip.provider_version,
            "slippage_status": slip.status,
            "slippage_hash": slip.evidence_hash,
            "expected_move_provenance": expected_provenance,
        }

        material = {
            "provider": self.provider_name,
            "provider_version": self.provider_version,
            "instrument": instrument,
            "market_hash": snapshot.evidence_hash,
            "fee_hash": fee.evidence_hash,
            "slippage_hash": slip.evidence_hash,
            "expected_move_bps": expected_move_bps,
            "expected_move_provenance": expected_provenance,
            "reasons": list(reasons),
            "available": not bool(reasons),
        }
        composite_hash = canonical_evidence_hash(material)
        diagnostics = {**diagnostics, "composite_hash": composite_hash}

        if reasons:
            return OfflineMicrostructureResult(
                available=False,
                inputs=None,
                reasons=tuple(reasons),
                diagnostics=diagnostics,
                market_hash=snapshot.evidence_hash,
                fee_hash=fee.evidence_hash,
                slippage_hash=slip.evidence_hash,
                expected_move_provenance=expected_provenance,
                composite_hash=composite_hash,
            )

        assert expected_move_bps is not None
        assert snapshot.spread_bps is not None
        assert fee.fee_bps is not None
        assert slip.slippage_bps is not None

        inputs = OfflineMicrostructureInputs(
            expected_move_bps=float(expected_move_bps),
            fee_bps=float(fee.fee_bps),
            spread_bps=float(snapshot.spread_bps),
            slippage_bps=float(slip.slippage_bps),
        )
        return OfflineMicrostructureResult(
            available=True,
            inputs=inputs,
            reasons=(),
            diagnostics=diagnostics,
            market_hash=snapshot.evidence_hash,
            fee_hash=fee.evidence_hash,
            slippage_hash=slip.evidence_hash,
            expected_move_provenance=expected_provenance,
            composite_hash=composite_hash,
        )


__all__ = [
    "OfflineMicrostructureInputs",
    "OfflineMicrostructureResult",
    "OfflineCertificationMicrostructureProvider",
    "COMPOSITE_PROVIDER_NAME",
]
