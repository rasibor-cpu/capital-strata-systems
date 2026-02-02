"""
REA Capital – Alpaca Live Data Adapter
-------------------------------------
Deterministic self-test:
- Loads keys from environment
- Prints config banner
- Fetches a snapshot quote (crypto by default)
- Exits cleanly with explicit output

Compatible with alpaca-py
"""

import os
import sys
import time
from datetime import datetime, timezone

from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoLatestQuoteRequest

# -----------------------------
# Config helpers
# -----------------------------

def _mask(s: str) -> str:
    if not s:
        return "MISSING"
    if len(s) <= 6:
        return "***"
    return s[:3] + "***" + s[-3:]


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def print_banner():
    print("=" * 72)
    print("REA Capital – Alpaca Live Data Adapter (Self-Test)")
    print(f"UTC Now: {datetime.now(timezone.utc).isoformat()}")
    print("-" * 72)

    key_id = _env("APCA_API_KEY_ID") or _env("ALPACA_API_KEY")
    secret = _env("APCA_API_SECRET_KEY") or _env("ALPACA_SECRET_KEY")

    print(f"API KEY ID   : {_mask(key_id)}")
    print(f"API SECRET  : {_mask(secret)}")
    print("Mode        : Crypto (snapshot)")
    print("=" * 72)

    if not key_id or not secret:
        print("ERROR: Alpaca API keys not found in environment.")
        print("Set either:")
        print("  APCA_API_KEY_ID / APCA_API_SECRET_KEY")
        print("or")
        print("  ALPACA_API_KEY / ALPACA_SECRET_KEY")
        sys.exit(2)


# -----------------------------
# Snapshot test (Crypto)
# -----------------------------

def fetch_crypto_snapshot(symbol: str = "BTC/USD"):
    """
    Fetch a single latest quote for a crypto symbol.
    """
    client = CryptoHistoricalDataClient()

    req = CryptoLatestQuoteRequest(symbol_or_symbols=symbol)
    quotes = client.get_crypto_latest_quote(req)

    q = quotes.get(symbol)
    if not q:
        raise RuntimeError(f"No quote returned for {symbol}")

    return {
        "symbol": symbol,
        "bid": float(q.bid_price) if q.bid_price is not None else None,
        "ask": float(q.ask_price) if q.ask_price is not None else None,
        "ts": q.timestamp.isoformat() if q.timestamp else None,
    }


# -----------------------------
# Main (self-test)
# -----------------------------

def main():
    print_banner()

    symbol = _env("REA_TEST_CRYPTO", "BTC/USD")
    print(f"Requesting snapshot for: {symbol}")

    try:
        snap = fetch_crypto_snapshot(symbol)
    except Exception as e:
        print("SNAPSHOT ERROR:", repr(e))
        sys.exit(1)

    print("SNAPSHOT OK")
    print(f"  Symbol : {snap['symbol']}")
    print(f"  Bid    : {snap['bid']}")
    print(f"  Ask    : {snap['ask']}")
    print(f"  Time   : {snap['ts']}")

    print("-" * 72)
    print("Alpaca adapter self-test completed successfully.")
    print("=" * 72)


if __name__ == "__main__":
    main()
