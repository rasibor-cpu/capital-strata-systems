"""Phase 186A-R1 — offline fixture slippage provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from backend.app.market.provider_interfaces import ProviderMetadata, SlippageEstimate
from backend.app.market.providers._common import (
    PROVIDER_FRAMEWORK_VERSION,
    SLIPPAGE_FIXTURE_PROVIDER_NAME,
    load_json_mapping,
    resolve_approved_fixture_path,
)
from backend.app.market.providers.evidence import canonical_evidence_hash
from backend.app.market.status import QUALITY_CERTIFIED, QUALITY_UNKNOWN, STATUS_AVAILABLE, STATUS_NOT_AVAILABLE


class FixtureSlippageProvider:
    """Deterministic offline slippage model. Never silently returns zero."""

    provider_name = SLIPPAGE_FIXTURE_PROVIDER_NAME
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
        self.model_id = str(self._payload.get("model_id") or "SLIPPAGE_MODEL_UNSPECIFIED")
        self.model_version = str(self._payload.get("model_version") or PROVIDER_FRAMEWORK_VERSION)

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name=self.provider_name,
            provider_version=self.model_version,
            provider_status=self.provider_status,
        )

    def estimate_slippage(
        self,
        *,
        symbol: str,
        notional: float,
        side: str,
        context: Mapping[str, Any] | None = None,
    ) -> SlippageEstimate:
        del side, context, notional
        instrument = str(symbol or "").strip().upper()
        instruments = self._payload.get("instruments")
        if not isinstance(instruments, Mapping) or instrument not in instruments:
            return self._unavailable(instrument, "instrument_out_of_scope")
        row = instruments[instrument]
        if not isinstance(row, Mapping):
            return self._unavailable(instrument, "malformed_slippage_row")
        if "slippage_bps" not in row or row.get("slippage_bps") is None:
            return self._unavailable(instrument, "insufficient_slippage_facts")
        try:
            slippage_bps = float(row["slippage_bps"])
        except (TypeError, ValueError):
            return self._unavailable(instrument, "invalid_slippage_bps")
        if slippage_bps != slippage_bps or slippage_bps < 0:
            return self._unavailable(instrument, "invalid_slippage_bps")
        if slippage_bps == 0.0 and not bool(row.get("allow_zero", False)):
            return self._unavailable(instrument, "silent_zero_slippage_forbidden")

        evidence = {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "instrument": instrument,
            "slippage_bps": slippage_bps,
            "status": STATUS_AVAILABLE,
        }
        return SlippageEstimate(
            slippage_bps=slippage_bps,
            provider=f"{self.provider_name}:{self.model_id}",
            provider_version=self.model_version,
            quality=QUALITY_CERTIFIED,
            status=STATUS_AVAILABLE,
            evidence_hash=canonical_evidence_hash(evidence),
            fail_reason="",
            instrument=instrument,
        )

    def _unavailable(self, instrument: str, reason: str) -> SlippageEstimate:
        evidence = {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "instrument": instrument,
            "status": STATUS_NOT_AVAILABLE,
            "fail_reason": reason,
        }
        return SlippageEstimate(
            slippage_bps=None,
            provider=f"{self.provider_name}:{self.model_id}",
            provider_version=self.model_version,
            quality=QUALITY_UNKNOWN,
            status=STATUS_NOT_AVAILABLE,
            evidence_hash=canonical_evidence_hash(evidence),
            fail_reason=reason,
            instrument=instrument,
        )
