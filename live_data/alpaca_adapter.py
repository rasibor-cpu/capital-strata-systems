"""
Alpaca Data Adapter (Crypto Snapshot)
-------------------------------------

Uses Alpaca data endpoint to fetch latest crypto quote.

Env vars expected:
- APCA_API_KEY_ID
- APCA_API_SECRET_KEY
Optional:
- ALPACA_DATA_URL : defaults to https://data.alpaca.markets
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Callable, Dict, Any

import requests


DEFAULT_DATA_URL = "https://data.alpaca.markets"


class AlpacaLiveDataAdapter:
    """
    Data-only Alpaca streaming adapter.

    The alpaca-py dependency is imported only when streaming starts so pytest
    collection and snapshot-only usage do not require live-data dependencies.
    """

    def __init__(self, api_key: str, secret_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self._quote_handler: Callable[[Any], None] | None = None
        self._tick_handler: Callable[[Any], None] | None = None
        self._stream: Any | None = None
        self._thread: threading.Thread | None = None

    @classmethod
    def from_env(cls) -> "AlpacaLiveDataAdapter":
        api_key = (
            os.environ.get("APCA_API_KEY_ID")
            or os.environ.get("ALPACA_API_KEY")
            or ""
        ).strip()
        secret_key = (
            os.environ.get("APCA_API_SECRET_KEY")
            or os.environ.get("ALPACA_SECRET_KEY")
            or ""
        ).strip()

        if not api_key:
            raise RuntimeError(
                "Missing required environment variable: APCA_API_KEY_ID"
            )

        if not secret_key:
            raise RuntimeError(
                "Missing required environment variable: APCA_API_SECRET_KEY"
            )

        return cls(
            api_key=api_key,
            secret_key=secret_key,
            base_url=os.environ.get(
                "ALPACA_BASE_URL",
                "https://paper-api.alpaca.markets",
            ),
        )

    def set_quote_handler(self, fn: Callable[[Any], None]) -> None:
        self._quote_handler = fn

    def set_tick_handler(self, fn: Callable[[Any], None]) -> None:
        self._tick_handler = fn

    def start_streaming_quotes(self, symbols: list[str]) -> None:
        if not self._quote_handler:
            raise RuntimeError("Quote handler not set")

        stream = self._build_stock_stream()

        async def _on_quote(quote: Any) -> None:
            if self._quote_handler:
                self._quote_handler(quote)

        for symbol in symbols:
            stream.subscribe_quotes(_on_quote, symbol)

        self._start_stream(stream)

    def start_streaming_trades(self, symbols: list[str]) -> None:
        if not self._tick_handler:
            raise RuntimeError("Tick handler not set")

        stream = self._build_stock_stream()

        async def _on_trade(trade: Any) -> None:
            if self._tick_handler:
                self._tick_handler(trade)

        for symbol in symbols:
            stream.subscribe_trades(_on_trade, symbol)

        self._start_stream(stream)

    def stop_streaming(self) -> None:
        if self._stream:
            self._stream.stop()

        if self._thread:
            self._thread.join(timeout=5)

    def _build_stock_stream(self) -> Any:
        try:
            from alpaca.data.live import StockDataStream
        except ImportError as exc:
            raise RuntimeError(
                "Alpaca live streaming requires the alpaca-py package"
            ) from exc

        return StockDataStream(
            self.api_key,
            self.secret_key,
            raw_data=False,
        )

    def _start_stream(self, stream: Any) -> None:
        self._stream = stream
        self._thread = threading.Thread(
            target=stream.run,
            daemon=True,
        )
        self._thread.start()


def _require_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v


def _alpaca_headers() -> Dict[str, str]:
    return {
        "APCA-API-KEY-ID": _require_env("APCA_API_KEY_ID"),
        "APCA-API-SECRET-KEY": _require_env("APCA_API_SECRET_KEY"),
        "Accept": "application/json",
    }


def fetch_alpaca_crypto_snapshot(provider_symbol: str) -> Dict[str, Any]:
    """
    provider_symbol example: "BTC/USD"
    """
    base = os.environ.get("ALPACA_DATA_URL", DEFAULT_DATA_URL).strip().rstrip("/")
    url = f"{base}/v1beta3/crypto/us/latest/quotes"
    params = {"symbols": provider_symbol}

    r = requests.get(url, headers=_alpaca_headers(), params=params, timeout=20)

    if r.status_code != 200:
        body = r.text[:800]
        raise RuntimeError(
            f"Alpaca crypto quote failed: HTTP {r.status_code}. "
            f"URL={url} symbols={provider_symbol}. "
            f"Body(first800)={body}"
        )

    data = r.json()
    quotes = (data.get("quotes") or {})
    q = quotes.get(provider_symbol)
    if not q:
        raise RuntimeError(f"No quote returned for {provider_symbol}")

    return {
        "source": "alpaca",
        "symbol": provider_symbol,
        "ap": q.get("ap"),
        "bp": q.get("bp"),
        "as": q.get("as"),
        "bs": q.get("bs"),
        "t": q.get("t"),
        "raw": q,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }
