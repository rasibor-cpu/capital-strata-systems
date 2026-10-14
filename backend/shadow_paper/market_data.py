"""Read-only, validated public market data for the shadow paper runner.

Source: Coinbase Exchange public ticker (the same public endpoint used by
backend.data.price_feed). Unlike PriceFeed.get_price, this returns the exchange
trade timestamp, bid/ask and trade id so freshness and provenance can be proven.

Fail closed: any missing, malformed, stale, future-dated or implausible quote is
rejected with a reason code. No price is ever substituted, cached or synthesized.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

LOGGER = logging.getLogger(__name__)

SOURCE_NAME = "COINBASE_EXCHANGE_PUBLIC_TICKER"
TICKER_URL_TEMPLATE = "https://api.exchange.coinbase.com/products/{product_id}/ticker"
SUPPORTED_INSTRUMENTS = ("BTC-USD", "ETH-USD")

# Data-quality limits (market-data validation only; not trading thresholds).
MAX_QUOTE_AGE_SECONDS = 120.0
MAX_FUTURE_SKEW_SECONDS = 5.0
MAX_SPREAD_BPS = 50.0
MAX_TRADE_DEVIATION_FROM_MID_BPS = 50.0
HTTP_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class MarketQuote:
    instrument: str
    source: str
    url: str
    price: float
    bid: float
    ask: float
    trade_id: int
    exchange_time_utc: str
    received_at_utc: str
    age_seconds: float
    spread_bps: float
    fetch_latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuoteRejection:
    instrument: str
    source: str
    url: str
    reason: str
    detail: str
    received_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# fetcher(url, timeout) -> (http_status, parsed_json_or_None)
Fetcher = Callable[[str, float], tuple[int, Any]]


def default_fetcher(url: str, timeout: float) -> tuple[int, Any]:
    import requests  # local import keeps tests network-free by injection

    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "CSS-ShadowPaperRunner/1.0"},
    )
    try:
        body = response.json()
    except ValueError:
        body = None
    return int(response.status_code), body


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_exchange_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _positive_finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def validate_ticker(
    *,
    instrument: str,
    url: str,
    http_status: int,
    body: Any,
    received_at: datetime,
    fetch_latency_ms: float,
) -> MarketQuote | QuoteRejection:
    received_iso = _iso(received_at)

    def reject(reason: str, detail: str = "") -> QuoteRejection:
        return QuoteRejection(instrument, SOURCE_NAME, url, reason, detail[:200], received_iso)

    if instrument not in SUPPORTED_INSTRUMENTS:
        return reject("UNSUPPORTED_INSTRUMENT", instrument)
    if http_status != 200:
        return reject("HTTP_STATUS", str(http_status))
    if not isinstance(body, dict):
        return reject("MALFORMED_BODY", type(body).__name__)

    for field in ("price", "bid", "ask", "time", "trade_id"):
        if body.get(field) in (None, ""):
            return reject("MISSING_FIELD", field)

    price = _positive_finite(body.get("price"))
    bid = _positive_finite(body.get("bid"))
    ask = _positive_finite(body.get("ask"))
    if price is None or bid is None or ask is None:
        return reject("INVALID_PRICE", f"price={body.get('price')} bid={body.get('bid')} ask={body.get('ask')}")
    if bid > ask:
        return reject("CROSSED_BOOK", f"bid={bid} ask={ask}")

    try:
        trade_id = int(body.get("trade_id"))
    except (TypeError, ValueError):
        return reject("INVALID_TRADE_ID", str(body.get("trade_id")))

    exchange_time = _parse_exchange_time(body.get("time"))
    if exchange_time is None:
        return reject("UNVERIFIABLE_TIMESTAMP", str(body.get("time")))

    age = (received_at - exchange_time).total_seconds()
    if age < -MAX_FUTURE_SKEW_SECONDS:
        return reject("FUTURE_TIMESTAMP", f"age_seconds={age:.3f}")
    if age > MAX_QUOTE_AGE_SECONDS:
        return reject("STALE_PRICE", f"age_seconds={age:.3f}")

    mid = (bid + ask) / 2.0
    spread_bps = (ask - bid) / mid * 10_000.0
    if spread_bps > MAX_SPREAD_BPS:
        return reject("ABNORMAL_SPREAD", f"spread_bps={spread_bps:.3f}")
    deviation_bps = abs(price - mid) / mid * 10_000.0
    if deviation_bps > MAX_TRADE_DEVIATION_FROM_MID_BPS:
        return reject("TRADE_FAR_FROM_QUOTE", f"deviation_bps={deviation_bps:.3f}")

    return MarketQuote(
        instrument=instrument,
        source=SOURCE_NAME,
        url=url,
        price=price,
        bid=bid,
        ask=ask,
        trade_id=trade_id,
        exchange_time_utc=_iso(exchange_time),
        received_at_utc=received_iso,
        age_seconds=round(max(age, 0.0), 3),
        spread_bps=round(spread_bps, 4),
        fetch_latency_ms=round(fetch_latency_ms, 1),
    )


class CoinbasePublicTicker:
    """Fetch and validate one quote. Never raises; returns a rejection instead."""

    def __init__(
        self,
        fetcher: Fetcher | None = None,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = HTTP_TIMEOUT_SECONDS,
    ) -> None:
        self._fetcher = fetcher or default_fetcher
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout = float(timeout_seconds)

    def fetch(self, instrument: str) -> MarketQuote | QuoteRejection:
        url = TICKER_URL_TEMPLATE.format(product_id=instrument)
        started = self._clock()
        try:
            status, body = self._fetcher(url, self._timeout)
        except Exception as exc:  # network errors are data rejections, never fatal
            LOGGER.warning("shadow market data fetch failed for %s: %s", instrument, exc)
            return QuoteRejection(
                instrument, SOURCE_NAME, url, "FETCH_ERROR",
                f"{type(exc).__name__}: {exc}"[:200], _iso(self._clock()),
            )
        received = self._clock()
        latency_ms = (received - started).total_seconds() * 1000.0
        return validate_ticker(
            instrument=instrument,
            url=url,
            http_status=status,
            body=body,
            received_at=received,
            fetch_latency_ms=latency_ms,
        )
