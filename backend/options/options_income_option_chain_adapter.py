"""Phase 178A — provider-neutral option-chain adapter (read-only)."""

from __future__ import annotations

from typing import Any, Protocol

from backend.options.options_income_advisory_contracts import option_chain_envelope, unexpected_advisory_fault
from backend.options.options_income_freshness import evaluate_freshness, utc_now
from backend.options.options_income_symbol_normalization import normalize_equity_symbol


class OptionChainProvider(Protocol):
    def get_option_chain(self, underlying: str) -> dict[str, Any]: ...


def fetch_option_chain(
    underlying: str,
    *,
    provider: OptionChainProvider | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Retrieve option chain; never fabricate contracts or scrape unapproved sources."""
    ts = generated_at or utc_now()
    norm = normalize_equity_symbol(underlying)

    if not norm.get("listed_options_eligible_symbol"):
        return option_chain_envelope(
            generated_at=ts,
            status="SYMBOL_UNSUPPORTED",
            provenance="CONFIGURATION",
            failure_reason="symbol_not_eligible_for_listed_equity_options",
            underlying_symbol=underlying,
            canonical_underlying=norm.get("canonical"),
            greeks_origin="MISSING",
        )

    if provider is None:
        return option_chain_envelope(
            generated_at=ts,
            status="OPTION_CHAIN_PROVIDER_NOT_CONFIGURED",
            provenance="CONFIGURATION",
            failure_reason="OPTION_CHAIN_PROVIDER_NOT_CONFIGURED",
            underlying_symbol=underlying,
            canonical_underlying=norm.get("canonical"),
            greeks_origin="MISSING",
            missing_fields=["expirations", "strikes", "calls", "puts"],
        )

    try:
        raw = dict(provider.get_option_chain(str(norm["canonical"])) or {})
    except Exception as exc:  # noqa: BLE001
        fault = unexpected_advisory_fault(exc)
        return option_chain_envelope(
            generated_at=ts,
            status="FAILED",
            provenance="OPTION_CHAIN_PROVIDER",
            failure_reason=fault["failure_reason"],
            correlation_id=fault["correlation_id"],
            underlying_symbol=underlying,
            canonical_underlying=norm.get("canonical"),
            greeks_origin="MISSING",
        )

    if raw.get("demonstration") or str(raw.get("provenance") or "").upper() == "DEMONSTRATION":
        return option_chain_envelope(
            generated_at=ts,
            status="FAILED",
            provenance="DEMONSTRATION",
            failure_reason="demonstration_chain_rejected_as_live",
            underlying_symbol=underlying,
            canonical_underlying=norm.get("canonical"),
            greeks_origin="MISSING",
        )

    provider_ts = raw.get("quote_timestamp") or raw.get("provider_timestamp") or raw.get("timestamp")
    fresh = evaluate_freshness("option_chain_quote", provider_timestamp=provider_ts, now=ts)
    calls = list(raw.get("calls") or [])
    puts = list(raw.get("puts") or [])
    expirations = list(raw.get("expirations") or raw.get("expiries") or [])
    strikes = list(raw.get("strikes") or [])
    missing: list[str] = []
    if not calls:
        missing.append("calls")
    if not puts:
        missing.append("puts")
    if not expirations:
        missing.append("expirations")

    greeks_origin = str(raw.get("greeks_origin") or "MISSING").upper()
    if greeks_origin not in {"PROVIDER", "DERIVED", "MISSING"}:
        greeks_origin = "MISSING"

    status = str(raw.get("status") or "READY").upper()
    if fresh["stale"]:
        status = "STALE"
    elif missing:
        status = "PARTIAL_DATA" if (calls or puts) else "INCOMPLETE"

    return option_chain_envelope(
        generated_at=ts,
        status=status,
        provenance=str(raw.get("provenance") or "OPTION_CHAIN_PROVIDER"),
        provider_timestamp=provider_ts,
        received_at=ts,
        age_seconds=fresh.get("age_seconds"),
        freshness=fresh.get("freshness"),
        quality="PARTIAL" if missing else "COMPLETE",
        completeness_pct=None,
        missing_fields=missing,
        failure_reason=raw.get("failure_reason") or fresh.get("stale_reason"),
        underlying_symbol=underlying,
        canonical_underlying=norm.get("canonical"),
        expirations=expirations,
        strikes=strikes,
        calls=calls,
        puts=puts,
        contract_count=len(calls) + len(puts),
        greeks_origin=greeks_origin,
        currency=raw.get("currency"),
        exchange=raw.get("exchange"),
        multiplier=raw.get("multiplier", 100),
        exercise_style=raw.get("exercise_style"),
    )


__all__ = ["OptionChainProvider", "fetch_option_chain"]
