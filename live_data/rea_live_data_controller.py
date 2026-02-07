"""
REA Live Data Controller (Provider-Agnostic)

Responsibilities:
- Strategy Concept -> Canonical REA Instrument
- Canonical REA Instrument -> Provider Symbol (via JSON map)
- Snapshot fetching via provider adapters
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

# Existing Alpaca crypto adapter
from live_data.alpaca_client import quotes, CryptoLatestQuoteRequest

# OANDA broker adapter
import broker_oanda


DEFAULT_MAP_PATH = Path("data") / "provider_symbol_map.json"


# -------------------------------------------------
# Provider Symbol Mapping
# -------------------------------------------------

def load_provider_symbol_map(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Provider map not found: {path}. "
            "Create it (data/provider_symbol_map.json)."
        )

    with open(path, "r") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError("provider_symbol_map.json must be a JSON object.")

    return raw


def resolve_provider_symbol(
    provider: str,
    rea_instrument: str,
    mapping: Dict[str, Dict[str, str]],
) -> str:

    prov_map = mapping.get(provider)
    if not prov_map:
        raise KeyError(f"No mappings found for provider '{provider}'.")

    symbol = prov_map.get(rea_instrument)
    if not symbol:
        raise KeyError(
            f"Missing mapping for rea_instrument='{rea_instrument}' "
            f"under provider='{provider}'."
        )

    return symbol


# -------------------------------------------------
# Alpaca Crypto Adapter
# -------------------------------------------------

def alpaca_crypto_snapshot(provider_symbol: str) -> Dict[str, Any]:
    req = CryptoLatestQuoteRequest(symbol_or_symbols=provider_symbol)
    q = quotes.get(provider_symbol)

    if not q:
        raise RuntimeError(f"No quote returned for {provider_symbol}")

    return {
        "bid": float(q.bid_price),
        "ask": float(q.ask_price),
        "provider": "alpaca",
        "symbol": provider_symbol,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# -------------------------------------------------
# OANDA FX Adapter
# -------------------------------------------------

def oanda_fx_snapshot(provider_symbol: str) -> Dict[str, Any]:

    token = os.environ.get("OANDA_TOKEN")
    account_id = os.environ.get("OANDA_ACCOUNT_ID")

    if not token or not account_id:
        raise RuntimeError("OANDA_TOKEN or OANDA_ACCOUNT_ID not set.")

    pricing = broker_oanda.get_pricing(
        account_id=account_id,
        token=token,
        instruments=provider_symbol,
    )

    prices = pricing.get("prices")
    if not prices:
        raise RuntimeError("No prices returned from OANDA.")

    p = prices[0]

    bid = float(p["bids"][0]["price"])
    ask = float(p["asks"][0]["price"])

    return {
        "bid": bid,
        "ask": ask,
        "provider": "oanda",
        "symbol": provider_symbol,
        "timestamp": p["time"],
    }


# -------------------------------------------------
# Snapshot Router
# -------------------------------------------------

def fetch_snapshot(provider: str, provider_symbol: str) -> Dict[str, Any]:

    provider = provider.lower().strip()

    if provider == "alpaca":
        return alpaca_crypto_snapshot(provider_symbol)

    if provider == "oanda":
        return oanda_fx_snapshot(provider_symbol)

    raise ValueError(
        f"Unsupported provider '{provider}'. "
        "Implement adapter in this controller."
    )
