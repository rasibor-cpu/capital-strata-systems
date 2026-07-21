"""Phase 178A — provider-neutral market-data adapter (read-only)."""

from __future__ import annotations

from typing import Any, Protocol

from backend.options.options_income_advisory_contracts import market_data_envelope, unexpected_advisory_fault
from backend.options.options_income_freshness import evaluate_freshness, utc_now
from backend.options.options_income_symbol_normalization import normalize_equity_symbol


class UnderlyingQuoteProvider(Protocol):
    def get_underlying_quote(self, symbol: str) -> dict[str, Any]: ...


def fetch_underlying_market_data(
    symbol: str,
    *,
    provider: UnderlyingQuoteProvider | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Retrieve underlying quote via optional provider; never invent prices."""
    ts = generated_at or utc_now()
    norm = normalize_equity_symbol(symbol)
    if not norm.get("canonical"):
        return market_data_envelope(
            generated_at=ts,
            status="SYMBOL_UNSUPPORTED",
            provenance="CONFIGURATION",
            freshness="UNKNOWN",
            quality="NONE",
            failure_reason="empty_symbol",
            symbol=symbol,
            canonical_symbol=None,
        )

    if provider is None:
        return market_data_envelope(
            generated_at=ts,
            status="NOT_CONFIGURED",
            provenance="CONFIGURATION",
            freshness="UNKNOWN",
            quality="NONE",
            failure_reason="MARKET_DATA_PROVIDER_NOT_CONFIGURED",
            symbol=symbol,
            canonical_symbol=norm["canonical"],
            provider_native_symbol=norm.get("provider_native"),
            missing_fields=["bid", "ask", "last", "midpoint", "timestamp"],
        )

    try:
        raw = dict(provider.get_underlying_quote(str(norm["canonical"])) or {})
    except Exception as exc:  # noqa: BLE001
        fault = unexpected_advisory_fault(exc)
        return market_data_envelope(
            generated_at=ts,
            status="FAILED",
            provenance="MARKET_DATA_PROVIDER",
            freshness="UNKNOWN",
            quality="NONE",
            failure_reason=fault["failure_reason"],
            correlation_id=fault["correlation_id"],
            symbol=symbol,
            canonical_symbol=norm["canonical"],
        )

    if raw.get("demonstration") or str(raw.get("provenance") or "").upper() == "DEMONSTRATION":
        # Never publish demo as live
        return market_data_envelope(
            generated_at=ts,
            status="FAILED",
            provenance="DEMONSTRATION",
            freshness="UNKNOWN",
            quality="NONE",
            failure_reason="demonstration_data_rejected_as_live",
            symbol=symbol,
            canonical_symbol=norm["canonical"],
        )

    provider_ts = raw.get("timestamp") or raw.get("provider_timestamp")
    fresh = evaluate_freshness("underlying_quote", provider_timestamp=provider_ts, now=ts)
    status = str(raw.get("status") or "READY").upper()
    if status in {"MARKET_DATA_READY", "ADVISORY_READY"}:
        status = "READY"
    status = "STALE" if fresh["stale"] else status
    if status == "READY" and fresh["stale"]:
        status = "STALE"

    bid = raw.get("bid")
    ask = raw.get("ask")
    last = raw.get("last")
    midpoint = raw.get("midpoint")
    if midpoint is None and bid is not None and ask is not None:
        try:
            midpoint = (float(bid) + float(ask)) / 2.0
        except (TypeError, ValueError):
            midpoint = None

    missing = [f for f in ("bid", "ask", "last") if raw.get(f) is None]
    if missing and status == "READY":
        status = "PARTIAL_DATA"

    return market_data_envelope(
        generated_at=ts,
        status=status,
        provenance=str(raw.get("provenance") or "MARKET_DATA_PROVIDER"),
        provider_timestamp=provider_ts,
        received_at=ts,
        age_seconds=fresh.get("age_seconds"),
        stale_threshold_seconds=fresh.get("stale_threshold_seconds"),
        expiry_threshold_seconds=fresh.get("expiry_threshold_seconds"),
        advisory_status=fresh.get("advisory_status"),
        freshness=fresh.get("freshness"),
        quality="PARTIAL" if missing else "COMPLETE",
        completeness_pct=round(100.0 * (3 - len(missing)) / 3.0, 2),
        missing_fields=missing,
        failure_reason=raw.get("failure_reason") or fresh.get("stale_reason"),
        symbol=symbol,
        canonical_symbol=norm["canonical"],
        provider_native_symbol=raw.get("provider_native_symbol") or norm.get("provider_native"),
        bid=bid,
        ask=ask,
        last=last,
        midpoint=midpoint,
        previous_close=raw.get("previous_close"),
        daily_change=raw.get("daily_change"),
        volume=raw.get("volume"),
        currency=raw.get("currency") or norm.get("currency_hint"),
        market_open=raw.get("market_open"),
        historical_prices=raw.get("historical_prices"),
        realized_volatility=raw.get("realized_volatility"),
    )


__all__ = ["UnderlyingQuoteProvider", "fetch_underlying_market_data"]
