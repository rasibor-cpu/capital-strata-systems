"""
REA Live Data Controller (Provider-Agnostic)
--------------------------------------------

Purpose:
- Fetch a single "snapshot" quote from a selected provider using a canonical REA instrument.
- Provider symbol mappings are governance-controlled via JSON map:
    data/provider_symbol_map.json
  Structure:
    {
      "alpaca": {"REA:CRYPTO:BTCUSD": "BTC/USD"},
      "oanda":  {"REA:FX:EURUSD": "EUR_USD"}
    }

Safe behavior:
- If mapping file is missing, we attempt a best-effort fallback symbol format.
- Uses stdlib HTTP (urllib) to avoid extra dependency issues.

Env vars:
- Alpaca:
    APCA_API_KEY_ID
    APCA_API_SECRET_KEY
- OANDA:
    OANDA_API_TOKEN   (preferred)
    OANDA_TOKEN       (fallback)
    OANDA_ACCOUNT_ID
    OANDA_API_URL     (optional; defaults to practice)
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_MAP_PATH = Path("data") / "provider_symbol_map.json"


# -------------------------------------------------------------------
# mapping + symbol handling
# -------------------------------------------------------------------

def load_provider_symbol_map(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("provider_symbol_map.json must be a JSON object at top level.")
    out: Dict[str, Dict[str, str]] = {}
    for provider, mapping in raw.items():
        if not isinstance(provider, str) or not isinstance(mapping, dict):
            continue
        out[provider] = {}
        for rea_inst, prov_sym in mapping.items():
            if isinstance(rea_inst, str) and isinstance(prov_sym, str):
                out[provider][rea_inst] = prov_sym
    return out


def fallback_provider_symbol(provider: str, rea_instrument: str) -> str:
    """
    Best-effort fallback if map is missing.
    REA format examples:
      REA:FX:EURUSD   -> OANDA: EUR_USD
      REA:CRYPTO:BTCUSD -> Alpaca: BTC/USD
    """
    provider = provider.lower().strip()
    parts = rea_instrument.strip().split(":")
    if len(parts) != 3:
        return rea_instrument

    _, asset_class, ticker = parts[0], parts[1].upper(), parts[2].upper()

    if provider == "oanda" and asset_class == "FX" and len(ticker) == 6:
        return f"{ticker[0:3]}_{ticker[3:6]}"
    if provider == "alpaca" and asset_class == "CRYPTO" and len(ticker) >= 6:
        # BTCUSD -> BTC/USD (assume last 3 is quote currency)
        base = ticker[:-3]
        quote = ticker[-3:]
        return f"{base}/{quote}"

    # Default fallback: pass through
    return ticker


def resolve_provider_symbol(provider: str, rea_instrument: str, mapping: Dict[str, Dict[str, str]]) -> str:
    provider = provider.lower().strip()
    prov_map = mapping.get(provider, {})
    if rea_instrument in prov_map:
        return prov_map[rea_instrument]
    return fallback_provider_symbol(provider, rea_instrument)


# -------------------------------------------------------------------
# stdlib HTTP helpers
# -------------------------------------------------------------------

def http_json(url: str, headers: Optional[Dict[str, str]] = None) -> Any:
    hdrs = headers or {}
    req = Request(url, headers=hdrs, method="GET")
    try:
        with urlopen(req, timeout=20) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            return json.loads(data)
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        raise RuntimeError(f"HTTP {e.code} for {url}. Body: {body[:500]}") from e
    except URLError as e:
        raise RuntimeError(f"Network error calling {url}: {e}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Non-JSON response from {url}: {e}") from e


# -------------------------------------------------------------------
# provider implementations
# -------------------------------------------------------------------

def alpaca_crypto_snapshot(provider_symbol: str) -> Dict[str, Any]:
    key_id = os.environ.get("APCA_API_KEY_ID", "").strip()
    secret = os.environ.get("APCA_API_SECRET_KEY", "").strip()

    if not key_id or not secret:
        raise RuntimeError("Alpaca API keys not found in environment. Expected APCA_API_KEY_ID and APCA_API_SECRET_KEY.")

    # Crypto quotes endpoint (works for BTC/USD as you tested)
    url = f"https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes?symbols={provider_symbol}"
    headers = {
        "APCA-API-KEY-ID": key_id,
        "APCA-API-SECRET-KEY": secret,
        "Accept": "application/json",
    }
    payload = http_json(url, headers=headers)

    quotes = payload.get("quotes", {}) if isinstance(payload, dict) else {}
    q = quotes.get(provider_symbol) if isinstance(quotes, dict) else None
    if not isinstance(q, dict):
        raise RuntimeError(f"No quote returned for {provider_symbol}. Payload keys: {list(quotes.keys())[:10]}")

    # Alpaca returns bid/ask as bp/ap (based on your observed response)
    ask = q.get("ap")
    bid = q.get("bp")
    ts = q.get("t")

    return {
        "provider": "alpaca",
        "provider_symbol": provider_symbol,
        "bid": bid,
        "ask": ask,
        "timestamp": ts or datetime.now(timezone.utc).isoformat(),
        "raw": q,
    }


def oanda_fx_snapshot(provider_symbol: str) -> Dict[str, Any]:
    # Token: prefer OANDA_API_TOKEN (as used in your repo), fall back to OANDA_TOKEN
    token = (os.environ.get("OANDA_API_TOKEN") or os.environ.get("OANDA_TOKEN") or "").strip()
    acct = os.environ.get("OANDA_ACCOUNT_ID", "").strip()
    if not token:
        raise RuntimeError("OANDA token not found. Set OANDA_API_TOKEN (preferred) or OANDA_TOKEN.")
    if not acct:
        raise RuntimeError("OANDA account id not found. Set OANDA_ACCOUNT_ID.")

    base = (os.environ.get("OANDA_API_URL") or "https://api-fxpractice.oanda.com").strip().rstrip("/")
    url = f"{base}/v3/accounts/{acct}/pricing?instruments={provider_symbol}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    payload = http_json(url, headers=headers)

    # OANDA pricing response includes "prices": [ ... ]
    prices = payload.get("prices") if isinstance(payload, dict) else None
    if not isinstance(prices, list) or not prices:
        raise RuntimeError(f"No prices returned for {provider_symbol}. Response keys: {list(payload.keys()) if isinstance(payload, dict) else type(payload)}")

    p0 = prices[0]
    bids = p0.get("bids", []) if isinstance(p0, dict) else []
    asks = p0.get("asks", []) if isinstance(p0, dict) else []

    bid = bids[0].get("price") if bids and isinstance(bids[0], dict) else None
    ask = asks[0].get("price") if asks and isinstance(asks[0], dict) else None

    return {
        "provider": "oanda",
        "provider_symbol": provider_symbol,
        "bid": bid,
        "ask": ask,
        "timestamp": p0.get("time") if isinstance(p0, dict) else datetime.now(timezone.utc).isoformat(),
        "raw": p0,
    }


def fetch_snapshot(provider: str, provider_symbol: str) -> Dict[str, Any]:
    p = provider.lower().strip()
    if p == "alpaca":
        return alpaca_crypto_snapshot(provider_symbol)
    if p == "oanda":
        return oanda_fx_snapshot(provider_symbol)
    raise ValueError(f"Unsupported provider '{provider}'. Supported: alpaca, oanda")


# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------

@dataclass(frozen=True)
class Args:
    provider: str
    rea: str
    map_path: Path


def parse_args() -> Args:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, help="Provider key (e.g., alpaca, oanda)")
    ap.add_argument("--rea", required=True, help="Canonical REA instrument (e.g., REA:CRYPTO:BTCUSD, REA:FX:EURUSD)")
    ap.add_argument("--map", dest="map_path", default=str(DEFAULT_MAP_PATH), help="Path to provider_symbol_map.json")
    ns = ap.parse_args()
    return Args(provider=ns.provider, rea=ns.rea, map_path=Path(ns.map_path))


def main() -> int:
    args = parse_args()
    mapping = load_provider_symbol_map(args.map_path)
    provider_symbol = resolve_provider_symbol(args.provider, args.rea, mapping)

    snap = fetch_snapshot(args.provider, provider_symbol)

    out = {
        "rea_instrument": args.rea,
        "provider": args.provider.lower().strip(),
        "provider_symbol": provider_symbol,
        "snapshot": snap,
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
