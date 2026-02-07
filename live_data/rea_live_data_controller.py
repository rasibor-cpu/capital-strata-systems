"""
REA Live Data Controller (Provider-Agnostic, Governance-Safe)

Purpose:
- Resolve Canonical REA instrument → Provider symbol
- Fetch live snapshot via provider adapter
- Return structured envelope
- No direct broker SDK imports here
- Fail closed by default
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

# Provider adapters (governance controlled)
from live_data.oanda_adapter import fetch_oanda_snapshot
from live_data.alpaca_adapter import fetch_alpaca_crypto_snapshot


# --------------------------------------------------------
# Default mapping path (governance controlled JSON)
# --------------------------------------------------------

DEFAULT_MAP_PATH = Path("data") / "provider_symbol_map.json"


# --------------------------------------------------------
# Mapping loader
# --------------------------------------------------------

def load_provider_symbol_map(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Provider map not found: {path}. "
            f"Create it (data/provider_symbol_map.json)."
        )

    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError("provider_symbol_map.json must be a JSON object.")

    return raw


def resolve_provider_symbol(
    provider: str,
    rea_instrument: str,
    mapping: Dict[str, Dict[str, str]]
) -> str:
    prov_map = mapping.get(provider)
    if not prov_map:
        raise KeyError(f"No mappings found for provider '{provider}'.")

    symbol = prov_map.get(rea_instrument)
    if not symbol:
        raise KeyError(
            f"Missing mapping for '{rea_instrument}' under provider '{provider}'."
        )

    return symbol


# --------------------------------------------------------
# Snapshot Router
# --------------------------------------------------------

def fetch_snapshot(provider: str, provider_symbol: str) -> Dict[str, Any]:
    provider = provider.lower().strip()

    if provider == "oanda":
        return fetch_oanda_snapshot(provider_symbol)

    if provider == "alpaca":
        return fetch_alpaca_crypto_snapshot(provider_symbol)

    raise ValueError(
        f"Unsupported provider '{provider}'. "
        f"Implement adapter before use."
    )


# --------------------------------------------------------
# Envelope Builder
# --------------------------------------------------------

def build_envelope(
    provider: str,
    rea_instrument: str,
    provider_symbol: str,
    snapshot: Dict[str, Any]
) -> Dict[str, Any]:

    return {
        "provider": provider,
        "rea_instrument": rea_instrument,
        "provider_symbol": provider_symbol,
        "snapshot": snapshot,
        "ts_utc": datetime.now(timezone.utc).isoformat()
    }


# --------------------------------------------------------
# CLI Entry
# --------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(description="REA Live Snapshot Fetcher")

    parser.add_argument(
        "--provider",
        required=True,
        help="Provider key (e.g. oanda, alpaca)"
    )

    parser.add_argument(
        "--rea",
        required=True,
        help="Canonical REA instrument (e.g. REA:FX:EURUSD)"
    )

    args = parser.parse_args()

    provider = args.provider.lower().strip()
    rea_instrument = args.rea.strip()

    map_path = Path(
        os.environ.get("REA_PROVIDER_MAP", str(DEFAULT_MAP_PATH))
    )

    mapping = load_provider_symbol_map(map_path)

    provider_symbol = resolve_provider_symbol(
        provider,
        rea_instrument,
        mapping
    )

    snapshot = fetch_snapshot(provider, provider_symbol)

    envelope = build_envelope(
        provider,
        rea_instrument,
        provider_symbol,
        snapshot
    )

    print(json.dumps(envelope, indent=2))


if __name__ == "__main__":
    main()
