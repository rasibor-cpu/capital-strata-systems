"""Phase 186A-R1 — offline OANDA pricing fixture → LiveMarketSnapshot (no HTTP)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from backend.app.market.live_market_snapshot import LiveMarketSnapshot
from backend.app.market.provider_interfaces import ProviderMetadata
from backend.app.market.providers._common import (
    DEFAULT_QUOTE_MAX_AGE_SECONDS,
    OANDA_FIXTURE_PROVIDER_NAME,
    PROVIDER_FRAMEWORK_VERSION,
    classify_freshness,
    context_float,
    evaluation_time_from_context,
    load_json_mapping,
    parse_utc_timestamp,
    require_positive_finite,
    resolve_approved_fixture_path,
)
from backend.app.market.providers.evidence import canonical_evidence_hash
from backend.app.market.status import (
    QUALITY_CERTIFIED,
    QUALITY_UNKNOWN,
    QUALITY_UNVERIFIED,
    STATUS_AVAILABLE,
    STATUS_NOT_AVAILABLE,
)


class OandaFixtureMarketProvider:
    """Deterministic offline OANDA pricing fixture adapter. OFFLINE_CERTIFICATION_ONLY."""

    provider_name = OANDA_FIXTURE_PROVIDER_NAME
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

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            provider_status=self.provider_status,
        )

    def get_snapshot(
        self,
        *,
        symbol: str,
        context: Mapping[str, Any] | None = None,
    ) -> LiveMarketSnapshot:
        instrument = str(symbol or "").strip().upper()
        try:
            return self._build(instrument=instrument, context=context)
        except ValueError as exc:
            payload = {
                "status": STATUS_NOT_AVAILABLE,
                "provider": self.provider_name,
                "provider_version": self.provider_version,
                "instrument": instrument,
                "fail_reason": str(exc),
            }
            return LiveMarketSnapshot(
                bid=None,
                ask=None,
                mid=None,
                spread=None,
                spread_bps=None,
                estimated_slippage=None,
                estimated_fee=None,
                currency=None,
                quote_timestamp=None,
                provider=self.provider_name,
                provider_version=self.provider_version,
                quality=QUALITY_UNKNOWN,
                freshness="NOT_AVAILABLE",
                status=STATUS_NOT_AVAILABLE,
                evidence_hash=canonical_evidence_hash(payload),
                fail_reason=str(exc),
            )

    def _build(
        self,
        *,
        instrument: str,
        context: Mapping[str, Any] | None,
    ) -> LiveMarketSnapshot:
        if not instrument:
            raise ValueError("instrument required")

        payload = self._payload
        quotes = payload.get("quotes")
        if isinstance(quotes, Mapping):
            row = quotes.get(instrument)
            if not isinstance(row, Mapping):
                raise ValueError("unsupported instrument")
        else:
            fixture_instrument = str(
                payload.get("instrument") or payload.get("symbol") or ""
            ).upper()
            if fixture_instrument != instrument:
                raise ValueError("unsupported instrument")
            row = payload

        bid = require_positive_finite("bid", row.get("bid"))
        ask = require_positive_finite("ask", row.get("ask"))
        if ask < bid:
            raise ValueError("crossed market ask < bid")

        timestamp_raw = row.get("timestamp") or row.get("time") or row.get("quote_timestamp")
        if timestamp_raw is None or not str(timestamp_raw).strip():
            raise ValueError("missing timestamp")
        quote_time = parse_utc_timestamp(timestamp_raw)
        evaluation_time = evaluation_time_from_context(context)
        max_age = context_float(context, "max_age_seconds", DEFAULT_QUOTE_MAX_AGE_SECONDS)
        freshness, age = classify_freshness(
            quote_time=quote_time,
            evaluation_time=evaluation_time,
            max_age_seconds=max_age,
        )
        if freshness == "FUTURE":
            raise ValueError("future-dated quote")
        if freshness != "FRESH":
            raise ValueError(f"stale quote freshness={freshness} age={age}")

        mid = (bid + ask) / 2.0
        spread = ask - bid
        if mid <= 0:
            raise ValueError("unable to compute spread_bps")
        spread_bps = (spread / mid) * 10_000.0
        currency = str(row.get("currency") or payload.get("currency") or "USD").upper()
        quality_token = str(payload.get("quality") or row.get("quality") or "CERTIFIED").upper()
        quality = (
            QUALITY_CERTIFIED
            if quality_token == "CERTIFIED"
            else QUALITY_UNVERIFIED if quality_token == "UNVERIFIED" else QUALITY_CERTIFIED
        )
        quote_timestamp = quote_time.isoformat().replace("+00:00", "Z")
        evidence = {
            "schema_id": "LIVE_MARKET_SNAPSHOT",
            "schema_version": "185A.1",
            "provider": self.provider_name,
            "provider_version": self.provider_version,
            "instrument": instrument,
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread": spread,
            "spread_bps": spread_bps,
            "currency": currency,
            "quote_timestamp": quote_timestamp,
            "quality": quality,
            "freshness": freshness,
            "status": STATUS_AVAILABLE,
        }
        return LiveMarketSnapshot(
            bid=bid,
            ask=ask,
            mid=mid,
            spread=spread,
            spread_bps=spread_bps,
            estimated_slippage=None,
            estimated_fee=None,
            currency=currency,
            quote_timestamp=quote_timestamp,
            provider=self.provider_name,
            provider_version=self.provider_version,
            quality=quality,
            freshness=freshness,
            status=STATUS_AVAILABLE,
            evidence_hash=canonical_evidence_hash(evidence),
            fail_reason="",
        )
