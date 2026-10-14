"""Read-only Binance Spot public market data for the shadow paper runner.

Uses Binance's market-data-only host (no API key, no account access). One quote =
the latest public trade (price, trade id, exchange timestamp) from /api/v3/trades
plus the current best bid/ask from /api/v3/ticker/bookTicker. The combined quote is
validated by the same fail-closed rules as the Coinbase source (stale, missing,
crossed, implausible -> rejected; nothing is substituted).

If Binance answers HTTP 451 (service unavailable from a restricted location) the
quote is rejected as RESTRICTED_LOCATION. There is deliberately no fallback host,
proxy or VPN path: a geographic restriction must be respected, not worked around.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from backend.shadow_paper.market_data import (
    HTTP_TIMEOUT_SECONDS,
    Fetcher,
    MarketQuote,
    QuoteRejection,
    default_fetcher,
    validate_ticker,
)

LOGGER = logging.getLogger(__name__)

SOURCE_NAME = "BINANCE_SPOT_PUBLIC_MARKET_DATA"
PUBLIC_DATA_BASE_URL = "https://data-api.binance.vision"
TRADES_PATH = "/api/v3/trades"
BOOK_TICKER_PATH = "/api/v3/ticker/bookTicker"
SUPPORTED_INSTRUMENTS = ("BTCUSDT", "ETHUSDT")
RESTRICTED_LOCATION_STATUS = 451


def _iso_from_ms(value: Any) -> str | None:
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")


class BinancePublicTicker:
    """Fetch and validate one Binance Spot quote. Never raises; returns a rejection instead."""

    source_name = SOURCE_NAME
    supported_instruments = SUPPORTED_INSTRUMENTS

    def __init__(
        self,
        fetcher: Fetcher | None = None,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = HTTP_TIMEOUT_SECONDS,
        base_url: str = PUBLIC_DATA_BASE_URL,
    ) -> None:
        if base_url != PUBLIC_DATA_BASE_URL:
            raise ValueError("only the Binance public market-data host is permitted")
        self._fetcher = fetcher or default_fetcher
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout = float(timeout_seconds)

    def _reject(self, instrument: str, url: str, reason: str, detail: str) -> QuoteRejection:
        received = self._clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return QuoteRejection(instrument, SOURCE_NAME, url, reason, detail[:200], received)

    def fetch(self, instrument: str) -> MarketQuote | QuoteRejection:
        trades_url = f"{PUBLIC_DATA_BASE_URL}{TRADES_PATH}?symbol={instrument}&limit=1"
        book_url = f"{PUBLIC_DATA_BASE_URL}{BOOK_TICKER_PATH}?symbol={instrument}"
        if instrument not in SUPPORTED_INSTRUMENTS:
            return self._reject(instrument, trades_url, "UNSUPPORTED_INSTRUMENT", instrument)

        started = self._clock()
        try:
            trade_status, trade_body = self._fetcher(trades_url, self._timeout)
            book_status, book_body = self._fetcher(book_url, self._timeout)
        except Exception as exc:  # network errors are data rejections, never fatal
            LOGGER.warning("binance public data fetch failed for %s: %s", instrument, exc)
            return self._reject(instrument, trades_url, "FETCH_ERROR", f"{type(exc).__name__}: {exc}")
        received = self._clock()

        for status in (trade_status, book_status):
            if status == RESTRICTED_LOCATION_STATUS:
                return self._reject(
                    instrument, trades_url, "RESTRICTED_LOCATION",
                    "Binance returned HTTP 451 (restricted location); no workaround is attempted",
                )
        if trade_status != 200:
            return self._reject(instrument, trades_url, "HTTP_STATUS", f"trades={trade_status}")
        if book_status != 200:
            return self._reject(instrument, book_url, "HTTP_STATUS", f"bookTicker={book_status}")
        if not isinstance(trade_body, list) or len(trade_body) != 1 or not isinstance(trade_body[0], dict):
            return self._reject(instrument, trades_url, "MALFORMED_BODY", "trades response is not a single trade")
        if not isinstance(book_body, dict) or book_body.get("symbol") != instrument:
            return self._reject(instrument, book_url, "MALFORMED_BODY", "bookTicker symbol mismatch")

        trade = trade_body[0]
        body = {
            "price": trade.get("price"),
            "trade_id": trade.get("id"),
            "time": _iso_from_ms(trade.get("time")),
            "bid": book_body.get("bidPrice"),
            "ask": book_body.get("askPrice"),
        }
        return validate_ticker(
            instrument=instrument,
            url=trades_url,
            http_status=200,
            body=body,
            received_at=received,
            fetch_latency_ms=(received - started).total_seconds() * 1000.0,
            supported=SUPPORTED_INSTRUMENTS,
            source=SOURCE_NAME,
        )
