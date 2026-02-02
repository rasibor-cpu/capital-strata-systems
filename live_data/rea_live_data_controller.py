"""
REA Live Data Controller (Provider-Agnostic)
--------------------------------------------
Purpose:
- Enforce governance-locked mapping:
    Strategy Concept -> Canonical REA Instrument -> Provider Symbol
  (For now we implement Canonical REA Instrument -> Provider Symbol mapping via JSON)

- Pull a snapshot tick from Alpaca (crypto)
- Emit normalized MarketDataTick JSON to stdout (and optionally to audit_logs)

Run:
  python live_data\\rea_live_data_controller.py --provider alpaca --rea REA:CRYPTO:BTCUSD

Optional:
  set REA_PROVIDER_MAP=data\\provider_symbol_map.json
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# -----------------------------
# Normalized tick model
# -----------------------------

@dataclass(frozen=True)
class MarketDataTick:
    ts_utc: str
    provider: str
    rea_instrument: str
    provider_symbol: str
    bid: Optional[float]
    ask: Optional[float]
    mid: Optional[float]
    source: str = "snapshot"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -----------------------------
# Governance mapping loader
# -----------------------------

DEFAULT_MAP_PATH = Path("data") / "provider_symbol_map.json"


def load_provider_symbol_map(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Provider map not found: {path}. Create it (data/provider_symbol_map.json)."
        )

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("provider_symbol_map.json must be a JSON object at top level.")

    # expected shape: { "alpaca": { "REA:CRYPTO:BTCUSD": "BTC/USD", ... }, "other": {...} }
    out: Dict[str, Dict[str, str]] = {}
    for provider, mapping in raw.items():
        if not isinstance(provider, str) or not isinstance(mapping, dict):
            raise ValueError("Invalid provider map structure.")
        out[provider] = {}
        for rea_inst, prov_sym in mapping.items():
            if not isinstance(rea_inst, str) or not isinstance(prov_sym, str):
                raise ValueError("Mapping entries must be strings.")
            out[provider][rea_inst] = prov_sym
    return out


def resolve_provider_symbol(provider: str, rea_instrument: str, mapping: Dict[str, Dict[str, str]]) -> str:
    prov_map = mapping.get(provider)
    if not prov_map:
        raise KeyError(f"No mappings found for provider '{provider}'.")
    sym = prov_map.get(rea_instrument)
    if not sym:
        raise KeyError(
            f"Missing mapping for rea_instrument='{rea_instrument}' under provider='{provider}'. "
            f"Update data/provider_symbol_map.json (governance-controlled)."
        )
    return sym


# -----------------------------
# Provider adapters (snapshot)
# -----------------------------

def alpaca_crypto_snapshot(provider_symbol: str) -> Dict[str, Any]:
    # We reuse the logic style in live_data/alpaca_adapter.py (alpaca-py)
    from alpaca.data.historical import CryptoHistoricalDataClient
    from alpaca.data.requests import CryptoLatestQuoteRequest

    client = CryptoHistoricalDataClient()
    req = CryptoLatestQuoteRequest(symbol_or_symbols=provider_symbol)
    quotes = client.get_crypto_latest_quote(req)

    q = quotes.get(provider_symbol)
    if not q:
        raise RuntimeError(f"No quote returned for {provider_symbol}")

    bid = float(q.bid_price) if q.bid_price is not None else None
    ask = float(q.ask_price) if q.ask_price is not None else None

    mid = None
    if bid is not None and ask is not None:
        mid = (bid + ask) / 2.0

    ts = q.timestamp.isoformat() if q.timestamp else utc_now_iso()

    return {"bid": bid, "ask": ask, "mid": mid, "ts": ts}


def fetch_snapshot(provider: str, provider_symbol: str) -> Dict[str, Any]:
    provider = provider.lower().strip()
    if provider == "alpaca":
        return alpaca_crypto_snapshot(provider_symbol)

    raise ValueError(f"Unsupported provider '{provider}'. Implement adapter in this controller.")


# -----------------------------
# Output + optional audit log
# -----------------------------

def write_audit_log(tick: MarketDataTick) -> Path:
    log_dir = Path("audit_logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # filename safe
    safe_inst = tick.rea_instrument.replace(":", "_").replace("/", "_")
    fname = f"live_tick_{tick.provider}_{safe_inst}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path = log_dir / fname
    path.write_text(json.dumps(asdict(tick), indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="REA Live Data Controller (snapshot)")
    parser.add_argument("--provider", required=True, help="Provider key (e.g., alpaca)")
    parser.add_argument("--rea", required=True, help="Canonical REA instrument id (e.g., REA:CRYPTO:BTCUSD)")
    parser.add_argument("--audit", action="store_true", help="Write tick JSON to audit_logs/")
    args = parser.parse_args()

    map_path = Path(os.environ.get("REA_PROVIDER_MAP", str(DEFAULT_MAP_PATH)))

    mapping = load_provider_symbol_map(map_path)
    provider_symbol = resolve_provider_symbol(args.provider, args.rea, mapping)

    snap = fetch_snapshot(args.provider, provider_symbol)

    tick = MarketDataTick(
        ts_utc=snap.get("ts") or utc_now_iso(),
        provider=args.provider.lower(),
        rea_instrument=args.rea,
        provider_symbol=provider_symbol,
        bid=snap.get("bid"),
        ask=snap.get("ask"),
        mid=snap.get("mid"),
        source="snapshot",
    )

    print(json.dumps(asdict(tick), indent=2))

    if args.audit:
        p = write_audit_log(tick)
        print(f"\nAUDIT_LOG_WRITTEN: {p}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
