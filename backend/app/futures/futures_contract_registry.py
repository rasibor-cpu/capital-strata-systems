from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class FuturesContractSpec:
    symbol: str
    name: str
    exchange: str
    asset_class: str
    tick_size: float
    tick_value: float
    multiplier: float
    currency: str
    margin_class: str
    live_enabled: bool = False
    notes: str = ""


FUTURES_CONTRACTS: Dict[str, FuturesContractSpec] = {
    "ES": FuturesContractSpec(
        symbol="ES",
        name="E-mini S&P 500",
        exchange="CME",
        asset_class="FUTURES",
        tick_size=0.25,
        tick_value=12.50,
        multiplier=50.0,
        currency="USD",
        margin_class="EQUITY_INDEX",
        notes="Live execution disabled until futures broker adapter is approved.",
    ),
    "NQ": FuturesContractSpec(
        symbol="NQ",
        name="E-mini Nasdaq 100",
        exchange="CME",
        asset_class="FUTURES",
        tick_size=0.25,
        tick_value=5.00,
        multiplier=20.0,
        currency="USD",
        margin_class="EQUITY_INDEX",
        notes="Live execution disabled until futures broker adapter is approved.",
    ),
    "CL": FuturesContractSpec(
        symbol="CL",
        name="Crude Oil WTI",
        exchange="NYMEX",
        asset_class="FUTURES",
        tick_size=0.01,
        tick_value=10.00,
        multiplier=1000.0,
        currency="USD",
        margin_class="ENERGY",
        notes="Live execution disabled until futures broker adapter is approved.",
    ),
    "GC": FuturesContractSpec(
        symbol="GC",
        name="Gold",
        exchange="COMEX",
        asset_class="FUTURES",
        tick_size=0.10,
        tick_value=10.00,
        multiplier=100.0,
        currency="USD",
        margin_class="METALS",
        notes="Live execution disabled until futures broker adapter is approved.",
    ),
    "ZN": FuturesContractSpec(
        symbol="ZN",
        name="10-Year Treasury Note",
        exchange="CBOT",
        asset_class="FUTURES",
        tick_size=0.015625,
        tick_value=15.625,
        multiplier=1000.0,
        currency="USD",
        margin_class="RATES",
        notes="Live execution disabled until futures broker adapter is approved.",
    ),
    "6E": FuturesContractSpec(
        symbol="6E",
        name="Euro FX Futures",
        exchange="CME",
        asset_class="FUTURES",
        tick_size=0.00005,
        tick_value=6.25,
        multiplier=125000.0,
        currency="USD",
        margin_class="FX_FUTURES",
        notes="Live execution disabled until futures broker adapter is approved.",
    ),
}


def normalize_futures_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def get_futures_contract(symbol: str) -> Optional[FuturesContractSpec]:
    return FUTURES_CONTRACTS.get(normalize_futures_symbol(symbol))


def is_supported_futures_contract(symbol: str) -> bool:
    return get_futures_contract(symbol) is not None


def futures_contract_summary(symbol: str) -> dict:
    contract = get_futures_contract(symbol)
    if contract is None:
        return {
            "supported": False,
            "symbol": normalize_futures_symbol(symbol),
            "reason": "UNKNOWN_FUTURES_CONTRACT",
        }

    return {
        "supported": True,
        "symbol": contract.symbol,
        "name": contract.name,
        "exchange": contract.exchange,
        "asset_class": contract.asset_class,
        "tick_size": contract.tick_size,
        "tick_value": contract.tick_value,
        "multiplier": contract.multiplier,
        "currency": contract.currency,
        "margin_class": contract.margin_class,
        "live_enabled": contract.live_enabled,
        "notes": contract.notes,
    }
