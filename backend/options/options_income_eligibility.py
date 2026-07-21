"""Phase 178A — covered-call and cash-secured-put eligibility (advisory)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


SHARES_PER_CONTRACT = 100


def evaluate_covered_call_eligibility(
    *,
    underlying: str,
    holdings: Mapping[str, Any] | None,
    chain: Mapping[str, Any] | None = None,
    broker_supports_listed_options: bool = False,
) -> dict[str, Any]:
    """Validate share coverage without inventing holdings."""
    reasons: list[str] = []
    hold = dict(holdings or {})
    if str(hold.get("status") or "").upper() in {"NOT_CONFIGURED", "FAILED", "CONFIGURATION_REQUIRED", ""}:
        reasons.append("holdings_unavailable")
    if not broker_supports_listed_options:
        reasons.append("broker_lacks_listed_options_capability")

    rows = list(hold.get("holdings") or [])
    match = None
    for row in rows:
        if str(row.get("symbol") or "").upper() == str(underlying or "").upper():
            match = row
            break
    if match is None:
        reasons.append("underlying_not_held")
        qty = 0.0
        encumbered = 0.0
    else:
        try:
            qty = float(match.get("quantity") or 0.0)
        except (TypeError, ValueError):
            qty = 0.0
            reasons.append("quantity_unparseable")
        try:
            encumbered = float(match.get("encumbered_quantity") or 0.0)
        except (TypeError, ValueError):
            encumbered = 0.0
        if bool(match.get("restricted")):
            reasons.append("position_restricted")

    free = max(0.0, qty - encumbered)
    contracts = int(free // SHARES_PER_CONTRACT)
    if contracts < 1:
        reasons.append("insufficient_unencumbered_shares")

    chain_status = str((chain or {}).get("status") or "").upper()
    if chain_status in {"STALE", "FAILED", "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED", "INCOMPLETE"}:
        reasons.append(f"option_chain_{chain_status.lower()}")

    eligible = not reasons
    return {
        "strategy": "COVERED_CALL",
        "underlying": underlying,
        "eligible": eligible,
        "free_shares": free,
        "contracts_available": contracts if eligible else 0,
        "exclusion_reasons": reasons,
        "advisory_only": True,
        "execution_allowed": False,
        "provenance": "ACCOUNT_HOLDINGS|DERIVED",
    }


def evaluate_cash_secured_put_eligibility(
    *,
    strike: float,
    multiplier: int = 100,
    collateral: Mapping[str, Any] | None,
    chain: Mapping[str, Any] | None = None,
    broker_supports_listed_options: bool = False,
    currency: str | None = None,
    reserve_haircut: float = 0.0,
) -> dict[str, Any]:
    """Require traceable collateral — never claim cash-secured without a source."""
    reasons: list[str] = []
    coll = dict(collateral or {})
    if not broker_supports_listed_options:
        reasons.append("broker_lacks_listed_options_capability")

    auth = str(coll.get("authority_level") or "UNAVAILABLE")
    if auth == "UNAVAILABLE" or coll.get("value") is None:
        reasons.append("collateral_unavailable")
    if not coll.get("source") or coll.get("source") == "UNAVAILABLE":
        reasons.append("collateral_source_missing")

    required = float(strike) * int(multiplier)
    available = None
    try:
        available = float(coll["value"]) if coll.get("value") is not None else None
    except (TypeError, ValueError):
        reasons.append("collateral_value_unparseable")
        available = None

    if available is not None:
        usable = available * (1.0 - float(reserve_haircut or 0.0))
        if usable < required:
            reasons.append("insufficient_collateral")
    else:
        usable = None

    chain_status = str((chain or {}).get("status") or "").upper()
    if chain_status in {"STALE", "FAILED", "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED", "INCOMPLETE"}:
        reasons.append(f"option_chain_{chain_status.lower()}")

    if currency and coll.get("currency") and str(currency).upper() != str(coll.get("currency")).upper():
        reasons.append("currency_mismatch_fx_not_applied")

    eligible = not reasons
    return {
        "strategy": "CASH_SECURED_PUT",
        "eligible": eligible,
        "required_collateral": required,
        "available_collateral": available,
        "usable_collateral": usable,
        "collateral_authority": auth,
        "collateral_source": coll.get("source"),
        "currency": coll.get("currency") or currency,
        "exclusion_reasons": reasons,
        "advisory_only": True,
        "execution_allowed": False,
        "provenance": "ACCOUNT_HOLDINGS|BROKER|DERIVED",
    }


def summarize_exclusions(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "rejected_count": len(rows),
        "reasons": sorted({r for row in rows for r in list(row.get("exclusion_reasons") or [])}),
        "advisory_only": True,
    }


__all__ = [
    "SHARES_PER_CONTRACT",
    "evaluate_cash_secured_put_eligibility",
    "evaluate_covered_call_eligibility",
    "summarize_exclusions",
]
