"""
REA Live Data Controller (Provider-Agnostic)
--------------------------------------------

Purpose:
- Single entrypoint to fetch a live snapshot for a REA canonical instrument
  from a selected provider (e.g., OANDA for FX pricing, Alpaca for crypto quotes).

Key design points:
- Provider symbol mapping is governance-controlled via JSON file:
    data/provider_symbol_map.json

- Safe defaults:
  - Missing mapping => fail closed with a clear error.
  - Missing required env vars => fail closed with a clear error.
  - Provider response shape variations are handled defensively.

CLI examples:
  python -m live_data.rea_live_data_controller --provider alpaca --rea REA:CRYPTO:BTCUSD
  python -m live_data.rea_live_data_controller --provider oanda  --rea REA:FX:EURUSD

Env vars expected:
  Alpaca:
    APCA_API_KEY_ID
    APCA_API_SECRET_KEY

  OANDA (practice or live depends on adapter/config):
    OANDA_TOKEN
    OANDA_ACCOUNT_ID
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_MAP_PATH = Path("data") / "provider_symbol_map.json"


# -----------------------------
# helpers
# -----------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_inst(s: str) -> str:
    # filename-safe token
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")


def _require_env(name: str) -> str:
    v = os.environ.get(name)
    if not v or not str(v).strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return str(v).strip()


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Provider map not found: {path}. Create it (data/provider_symbol_map.json)."
        )
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Provider map is empty: {path}")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("provider_symbol_map.json must be a JSON object at top level.")
    return obj


def load_provider_symbol_map(path: Optional[Path] = None) -> Dict[str, Dict[str, str]]:
    p = path or Path(os.environ.get("REA_PROVIDER_MAP", str(DEFAULT_MAP_PATH)))
    data = _read_json(p)

    # Validate: { provider: { rea_instrument: provider_symbol } }
    out: Dict[str, Dict[str, str]] = {}
    for provider, mapping in data.items():
        if not isinstance(provider, str) or not isinstance(mapping, dict):
            raise ValueError("Invalid provider map structure (provider keys must be strings).")
        inner: Dict[str, str] = {}
        for rea_inst, prov_sym in mapping.items():
            if not isinstance(rea_inst, str) or not isinstance(prov_sym, str):
                raise ValueError("Invalid provider map structure (inner keys/values must be strings).")
            inner[rea_inst.strip()] = prov_sym.strip()
        out[provider.strip().lower()] = inner
    return out


def resolve_provider_symbol(provider: str, rea_instrument: str, mapping: Dict[str, Dict[str, str]]) -> str:
    p = provider.lower().strip()
    if p not in mapping:
        raise KeyError(f"No mappings found for provider '{provider}'.")
    if rea_instrument not in mapping[p]:
        raise KeyError(
            f"Missing mapping for rea_instrument='{rea_instrument}' under provider='{provider}'. "
            f"Update data/provider_symbol_map.json (governance-controlled)."
        )
    return mapping[p][rea_instrument]


def _to_float(x: Any) -> float:
    # OANDA/Alpaca often return strings; accept both.
    try:
        return float(x)
    except Exception:
        raise ValueError(f"Expected numeric value, got: {x!r}")


# -----------------------------
# Alpaca (crypto quotes) — stdlib HTTP
# -----------------------------

def _alpaca_headers() -> Dict[str, str]:
    key_id = _require_env("APCA_API_KEY_ID")
    secret = _require_env("APCA_API_SECRET_KEY")
    return {
        "APCA-API-KEY-ID": key_id,
        "APCA-API-SECRET-KEY": secret,
        "Accept": "application/json",
    }


def fetch_alpaca_crypto_snapshot(provider_symbol: str, include_raw: bool = True) -> Dict[str, Any]:
    """
    provider_symbol example: "BTC/USD"
    Endpoint used: v1beta3 crypto latest quotes (US)
    """
    base = "https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes"
    qs = urllib.parse.urlencode({"symbols": provider_symbol})
    url = f"{base}?{qs}"

    req = urllib.request.Request(url, headers=_alpaca_headers(), method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", errors="replace")

    obj = json.loads(body)
    quotes = obj.get("quotes", {})
    if provider_symbol not in quotes:
        raise RuntimeError(f"Alpaca returned no quote for symbol '{provider_symbol}'. Keys={list(quotes.keys())[:10]}")
    q = quotes[provider_symbol]

    ask = _to_float(q.get("ap"))
    bid = _to_float(q.get("bp"))
    ts = q.get("t") or _utc_now_iso()

    out: Dict[str, Any] = {
        "source": "alpaca",
        "instrument": provider_symbol,
        "time": ts,
        "bid": bid,
        "ask": ask,
        "mid": (bid + ask) / 2.0,
        "spread": ask - bid,
        "status": "ok",
        "tradeable": True,
        "ts_utc": _utc_now_iso(),
    }
    if include_raw:
        out["raw"] = obj
    return out


# -----------------------------
# OANDA (FX pricing) — accept both raw and normalized shapes
# -----------------------------

def _normalize_oanda_price_block(price_block: Dict[str, Any], provider_symbol: str, rea_instrument: str) -> Dict[str, Any]:
    """
    Accepts:
      A) Raw OANDA pricing structure (prices[0] with bids/asks arrays), OR
      B) Already-normalized dict from our adapter (keys: bid/ask/time/status/tradeable/etc.)
    Returns a normalized snapshot with keys:
      source, instrument, time, bid, ask, mid, spread, status, tradeable, raw, ts_utc
    """
    # Case B: already normalized by our adapter
    if "bid" in price_block and "ask" in price_block:
        bid = _to_float(price_block.get("bid"))
        ask = _to_float(price_block.get("ask"))
        t = price_block.get("time") or price_block.get("ts") or price_block.get("timestamp") or _utc_now_iso()
        status = price_block.get("status") or "ok"
        tradeable = bool(price_block.get("tradeable", True))

        out_b: Dict[str, Any] = {
            "source": "oanda",
            "instrument": provider_symbol,
            "time": t,
            "bid": bid,
            "ask": ask,
            "mid": (bid + ask) / 2.0,
            "spread": ask - bid,
            "status": status,
            "tradeable": tradeable,
            "ts_utc": _utc_now_iso(),
        }
        # keep raw if present
        if "raw" in price_block:
            out_b["raw"] = price_block["raw"]
        else:
            out_b["raw"] = price_block
        # Optional warning info
        if not tradeable or str(status).lower() == "non-tradeable":
            print("⚠️ OANDA instrument marked non-tradeable.")
        return out_b

    # Case A: raw OANDA pricing price block
    # Typical fields:
    #  instrument, time, status, tradeable, bids:[{price,liquidity}], asks:[{price,liquidity}]
    bids = price_block.get("bids")
    asks = price_block.get("asks")
    if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
        raise RuntimeError(
            "Invalid OANDA snapshot structure: missing bids/asks arrays. "
            f"Keys present: {list(price_block.keys())}"
        )

    bid = _to_float(bids[0].get("price"))
    ask = _to_float(asks[0].get("price"))
    t = price_block.get("time") or _utc_now_iso()

    status = price_block.get("status") or "ok"
    tradeable = bool(price_block.get("tradeable", False))

    out_a: Dict[str, Any] = {
        "source": "oanda",
        "instrument": provider_symbol,
        "time": t,
        "bid": bid,
        "ask": ask,
        "mid": (bid + ask) / 2.0,
        "spread": ask - bid,
        "status": status,
        "tradeable": tradeable,
        "ts_utc": _utc_now_iso(),
        "raw": {
            "rea_instrument": rea_instrument,
            "provider_symbol": provider_symbol,
            "price_block": price_block,
        },
    }
    if not tradeable or str(status).lower() == "non-tradeable":
        print("⚠️ OANDA instrument marked non-tradeable.")
    return out_a


def fetch_oanda_snapshot(provider_symbol: str, rea_instrument: str) -> Dict[str, Any]:
    """
    Uses our local adapter if present. This keeps broker-specific URL selection
    (practice vs live) centralized.

    Adapter must expose: fetch_oanda_snapshot(provider_symbol: str) -> dict
    (either raw OANDA price block, or already normalized).
    """
    try:
        # Prefer local adapter
        from live_data.oanda_adapter import fetch_oanda_snapshot as adapter_fetch  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "OANDA adapter import failed. Ensure live_data/oanda_adapter.py exists and is importable. "
            f"Import error: {e}"
        )

    raw = adapter_fetch(provider_symbol)
    if raw is None:
        raise RuntimeError("OANDA adapter returned None.")

    # Adapter may return full response or a single price block; handle both
    if isinstance(raw, dict) and "prices" in raw and isinstance(raw.get("prices"), list) and raw["prices"]:
        price_block = raw["prices"][0]
        return _normalize_oanda_price_block(price_block, provider_symbol, rea_instrument)

    if isinstance(raw, dict):
        return _normalize_oanda_price_block(raw, provider_symbol, rea_instrument)

    raise RuntimeError(f"Unexpected OANDA adapter return type: {type(raw)}")


# -----------------------------
# public entrypoints
# -----------------------------

def fetch_snapshot(provider: str, provider_symbol: str, rea_instrument: str) -> Dict[str, Any]:
    p = provider.lower().strip()

    if p == "alpaca":
        snap = fetch_alpaca_crypto_snapshot(provider_symbol=provider_symbol, include_raw=True)
        snap["rea_instrument"] = rea_instrument
        return snap

    if p == "oanda":
        snap = fetch_oanda_snapshot(provider_symbol=provider_symbol, rea_instrument=rea_instrument)
        snap["rea_instrument"] = rea_instrument
        return snap

    raise ValueError(f"Unsupported provider '{provider}'. Supported: alpaca, oanda")


def write_snapshot_file(snapshot: Dict[str, Any]) -> Path:
    provider = str(snapshot.get("source", "provider")).lower()
    rea_inst = str(snapshot.get("rea_instrument", "REA"))
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fname = f"live_tick_{provider}_{_safe_inst(rea_inst)}_{ts}.json"
    out_path = Path(fname)
    out_path.write_text(json.dumps(snapshot, indent=2, sort_keys=False), encoding="utf-8")
    return out_path


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Fetch a live snapshot for a REA instrument from a selected provider.")
    p.add_argument("--provider", required=True, help="Provider key (e.g., alpaca, oanda)")
    p.add_argument("--rea", required=True, help="REA canonical instrument (e.g., REA:FX:EURUSD, REA:CRYPTO:BTCUSD)")
    p.add_argument("--map", default=str(os.environ.get("REA_PROVIDER_MAP", str(DEFAULT_MAP_PATH))),
                   help="Path to provider symbol map JSON (default: data/provider_symbol_map.json)")
    p.add_argument("--no-file", action="store_true", help="Do not write snapshot to a JSON file (print only).")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()

    provider = args.provider.strip()
    rea_instrument = args.rea.strip()
    map_path = Path(args.map)

    mapping = load_provider_symbol_map(map_path)
    provider_symbol = resolve_provider_symbol(provider, rea_instrument, mapping)

    snap = fetch_snapshot(provider=provider, provider_symbol=provider_symbol, rea_instrument=rea_instrument)

    # Always print snapshot (short)
    print(json.dumps(
        {
            "source": snap.get("source"),
            "rea_instrument": snap.get("rea_instrument"),
            "instrument": snap.get("instrument"),
            "time": snap.get("time"),
            "bid": snap.get("bid"),
            "ask": snap.get("ask"),
            "mid": snap.get("mid"),
            "spread": snap.get("spread"),
            "status": snap.get("status"),
            "tradeable": snap.get("tradeable"),
            "ts_utc": snap.get("ts_utc"),
        },
        indent=2
    ))

    if not args.no_file:
        out_path = write_snapshot_file(snap)
        print(f"\nWrote: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
