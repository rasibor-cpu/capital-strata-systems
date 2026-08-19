"""Phase 186A-R1 — offline fixture FX conversion with immutable per-result provenance."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional

from backend.app.market.fx_conversion_contract import FXConversionQuote, normalize_currency_code
from backend.app.market.provider_interfaces import ProviderMetadata
from backend.app.market.providers._common import (
    DEFAULT_FX_MAX_AGE_SECONDS,
    DEFAULT_TRIANGULATION_TIMESTAMP_WINDOW_SECONDS,
    FX_FIXTURE_PROVIDER_NAME,
    PROVIDER_FRAMEWORK_VERSION,
    canonical_pair,
    classify_freshness,
    context_float,
    evaluation_time_from_context,
    load_json_mapping,
    parse_utc_timestamp,
    require_positive_finite,
    resolve_approved_fixture_path,
)
from backend.app.market.providers.evidence import canonical_evidence_hash, weakest_quality
from backend.app.market.status import QUALITY_CERTIFIED, QUALITY_UNKNOWN, STATUS_AVAILABLE, STATUS_NOT_AVAILABLE


class FixtureFXConversionProvider:
    """Deterministic fixture-backed FX conversion with immutable result provenance.

    OFFLINE_CERTIFICATION_ONLY. Never uses a default cross-currency rate of 1.
    Same-currency IDENTITY returns rate=1 with governed quality without a fixture rate.
    """

    provider_name = FX_FIXTURE_PROVIDER_NAME
    provider_version = PROVIDER_FRAMEWORK_VERSION
    provider_status = "OFFLINE_CERTIFICATION_ONLY"

    def __init__(
        self,
        fixture_path: Path | str,
        *,
        approved_root: Path | None = None,
    ) -> None:
        self.fixture_path = resolve_approved_fixture_path(fixture_path, approved_root=approved_root)
        self._approved_root = approved_root
        payload = dict(load_json_mapping(self.fixture_path, approved_root=approved_root))
        self._rates: dict[str, dict[str, Any]] = {}
        rates = payload.get("rates")
        if not isinstance(rates, Mapping):
            raise ValueError("FX fixture requires rates object")
        seen: dict[str, float] = {}
        for key, row in rates.items():
            if not isinstance(row, Mapping):
                continue
            token = str(key).upper().replace("-", "/")
            if "/" not in token and len(token) == 6:
                token = f"{token[:3]}/{token[3:]}"
            rate = require_positive_finite("rate", row.get("rate"))
            if token in seen and seen[token] != rate:
                raise ValueError(f"contradictory duplicate rates for {token}")
            seen[token] = rate
            self._rates[token] = dict(row)
            self._rates[token]["_rate_id"] = str(row.get("rate_id") or token)
        self._hub = str(payload.get("triangulation_hub") or "USD").upper()

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            provider_status=self.provider_status,
        )

    def get_conversion(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        context: Mapping[str, Any] | None = None,
    ) -> FXConversionQuote:
        base = normalize_currency_code(base_currency)
        quote = normalize_currency_code(quote_currency)
        if base is None or quote is None:
            return self._unavailable(
                str(base_currency or "UNKNOWN"),
                str(quote_currency or "UNKNOWN"),
                reason="invalid_currency",
            )

        if base == quote:
            return self._identity(base, context)

        try:
            return self._resolve(base, quote, context)
        except ValueError as exc:
            return self._unavailable(base, quote, reason=str(exc))

    def _identity(self, currency: str, context: Mapping[str, Any] | None) -> FXConversionQuote:
        evaluation_time = evaluation_time_from_context(context)
        ts = evaluation_time.isoformat().replace("+00:00", "Z")
        path = (currency,)
        payload = {
            "schema_id": "FX_CONVERSION",
            "schema_version": "185A.1",
            "provider": self.provider_name,
            "provider_version": self.provider_version,
            "base": currency,
            "quote": currency,
            "rate": 1.0,
            "path_type": "IDENTITY",
            "conversion_path": list(path),
            "quality": "GOVERNED_IDENTITY",
            "status": STATUS_AVAILABLE,
        }
        return FXConversionQuote(
            base_currency=currency,
            quote_currency=currency,
            rate=1.0,
            timestamp=ts,
            provider=self.provider_name,
            provider_version=self.provider_version,
            quality="GOVERNED_IDENTITY",
            status=STATUS_AVAILABLE,
            conversion_path=path,
            path_type="IDENTITY",
            contributing_rate_ids=("IDENTITY",),
            contributing_provider_ids=(self.provider_name,),
            contributing_timestamps=(ts,),
            evidence_hash=canonical_evidence_hash(payload),
            fail_reason="",
        )

    def _unavailable(self, base: str, quote: str, *, reason: str) -> FXConversionQuote:
        payload = {
            "schema_id": "FX_CONVERSION",
            "status": STATUS_NOT_AVAILABLE,
            "base": base,
            "quote": quote,
            "fail_reason": reason,
            "provider": self.provider_name,
            "provider_version": self.provider_version,
        }
        return FXConversionQuote(
            base_currency=base,
            quote_currency=quote,
            rate=None,
            timestamp=None,
            provider=self.provider_name,
            provider_version=self.provider_version,
            quality=QUALITY_UNKNOWN,
            status=STATUS_NOT_AVAILABLE,
            conversion_path=(),
            path_type="NONE",
            contributing_rate_ids=(),
            contributing_provider_ids=(),
            contributing_timestamps=(),
            evidence_hash=canonical_evidence_hash(payload),
            fail_reason=reason,
        )

    def _lookup_leg(
        self,
        base: str,
        quote: str,
        context: Mapping[str, Any] | None,
    ) -> Optional[dict[str, Any]]:
        key = canonical_pair(base, quote)
        row = self._rates.get(key)
        if not isinstance(row, Mapping):
            return None
        rate = require_positive_finite("rate", row.get("rate"))
        timestamp = str(row.get("timestamp") or "")
        if not timestamp.strip():
            raise ValueError("missing rate timestamp")
        quote_time = parse_utc_timestamp(timestamp)
        evaluation_time = evaluation_time_from_context(context)
        max_age = context_float(context, "fx_max_age_seconds", DEFAULT_FX_MAX_AGE_SECONDS)
        freshness, age = classify_freshness(
            quote_time=quote_time,
            evaluation_time=evaluation_time,
            max_age_seconds=max_age,
        )
        if freshness == "FUTURE":
            raise ValueError("future-dated conversion rate")
        if freshness != "FRESH":
            raise ValueError(f"stale conversion freshness={freshness} age={age}")
        quality = str(row.get("quality") or QUALITY_CERTIFIED).upper()
        return {
            "rate": rate,
            "timestamp": quote_time.isoformat().replace("+00:00", "Z"),
            "quote_time": quote_time,
            "rate_id": str(row.get("_rate_id") or key),
            "provider_id": str(row.get("provider_id") or self.provider_name),
            "quality": quality if quality != "UNKNOWN" else QUALITY_CERTIFIED,
            "pair": key,
        }

    def _resolve(
        self,
        base: str,
        quote: str,
        context: Mapping[str, Any] | None,
    ) -> FXConversionQuote:
        direct = self._lookup_leg(base, quote, context)
        if direct is not None:
            return self._build_quote(
                base=base,
                quote=quote,
                rate=float(direct["rate"]),
                path_type="DIRECT",
                path=(direct["pair"],),
                legs=(direct,),
            )

        inverse = self._lookup_leg(quote, base, context)
        if inverse is not None:
            return self._build_quote(
                base=base,
                quote=quote,
                rate=1.0 / float(inverse["rate"]),
                path_type="INVERSE",
                path=(inverse["pair"], "INVERSE"),
                legs=(inverse,),
            )

        hub = self._hub
        if base == hub or quote == hub:
            raise ValueError("missing conversion leg")

        leg_a = self._lookup_leg(base, hub, context)
        path_a: tuple[str, ...]
        if leg_a is None:
            inv_a = self._lookup_leg(hub, base, context)
            if inv_a is None:
                raise ValueError("missing conversion leg")
            leg_a = {
                **inv_a,
                "rate": 1.0 / float(inv_a["rate"]),
                "pair": inv_a["pair"],
            }
            path_a = (inv_a["pair"], "INVERSE")
        else:
            path_a = (leg_a["pair"],)

        leg_b = self._lookup_leg(hub, quote, context)
        path_b: tuple[str, ...]
        if leg_b is None:
            inv_b = self._lookup_leg(quote, hub, context)
            if inv_b is None:
                raise ValueError("missing conversion leg")
            leg_b = {
                **inv_b,
                "rate": 1.0 / float(inv_b["rate"]),
                "pair": inv_b["pair"],
            }
            path_b = (inv_b["pair"], "INVERSE")
        else:
            path_b = (leg_b["pair"],)

        window = context_float(
            context,
            "triangulation_timestamp_window_seconds",
            DEFAULT_TRIANGULATION_TIMESTAMP_WINDOW_SECONDS,
        )
        delta = abs(
            (leg_a["quote_time"] - leg_b["quote_time"]).total_seconds()  # type: ignore[operator]
        )
        if delta > window:
            raise ValueError("triangulation timestamp inconsistency")

        path = path_a + (f"TRIANGULATE_VIA_{hub}",) + path_b
        return self._build_quote(
            base=base,
            quote=quote,
            rate=float(leg_a["rate"]) * float(leg_b["rate"]),
            path_type="TRIANGULATED",
            path=path,
            legs=(leg_a, leg_b),
        )

    def _build_quote(
        self,
        *,
        base: str,
        quote: str,
        rate: float,
        path_type: str,
        path: tuple[str, ...],
        legs: tuple[dict[str, Any], ...],
    ) -> FXConversionQuote:
        timestamps = tuple(str(leg["timestamp"]) for leg in legs)
        rate_ids = tuple(str(leg["rate_id"]) for leg in legs)
        provider_ids = tuple(str(leg["provider_id"]) for leg in legs)
        quality = weakest_quality(*(str(leg["quality"]) for leg in legs))
        ts = min(timestamps) if timestamps else None
        payload = {
            "schema_id": "FX_CONVERSION",
            "schema_version": "185A.1",
            "provider": self.provider_name,
            "provider_version": self.provider_version,
            "base": base,
            "quote": quote,
            "rate": rate,
            "path_type": path_type,
            "conversion_path": list(path),
            "contributing_rate_ids": list(rate_ids),
            "contributing_provider_ids": list(provider_ids),
            "contributing_timestamps": list(timestamps),
            "quality": quality,
            "status": STATUS_AVAILABLE,
            "timestamp": ts,
        }
        return FXConversionQuote(
            base_currency=base,
            quote_currency=quote,
            rate=rate,
            timestamp=ts,
            provider=self.provider_name,
            provider_version=self.provider_version,
            quality=quality,
            status=STATUS_AVAILABLE,
            conversion_path=path,
            path_type=path_type,
            contributing_rate_ids=rate_ids,
            contributing_provider_ids=provider_ids,
            contributing_timestamps=timestamps,
            evidence_hash=canonical_evidence_hash(payload),
            fail_reason="",
        )
