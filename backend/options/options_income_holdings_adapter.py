"""Phase 178A — canonical read-only holdings adapter."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from backend.options.options_income_advisory_contracts import holdings_envelope, unexpected_advisory_fault
from backend.options.options_income_freshness import evaluate_freshness, utc_now
from backend.options.options_income_symbol_normalization import normalize_equity_symbol


class HoldingsProvider(Protocol):
    def get_holdings_snapshot(self) -> dict[str, Any]: ...


def _sanitize_account_id(raw: Any) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if len(text) <= 4:
        return "***"
    return f"***{text[-4:]}"


def fetch_account_holdings(
    *,
    provider: HoldingsProvider | None = None,
    broker: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ts = generated_at or utc_now()
    if provider is None:
        return holdings_envelope(
            generated_at=ts,
            status="NOT_CONFIGURED",
            provenance="CONFIGURATION",
            failure_reason="ACCOUNT_HOLDINGS_PROVIDER_NOT_CONFIGURED",
            broker=broker,
            account_id_sanitized=None,
            missing_fields=["cash", "holdings", "buying_power"],
        )

    try:
        raw = dict(provider.get_holdings_snapshot() or {})
    except Exception as exc:  # noqa: BLE001
        fault = unexpected_advisory_fault(exc)
        return holdings_envelope(
            generated_at=ts,
            status="FAILED",
            provenance="BROKER",
            failure_reason=fault["failure_reason"],
            correlation_id=fault["correlation_id"],
            broker=broker,
        )

    if raw.get("demonstration") or str(raw.get("provenance") or "").upper() == "DEMONSTRATION":
        return holdings_envelope(
            generated_at=ts,
            status="FAILED",
            provenance="DEMONSTRATION",
            failure_reason="demonstration_holdings_rejected_as_live",
            broker=broker,
        )

    provider_ts = raw.get("timestamp") or raw.get("provider_timestamp")
    fresh = evaluate_freshness("holdings", provider_timestamp=provider_ts, now=ts)
    holdings_rows = []
    for row in list(raw.get("holdings") or []):
        if not isinstance(row, Mapping):
            continue
        sym = normalize_equity_symbol(str(row.get("symbol") or ""))
        holdings_rows.append(
            {
                "symbol": sym.get("canonical"),
                "provider_native_symbol": row.get("symbol"),
                "quantity": row.get("quantity"),
                "average_cost": row.get("average_cost"),
                "market_value": row.get("market_value"),
                "currency": row.get("currency"),
                "restricted": bool(row.get("restricted")),
                "encumbered_quantity": row.get("encumbered_quantity") or 0,
            }
        )

    status = str(raw.get("status") or "READY").upper()
    if fresh["stale"]:
        status = "STALE"

    missing = []
    if raw.get("cash") is None:
        missing.append("cash")
    if not holdings_rows and not raw.get("option_positions"):
        missing.append("holdings")

    return holdings_envelope(
        generated_at=ts,
        status=status if not missing else ("PARTIAL_DATA" if status == "READY" else status),
        provenance=str(raw.get("provenance") or "ACCOUNT_HOLDINGS"),
        provider_timestamp=provider_ts,
        received_at=ts,
        age_seconds=fresh.get("age_seconds"),
        freshness=fresh.get("freshness"),
        quality="PARTIAL" if missing else "COMPLETE",
        missing_fields=missing,
        failure_reason=raw.get("failure_reason") or fresh.get("stale_reason"),
        broker=raw.get("broker") or broker,
        account_id_sanitized=_sanitize_account_id(raw.get("account_id") or raw.get("account_number")),
        account_type=raw.get("account_type"),
        base_currency=raw.get("base_currency") or raw.get("currency"),
        cash=raw.get("cash"),
        buying_power=raw.get("buying_power"),
        equity=raw.get("equity"),
        holdings=holdings_rows,
        option_positions=list(raw.get("option_positions") or []),
        short_positions=list(raw.get("short_positions") or []),
        restricted_positions=list(raw.get("restricted_positions") or []),
    )


__all__ = ["HoldingsProvider", "fetch_account_holdings"]
