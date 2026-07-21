"""Phase 178A — Canonical Options Income advisory data contracts.

Provider-neutral, read-only envelopes. Demonstration/fixture data must never be
labelled as live or current market data.
"""

from __future__ import annotations

import uuid
from typing import Any, Mapping

SCHEMA_VERSION = "css.options_income.advisory_data.v1"

PROVENANCE = (
    "BROKER",
    "MARKET_DATA_PROVIDER",
    "OPTION_CHAIN_PROVIDER",
    "ACCOUNT_HOLDINGS",
    "ACCOUNTING",
    "HISTORICAL",
    "CACHE",
    "CONFIGURATION",
    "DERIVED",
    "DEMONSTRATION",
)

MARKET_DATA_STATES = (
    "READY",
    "STALE",
    "PARTIAL_DATA",
    "PROVIDER_UNAVAILABLE",
    "SYMBOL_UNSUPPORTED",
    "MARKET_CLOSED",
    "FAILED",
    "NOT_CONFIGURED",
)

CHAIN_STATES = (
    "READY",
    "STALE",
    "PARTIAL_DATA",
    "PROVIDER_UNAVAILABLE",
    "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED",
    "SYMBOL_UNSUPPORTED",
    "INCOMPLETE",
    "FAILED",
    "NOT_CONFIGURED",
)

HOLDINGS_STATES = (
    "READY",
    "STALE",
    "PARTIAL_DATA",
    "PROVIDER_UNAVAILABLE",
    "CONFIGURATION_REQUIRED",
    "FAILED",
    "NOT_CONFIGURED",
)

GREEKS_ORIGIN = ("PROVIDER", "DERIVED", "MISSING")


def _base(
    *,
    status: str,
    provenance: str,
    generated_at: str,
    provider_timestamp: str | None = None,
    received_at: str | None = None,
    age_seconds: float | None = None,
    freshness: str = "UNKNOWN",
    quality: str = "UNKNOWN",
    completeness_pct: float | None = None,
    missing_fields: list[str] | None = None,
    failure_reason: str | None = None,
    correlation_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "provenance": provenance,
        "generated_at": generated_at,
        "provider_timestamp": provider_timestamp,
        "received_at": received_at or generated_at,
        "age_seconds": age_seconds,
        "freshness": freshness,
        "quality": quality,
        "completeness_pct": completeness_pct,
        "missing_fields": list(missing_fields or []),
        "quality_flags": [],
        "failure_reason": failure_reason,
        "correlation_id": correlation_id,
        "advisory_only": True,
        "execution_allowed": False,
        "demonstration": provenance == "DEMONSTRATION",
    }
    if extra:
        payload.update(dict(extra))
    return payload


def market_data_envelope(**kwargs: Any) -> dict[str, Any]:
    """Underlying quote contract."""
    return _base(
        **{
            "status": kwargs.get("status", "NOT_CONFIGURED"),
            "provenance": kwargs.get("provenance", "CONFIGURATION"),
            "generated_at": kwargs["generated_at"],
            "provider_timestamp": kwargs.get("provider_timestamp"),
            "received_at": kwargs.get("received_at"),
            "age_seconds": kwargs.get("age_seconds"),
            "freshness": kwargs.get("freshness", "UNKNOWN"),
            "quality": kwargs.get("quality", "UNKNOWN"),
            "completeness_pct": kwargs.get("completeness_pct"),
            "missing_fields": kwargs.get("missing_fields"),
            "failure_reason": kwargs.get("failure_reason"),
            "correlation_id": kwargs.get("correlation_id"),
            "extra": {
                "symbol": kwargs.get("symbol"),
                "canonical_symbol": kwargs.get("canonical_symbol"),
                "provider_native_symbol": kwargs.get("provider_native_symbol"),
                "bid": kwargs.get("bid"),
                "ask": kwargs.get("ask"),
                "last": kwargs.get("last"),
                "midpoint": kwargs.get("midpoint"),
                "previous_close": kwargs.get("previous_close"),
                "daily_change": kwargs.get("daily_change"),
                "volume": kwargs.get("volume"),
                "currency": kwargs.get("currency"),
                "market_open": kwargs.get("market_open"),
                "historical_prices": kwargs.get("historical_prices"),
                "realized_volatility": kwargs.get("realized_volatility"),
                "contract": "underlying_market_data",
            },
        }
    )


def option_chain_envelope(**kwargs: Any) -> dict[str, Any]:
    return _base(
        **{
            "status": kwargs.get("status", "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED"),
            "provenance": kwargs.get("provenance", "CONFIGURATION"),
            "generated_at": kwargs["generated_at"],
            "provider_timestamp": kwargs.get("provider_timestamp"),
            "received_at": kwargs.get("received_at"),
            "age_seconds": kwargs.get("age_seconds"),
            "freshness": kwargs.get("freshness", "UNKNOWN"),
            "quality": kwargs.get("quality", "UNKNOWN"),
            "completeness_pct": kwargs.get("completeness_pct"),
            "missing_fields": kwargs.get("missing_fields"),
            "failure_reason": kwargs.get("failure_reason"),
            "correlation_id": kwargs.get("correlation_id"),
            "extra": {
                "underlying_symbol": kwargs.get("underlying_symbol"),
                "canonical_underlying": kwargs.get("canonical_underlying"),
                "expirations": list(kwargs.get("expirations") or []),
                "strikes": list(kwargs.get("strikes") or []),
                "calls": list(kwargs.get("calls") or []),
                "puts": list(kwargs.get("puts") or []),
                "contract_count": int(kwargs.get("contract_count") or 0),
                "greeks_origin": kwargs.get("greeks_origin", "MISSING"),
                "currency": kwargs.get("currency"),
                "exchange": kwargs.get("exchange"),
                "multiplier": kwargs.get("multiplier", 100),
                "exercise_style": kwargs.get("exercise_style"),
                "contract": "option_chain",
            },
        }
    )


def holdings_envelope(**kwargs: Any) -> dict[str, Any]:
    return _base(
        **{
            "status": kwargs.get("status", "NOT_CONFIGURED"),
            "provenance": kwargs.get("provenance", "CONFIGURATION"),
            "generated_at": kwargs["generated_at"],
            "provider_timestamp": kwargs.get("provider_timestamp"),
            "received_at": kwargs.get("received_at"),
            "age_seconds": kwargs.get("age_seconds"),
            "freshness": kwargs.get("freshness", "UNKNOWN"),
            "quality": kwargs.get("quality", "UNKNOWN"),
            "completeness_pct": kwargs.get("completeness_pct"),
            "missing_fields": kwargs.get("missing_fields"),
            "failure_reason": kwargs.get("failure_reason"),
            "correlation_id": kwargs.get("correlation_id"),
            "extra": {
                "broker": kwargs.get("broker"),
                "account_id_sanitized": kwargs.get("account_id_sanitized"),
                "account_type": kwargs.get("account_type"),
                "base_currency": kwargs.get("base_currency"),
                "cash": kwargs.get("cash"),
                "buying_power": kwargs.get("buying_power"),
                "equity": kwargs.get("equity"),
                "holdings": list(kwargs.get("holdings") or []),
                "option_positions": list(kwargs.get("option_positions") or []),
                "short_positions": list(kwargs.get("short_positions") or []),
                "restricted_positions": list(kwargs.get("restricted_positions") or []),
                "contract": "account_holdings",
            },
        }
    )


def collateral_envelope(**kwargs: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": "collateral",
        "status": kwargs.get("status", "UNAVAILABLE"),
        "authority_level": kwargs.get("authority_level", "UNAVAILABLE"),
        "source": kwargs.get("source", "UNAVAILABLE"),
        "provenance": kwargs.get("provenance", "CONFIGURATION"),
        "currency": kwargs.get("currency"),
        "value": kwargs.get("value"),
        "calculation_basis": kwargs.get("calculation_basis"),
        "timestamp": kwargs.get("timestamp") or kwargs.get("generated_at"),
        "generated_at": kwargs["generated_at"],
        "haircut_or_reserve": kwargs.get("haircut_or_reserve"),
        "broker_confirmed": bool(kwargs.get("broker_confirmed", False)),
        "css_derived": bool(kwargs.get("css_derived", False)),
        "rejects_simulated_10000_fixture": True,
        "advisory_only": True,
        "execution_allowed": False,
        "failure_reason": kwargs.get("failure_reason"),
    }


def unexpected_advisory_fault(exc: Exception) -> dict[str, str]:
    """Return a correlation-safe boundary result without provider exception text."""
    return {
        "failure_reason": "UNEXPECTED_PROVIDER_FAULT",
        "fault_type": type(exc).__name__,
        "correlation_id": uuid.uuid4().hex,
    }


def broker_capability_truth() -> dict[str, Any]:
    """Honest Tier-1 options capability map — no fabricated listed-options support."""
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": "broker_capability_truth",
        "brokers": {
            "COINBASE": {
                "listed_equity_options": False,
                "role": "cryptocurrency market and account data",
                "note": "No North American listed-equity option chains",
            },
            "BINANCE": {
                "listed_equity_options": False,
                "role": "cryptocurrency market and account data",
                "note": "No standard North American listed-equity option chains",
            },
            "OANDA": {
                "listed_equity_options": False,
                "role": "FX market and account data",
                "note": "No listed-equity option chains",
            },
            "QUESTRADE": {
                "listed_equity_options": True,
                "role": "Canadian/U.S. securities, holdings, listed options when adapter authenticated",
                "adapter_state": "CONFIGURATION_REQUIRED",
                "note": "Capability declared; executable advisory connectivity requires credentials",
            },
        },
        "ibkr_registered": False,
        "alpaca_tier1": False,
        "provenance": "BROKER|CONFIGURATION",
        "advisory_only": True,
    }


__all__ = [
    "CHAIN_STATES",
    "GREEKS_ORIGIN",
    "HOLDINGS_STATES",
    "MARKET_DATA_STATES",
    "PROVENANCE",
    "SCHEMA_VERSION",
    "broker_capability_truth",
    "collateral_envelope",
    "holdings_envelope",
    "market_data_envelope",
    "option_chain_envelope",
    "unexpected_advisory_fault",
]
