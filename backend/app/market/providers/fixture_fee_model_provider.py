"""Phase 186A-R1 — offline fixture fee-model provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from backend.app.market.provider_interfaces import FeeEstimate, ProviderMetadata
from backend.app.market.providers._common import (
    FEE_FIXTURE_PROVIDER_NAME,
    PROVIDER_FRAMEWORK_VERSION,
    load_json_mapping,
    resolve_approved_fixture_path,
)
from backend.app.market.providers.evidence import canonical_evidence_hash
from backend.app.market.status import QUALITY_CERTIFIED, QUALITY_UNKNOWN, STATUS_AVAILABLE, STATUS_NOT_AVAILABLE


class FixtureFeeModelProvider:
    """Configuration/fixture-backed fee model for offline certification only."""

    provider_name = FEE_FIXTURE_PROVIDER_NAME
    provider_version = PROVIDER_FRAMEWORK_VERSION
    provider_status = "OFFLINE_CERTIFICATION_ONLY"

    def __init__(
        self,
        fixture_path: Path | str,
        *,
        approved_root: Path | None = None,
    ) -> None:
        self.fixture_path = resolve_approved_fixture_path(fixture_path, approved_root=approved_root)
        self._payload = dict(load_json_mapping(self.fixture_path, approved_root=approved_root))
        self.model_id = str(self._payload.get("model_id") or "FEE_MODEL_UNSPECIFIED")
        self.model_version = str(self._payload.get("model_version") or PROVIDER_FRAMEWORK_VERSION)

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name=self.provider_name,
            provider_version=self.model_version,
            provider_status=self.provider_status,
        )

    def estimate_fee(
        self,
        *,
        symbol: str,
        notional: float,
        side: str,
        context: Mapping[str, Any] | None = None,
    ) -> FeeEstimate:
        del side, context
        instrument = str(symbol or "").strip().upper()
        try:
            notional_f = float(notional)
        except (TypeError, ValueError):
            return self._unavailable(instrument, "invalid_notional")
        if notional_f != notional_f or notional_f <= 0:
            return self._unavailable(instrument, "invalid_notional")

        instruments = self._payload.get("instruments")
        if not isinstance(instruments, Mapping) or instrument not in instruments:
            return self._unavailable(instrument, "instrument_out_of_scope")
        row = instruments[instrument]
        if not isinstance(row, Mapping):
            return self._unavailable(instrument, "malformed_fee_row")
        if row.get("fee_bps") is None:
            return self._unavailable(instrument, "insufficient_fee_facts")
        try:
            fee_bps = float(row["fee_bps"])
        except (TypeError, ValueError):
            return self._unavailable(instrument, "invalid_fee_bps")
        if fee_bps != fee_bps or fee_bps < 0:
            return self._unavailable(instrument, "invalid_fee_bps")

        fee_absolute = notional_f * (fee_bps / 10_000.0)
        currency = str(row.get("currency") or self._payload.get("currency") or "CAD")
        evidence = {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "instrument": instrument,
            "fee_bps": fee_bps,
            "fee_absolute": fee_absolute,
            "currency": currency,
            "status": STATUS_AVAILABLE,
        }
        return FeeEstimate(
            fee_bps=fee_bps,
            fee_absolute=fee_absolute,
            currency=currency,
            provider=f"{self.provider_name}:{self.model_id}",
            provider_version=self.model_version,
            quality=QUALITY_CERTIFIED,
            status=STATUS_AVAILABLE,
            evidence_hash=canonical_evidence_hash(evidence),
            fail_reason="",
            instrument=instrument,
        )

    def _unavailable(self, instrument: str, reason: str) -> FeeEstimate:
        evidence = {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "instrument": instrument,
            "status": STATUS_NOT_AVAILABLE,
            "fail_reason": reason,
        }
        return FeeEstimate(
            fee_bps=None,
            fee_absolute=None,
            currency=None,
            provider=f"{self.provider_name}:{self.model_id}",
            provider_version=self.model_version,
            quality=QUALITY_UNKNOWN,
            status=STATUS_NOT_AVAILABLE,
            evidence_hash=canonical_evidence_hash(evidence),
            fail_reason=reason,
            instrument=instrument,
        )
