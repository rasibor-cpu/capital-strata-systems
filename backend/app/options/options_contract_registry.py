from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class OptionsContractSpec:
    underlying: str
    option_type: str
    strike: float
    expiry: str
    symbol: str
    asset_class: str
    multiplier: float
    currency: str
    exchange: str
    live_enabled: bool = False
    notes: str = ""


SUPPORTED_OPTION_UNDERLYINGS: Dict[str, dict] = {
    "SPY": {
        "exchange": "OPRA",
        "multiplier": 100.0,
        "currency": "USD",
        "notes": "ETF options. Live execution disabled until options broker adapter is approved.",
    },
    "QQQ": {
        "exchange": "OPRA",
        "multiplier": 100.0,
        "currency": "USD",
        "notes": "ETF options. Live execution disabled until options broker adapter is approved.",
    },
    "AAPL": {
        "exchange": "OPRA",
        "multiplier": 100.0,
        "currency": "USD",
        "notes": "Equity options. Live execution disabled until options broker adapter is approved.",
    },
}


def normalize_option_underlying(underlying: str) -> str:
    return str(underlying or "").strip().upper()


def normalize_option_type(option_type: str) -> str:
    value = str(option_type or "").strip().upper()
    if value in {"C", "CALL"}:
        return "CALL"
    if value in {"P", "PUT"}:
        return "PUT"
    return value


def build_option_symbol(
    *,
    underlying: str,
    option_type: str,
    strike: float,
    expiry: str,
) -> str:
    normalized_underlying = normalize_option_underlying(underlying)
    normalized_type = normalize_option_type(option_type)
    strike_value = float(strike)
    expiry_value = str(expiry or "").strip()

    type_code = "C" if normalized_type == "CALL" else "P" if normalized_type == "PUT" else normalized_type

    if strike_value.is_integer():
        strike_text = str(int(strike_value))
    else:
        strike_text = str(strike_value)

    if not expiry_value or expiry_value.upper() == "TBD":
        return f"{normalized_underlying}-{type_code}-{strike_text}"

    return f"{normalized_underlying}-{type_code}-{strike_text}-{expiry_value}"


def parse_simple_option_symbol(symbol: str) -> Optional[OptionsContractSpec]:
    """
    Parses simple CSS option symbols such as:
    - SPY-C-500
    - QQQ-C-400
    - AAPL-C-175

    If expiry is not present, expiry is marked as TBD.
    """

    raw = str(symbol or "").strip().upper()
    parts = raw.split("-")

    if len(parts) < 3:
        return None

    underlying = normalize_option_underlying(parts[0])
    option_type = normalize_option_type(parts[1])

    try:
        strike = float(parts[2])
    except Exception:
        return None

    expiry = parts[3] if len(parts) >= 4 else "TBD"

    return build_options_contract(
        underlying=underlying,
        option_type=option_type,
        strike=strike,
        expiry=expiry,
    )


def build_options_contract(
    *,
    underlying: str,
    option_type: str,
    strike: float,
    expiry: str = "TBD",
) -> Optional[OptionsContractSpec]:

    normalized_underlying = normalize_option_underlying(underlying)
    metadata = SUPPORTED_OPTION_UNDERLYINGS.get(normalized_underlying)

    if metadata is None:
        return None

    normalized_type = normalize_option_type(option_type)
    if normalized_type not in {"CALL", "PUT"}:
        return None

    symbol = build_option_symbol(
        underlying=normalized_underlying,
        option_type=normalized_type,
        strike=float(strike),
        expiry=expiry,
    )

    return OptionsContractSpec(
        underlying=normalized_underlying,
        option_type=normalized_type,
        strike=float(strike),
        expiry=str(expiry or "TBD"),
        symbol=symbol,
        asset_class="OPTIONS",
        multiplier=float(metadata["multiplier"]),
        currency=str(metadata["currency"]),
        exchange=str(metadata["exchange"]),
        live_enabled=False,
        notes=str(metadata.get("notes", "")),
    )


def get_options_contract(symbol: str) -> Optional[OptionsContractSpec]:
    return parse_simple_option_symbol(symbol)


def is_supported_options_contract(symbol: str) -> bool:
    return get_options_contract(symbol) is not None


def options_contract_summary(symbol: str) -> dict:
    contract = get_options_contract(symbol)

    if contract is None:
        return {
            "supported": False,
            "symbol": str(symbol or "").strip().upper(),
            "reason": "UNKNOWN_OR_UNSUPPORTED_OPTIONS_CONTRACT",
        }

    return {
        "supported": True,
        "symbol": contract.symbol,
        "underlying": contract.underlying,
        "option_type": contract.option_type,
        "strike": contract.strike,
        "expiry": contract.expiry,
        "asset_class": contract.asset_class,
        "multiplier": contract.multiplier,
        "currency": contract.currency,
        "exchange": contract.exchange,
        "live_enabled": contract.live_enabled,
        "notes": contract.notes,
    }
