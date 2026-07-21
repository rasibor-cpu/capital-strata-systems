"""Pure Questrade response-to-canonical read-only mappings."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import secrets
from typing import Any, Mapping, Sequence

from backend.options.options_income_freshness import evaluate_freshness
from backend.options.options_income_symbol_normalization import normalize_equity_symbol

_ACCOUNT_HASH_KEY = secrets.token_bytes(32)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def account_hash(account_number: Any) -> str:
    value = str(account_number or "")
    return hashlib.blake2b(value.encode("utf-8"), key=_ACCOUNT_HASH_KEY, digest_size=12).hexdigest()


def mask_account(account_number: Any) -> str:
    value = str(account_number or "")
    return f"***{value[-4:]}" if value else "UNAVAILABLE"


def account_restrictions(account_type: str | None) -> dict[str, Any]:
    kind = str(account_type or "UNKNOWN").upper()
    registered = kind in {"TFSA", "RRSP", "RESP", "LIRA", "RIF", "LRSP"}
    return {
        "account_type": kind,
        "registered": registered,
        "margin_assumed": kind == "MARGIN",
        "cash_secured_puts_assumed": False,
        "uncovered_options_assumed": False,
        "short_options_assumed": False,
        "requires_broker_confirmation": True,
        "tax_or_legal_advice": False,
    }


def map_accounts(payload: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    ts = generated_at or _utc_now()
    rows = []
    for raw in _rows(payload, "accounts"):
        number = raw.get("number") or raw.get("accountNumber") or raw.get("id")
        kind = str(raw.get("type") or raw.get("accountType") or "UNKNOWN").upper()
        rows.append(
            {
                "account_hash": account_hash(number),
                "masked_identifier": mask_account(number),
                "account_type": kind,
                "status": str(raw.get("status") or "UNKNOWN").upper(),
                "currency": raw.get("currency") or raw.get("baseCurrency"),
                "is_primary": bool(raw.get("isPrimary")),
                "read_only_available": True,
                "restrictions": account_restrictions(kind),
                "provenance": "QUESTRADE_ACCOUNT_DISCOVERY",
            }
        )
    return {
        "status": "ACCOUNT_SELECTION_REQUIRED" if len(rows) != 1 else "ACCOUNT_DISCOVERED",
        "accounts": rows,
        "account_count": len(rows),
        "explicit_selection_required": len(rows) != 1,
        "generated_at": ts,
        "full_account_numbers_returned": False,
        "execution_allowed": False,
    }


def map_balances(
    payload: Mapping[str, Any],
    *,
    account_type: str | None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ts = generated_at or _utc_now()
    rows = _rows(payload, "perCurrencyBalances") or _rows(payload, "combinedBalances") or _rows(payload, "balances")
    balances = [
        {
            "currency": row.get("currency"),
            "cash": row.get("cash"),
            "settled_cash": row.get("settledCash"),
            "available_cash": row.get("availableCash"),
            "equity": row.get("totalEquity") or row.get("equity"),
            "market_value": row.get("marketValue"),
            "buying_power": row.get("buyingPower"),
            "maintenance_excess": row.get("maintenanceExcess"),
            "broker_confirmed": True,
            "provenance": "QUESTRADE_BALANCES",
        }
        for row in rows
    ]
    return {
        "status": "ACCOUNT_READY" if balances else "ACCOUNT_UNAVAILABLE",
        "account_type": str(account_type or "UNKNOWN").upper(),
        "balances": balances,
        "broker_reported_buying_power_is_cash": False,
        "fx_conversion_performed": False,
        "timestamp": payload.get("timestamp"),
        "acquisition_timestamp": ts,
        "provider_timestamp": payload.get("timestamp"),
        "freshness": evaluate_freshness("balances", provider_timestamp=payload.get("timestamp"), now=ts),
        "provenance": "QUESTRADE_BALANCES",
        "execution_allowed": False,
    }


def map_positions(payload: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    ts = generated_at or _utc_now()
    positions = []
    option_positions = []
    for raw in _rows(payload, "positions"):
        symbol = str(raw.get("symbol") or "")
        norm = normalize_equity_symbol(symbol)
        security_type = str(raw.get("securityType") or raw.get("security_type") or "UNKNOWN").upper()
        row = {
            "symbol": norm.get("canonical"),
            "provider_native_symbol": symbol,
            "security_type": security_type,
            "quantity": raw.get("currentQuantity"),
            "open_quantity": raw.get("openQuantity"),
            "encumbered_quantity": raw.get("encumberedQuantity"),
            "average_cost": raw.get("averageEntryPrice"),
            "current_price": raw.get("currentPrice"),
            "market_value": raw.get("currentMarketValue"),
            "currency": raw.get("currency"),
            "unrealized_pnl": raw.get("openPnl"),
            "provenance": "QUESTRADE_POSITIONS",
        }
        if security_type == "OPTION" or any(raw.get(k) is not None for k in ("expiryDate", "strikePrice", "optionType")):
            option = {
                **row,
                "expiry": raw.get("expiryDate"),
                "strike": raw.get("strikePrice"),
                "option_type": str(raw.get("optionType") or "UNKNOWN").upper(),
                "side": "LONG" if (raw.get("currentQuantity") or 0) > 0 else "SHORT",
                "contract_multiplier": raw.get("multiplier") or 100,
            }
            option_positions.append(option)
        else:
            positions.append(row)
    return {
        "status": "HOLDINGS_READY",
        "holdings": positions,
        "option_positions": option_positions,
        "position_count": len(positions) + len(option_positions),
        "timestamp": payload.get("timestamp"),
        "acquisition_timestamp": ts,
        "provider_timestamp": payload.get("timestamp"),
        "freshness": evaluate_freshness("holdings", provider_timestamp=payload.get("timestamp"), now=ts),
        "provenance": "QUESTRADE_POSITIONS",
        "execution_allowed": False,
    }


def map_quotes(payload: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    ts = generated_at or _utc_now()
    quotes = []
    for raw in _rows(payload, "quotes"):
        bid, ask = raw.get("bidPrice"), raw.get("askPrice")
        midpoint = (float(bid) + float(ask)) / 2 if bid is not None and ask is not None else None
        quotes.append(
            {
                "symbol_id": raw.get("symbolId"),
                "symbol": normalize_equity_symbol(str(raw.get("symbol") or "")).get("canonical"),
                "bid": bid,
                "ask": ask,
                "last": raw.get("lastTradePrice"),
                "midpoint": midpoint,
                "volume": raw.get("volume"),
                "previous_close": raw.get("prevDayClosePrice"),
                "timestamp": raw.get("lastTradeTime") or payload.get("timestamp"),
                "acquisition_timestamp": ts,
                "provider_timestamp": raw.get("lastTradeTime") or payload.get("timestamp"),
                "freshness": evaluate_freshness(
                    "underlying_quote",
                    provider_timestamp=raw.get("lastTradeTime") or payload.get("timestamp"),
                    now=ts,
                ),
                "exchange": raw.get("listingExchange"),
                "currency": raw.get("currency"),
                "market_status": raw.get("isHalted") and "HALTED" or "AVAILABLE",
            }
        )
    return {
        "status": "MARKET_DATA_READY" if quotes else "MARKET_DATA_UNAVAILABLE",
        "quotes": quotes,
        "generated_at": ts,
        "provenance": "QUESTRADE_QUOTES",
        "execution_allowed": False,
    }


def map_option_chain(payload: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    ts = generated_at or _utc_now()
    expirations: list[str] = []
    strikes: list[float] = []
    calls: list[dict[str, Any]] = []
    puts: list[dict[str, Any]] = []
    for expiry in _rows(payload, "optionChain"):
        date = str(expiry.get("expiryDate") or "")
        if date and date not in expirations:
            expirations.append(date)
        roots = expiry.get("chainPerRoot") if isinstance(expiry.get("chainPerRoot"), Sequence) else []
        for root in roots:
            if not isinstance(root, Mapping):
                continue
            for contract in root.get("chainPerStrikePrice") or []:
                if not isinstance(contract, Mapping):
                    continue
                strike = contract.get("strikePrice")
                if strike is not None and float(strike) not in strikes:
                    strikes.append(float(strike))
                for side, key, quote_prefix in (
                    (calls, "callSymbolId", "call"),
                    (puts, "putSymbolId", "put"),
                ):
                    symbol_id = contract.get(key)
                    if symbol_id is not None:
                        side.append(
                            {
                                "symbol_id": symbol_id,
                                "strike": strike,
                                "expiry": date,
                                "bid": contract.get(f"{quote_prefix}Bid")
                                or contract.get("bidPrice"),
                                "ask": contract.get(f"{quote_prefix}Ask")
                                or contract.get("askPrice"),
                                "volume": contract.get("volume"),
                                "open_interest": contract.get("openInterest"),
                                "implied_volatility": contract.get("impliedVolatility"),
                                "delta": contract.get("delta"),
                                "gamma": contract.get("gamma"),
                                "theta": contract.get("theta"),
                                "vega": contract.get("vega"),
                                "rho": contract.get("rho"),
                                "provider_timestamp": contract.get("timestamp")
                                or payload.get("timestamp"),
                                "provenance": "QUESTRADE_OPTION_CHAIN",
                            }
                        )
    provider_greeks = any(
        any(row.get(name) is not None for name in ("delta", "gamma", "theta", "vega", "rho"))
        for row in (*calls, *puts)
    )
    return {
        "status": "OPTION_CHAIN_READY" if expirations and (calls or puts) else "OPTION_CHAIN_UNAVAILABLE",
        "expirations": sorted(expirations),
        "strikes": sorted(strikes),
        "calls": calls,
        "puts": puts,
        "metadata_available": bool(expirations),
        "contract_quotes_available": False,
        "greeks_origin": "PROVIDER" if provider_greeks else "MISSING",
        "provider_greeks_available": provider_greeks,
        "provider_timestamp": payload.get("timestamp"),
        "acquisition_timestamp": ts,
        "freshness": evaluate_freshness(
            "option_chain_quote",
            provider_timestamp=payload.get("timestamp"),
            now=ts,
        ),
        "expiration_calendar": sorted(expirations),
        "generated_at": ts,
        "provenance": "QUESTRADE_OPTION_CHAIN_METADATA",
        "execution_allowed": False,
    }


def _rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


__all__ = [
    "account_hash",
    "account_restrictions",
    "map_accounts",
    "map_balances",
    "map_option_chain",
    "map_positions",
    "map_quotes",
    "mask_account",
]
