"""Read-only market-data providers, failover and data-quality checks (closeout).

Extends backend.signals.candles with the approved free-data architecture. Nothing here can
place an order, and nothing here holds or logs a secret.

Providers (all read-only, all fail closed with a stable reason code)
  AlpacaCryptoPublicCandles   data.alpaca.markets v1beta3 crypto bars (no key needed)    LIVE
  AlpacaStockCandles          data.alpaca.markets v2 stock bars, feed=iex (keys needed)   INDICATIVE
                              IEX is one exchange (a few % of US volume): it is NOT the
                              consolidated tape, so it is never classified LIVE.
  BinanceSpotPublicCandles    data-api.binance.vision klines (public, no key)            LIVE
                              Requires an attested operating country; jurisdictions
                              Binance.com does not serve are refused before any request,
                              and HTTP 451 is authoritative (no alternate host, proxy or VPN).
  BlockedFeed                 options and futures: no authorized feed exists -> always blocked
  ReplayCandleProvider        deterministic replay from CsvCandleStore                    REPLAY

Quality and resilience
  RetryingHttp                per-host rate limit, exponential backoff with jitter-free
                              deterministic delays, Retry-After honoured, 451 never retried
  FailoverCandleProvider      ordered providers, normalised symbols, per-attempt provenance,
                              optional cross-provider discrepancy check (fail closed)
  compare_series              overlapping-bar close deviation in bps
  series_metrics              realised volatility, volume and completeness
  QuoteSnapshot / *Quotes     best bid/ask, spread in bps, top-of-book depth, exchange time
  measure_clock_skew          exchange server time vs local UTC clock
  provider_matrix             static readiness of every provider (credentials, jurisdiction)
"""
from __future__ import annotations

import math
import os
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from backend.signals.candles import (
    INDICATIVE,
    LIVE,
    REPLAY,
    Candle,
    CandleError,
    CandleProvider,
    CandleSeries,
    CoinbasePublicCandles,
    CsvCandleStore,
    OandaPracticeCandles,
    _Http,
    _requests_session,
    _now_utc,
    check_http,
    drop_incomplete,
    validate,
)

ALPACA_DATA_BASE = "https://data.alpaca.markets"
BINANCE_PUBLIC_BASE = "https://data-api.binance.vision"
COINBASE_BASE = "https://api.exchange.coinbase.com"

ALPACA_TIMEFRAMES = {60: "1Min", 300: "5Min", 900: "15Min", 3600: "1Hour", 14400: "4Hour", 86400: "1Day"}
BINANCE_INTERVALS = {60: "1m", 300: "5m", 900: "15m", 3600: "1h", 14400: "4h", 86400: "1d"}

# Binance.com service restrictions as recorded by PR #113 (backend/binance_readonly/eligibility.py).
# Must be re-verified against Binance's current Terms of Use; HTTP 451 is always authoritative.
BINANCE_RESTRICTED_COUNTRIES = frozenset({"CA", "US", "NL", "CU", "IR", "KP", "SY"})


# --------------------------------------------------------------------------- symbols
def normalize_symbol(provider: str, canonical: str) -> str:
    """Canonical crypto 'BASE-QUOTE' (e.g. BTC-USD) / FX 'EUR/USD' / equity 'SPY' -> provider symbol."""
    canonical = canonical.strip().upper()
    if provider == "coinbase":
        return canonical.replace("/", "-")
    if provider == "alpaca_crypto":
        return canonical.replace("-", "/")
    if provider == "alpaca_stock":
        if "-" in canonical or "/" in canonical:
            raise CandleError(f"symbol_not_equity:{canonical}")
        return canonical
    if provider == "binance":
        base, _, quote = canonical.replace("/", "-").partition("-")
        if not base or not quote:
            raise CandleError(f"symbol_invalid:{canonical}")
        # Binance spot quotes USD pairs in USDT/USDC; that is a different instrument (stablecoin basis),
        # so an exact USD market is not silently substituted.
        return f"{base}{quote}"
    if provider == "oanda":
        return canonical.replace("/", "_").replace("-", "_")
    raise CandleError(f"provider_unknown:{provider}")


# --------------------------------------------------------------------------- HTTP resilience
@dataclass
class RetryingHttp:
    """Wraps an HTTP client with a per-host minimum interval and bounded exponential backoff.

    Retries: connection errors, 429 and 5xx. Never retried: 451 (restricted location),
    401/403 (credentials) and other 4xx. Delays are deterministic (no jitter) so tests and
    replays are reproducible; Retry-After (seconds) overrides the computed delay, capped.
    """

    inner: Any = None
    min_interval_s: float = 0.25
    max_attempts: int = 4
    base_delay_s: float = 0.5
    max_delay_s: float = 8.0
    sleep: Callable[[float], None] = time.sleep
    monotonic: Callable[[], float] = time.monotonic
    attempts_log: list[dict] = field(default_factory=list)
    _last_call: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.inner is None:
            self.inner = _requests_session()

    def _throttle(self, host: str) -> None:
        last = self._last_call.get(host)
        if last is not None:
            wait = self.min_interval_s - (self.monotonic() - last)
            if wait > 0:
                self.sleep(wait)
        self._last_call[host] = self.monotonic()

    def get(self, url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 10.0):
        host = url.split("/")[2] if "://" in url else url
        delay = self.base_delay_s
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            self._throttle(host)
            try:
                resp = self.inner.get(url, params=params, headers=headers, timeout=timeout)
            except (OSError, ConnectionError) as exc:  # requests' errors subclass OSError
                last_exc = exc
                self.attempts_log.append({"host": host, "attempt": attempt, "error": type(exc).__name__})
            else:
                status = int(getattr(resp, "status_code", 200) or 0)
                self.attempts_log.append({"host": host, "attempt": attempt, "status": status})
                if status != 429 and status < 500:
                    return resp
                if attempt == self.max_attempts:
                    return resp
                retry_after = _retry_after_s(resp)
                if retry_after is not None:
                    delay = min(self.max_delay_s, retry_after)
            if attempt < self.max_attempts:
                self.sleep(min(self.max_delay_s, delay))
                delay = min(self.max_delay_s, delay * 2)
        raise CandleError(f"fetch_failed_after_retries:{type(last_exc).__name__ if last_exc else 'unknown'}")


def _retry_after_s(resp) -> float | None:
    headers = getattr(resp, "headers", None) or {}
    raw = headers.get("Retry-After") if hasattr(headers, "get") else None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def resilient_http() -> RetryingHttp:
    return RetryingHttp(_requests_session())


# --------------------------------------------------------------------------- providers
def _rfc3339(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_rfc3339(raw: Any) -> int:
    text = str(raw or "")
    if not text.endswith("Z") or len(text) < 20:
        raise CandleError("timestamp_invalid")
    return int(datetime.strptime(text[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())


class AlpacaCryptoPublicCandles:
    """Alpaca crypto bars (v1beta3, US location). Public: no API key is sent or required."""

    source = "alpaca_crypto_public"
    classification = LIVE

    def __init__(self, http: _Http | None = None, *, clock=None, base_url: str = ALPACA_DATA_BASE) -> None:
        if base_url.rstrip("/") != ALPACA_DATA_BASE:
            raise CandleError("alpaca_non_data_host_refused")
        self.http = http or _requests_session()
        self.clock = clock or _now_utc

    def fetch(self, instrument: str, *, granularity_s: int, end: datetime | None = None) -> CandleSeries:
        tf = ALPACA_TIMEFRAMES.get(granularity_s)
        if tf is None:
            raise CandleError("granularity_unsupported")
        symbol = normalize_symbol("alpaca_crypto", instrument)
        end_dt = end or self.clock()
        # Newest first: with ascending order a page that hits the limit (or a page-size cap) ends
        # in the past, and the "latest" bar was weeks old (seen on the real endpoint, run 38882824767).
        params = {"symbols": symbol, "timeframe": tf, "limit": 1000, "sort": "desc",
                  "start": _rfc3339(end_dt.timestamp() - 1000 * granularity_s), "end": _rfc3339(end_dt.timestamp())}
        resp = self.http.get(f"{ALPACA_DATA_BASE}/v1beta3/crypto/us/bars", params=params, timeout=10.0)
        check_http(resp)
        body = resp.json()
        rows = ((body or {}).get("bars") or {}).get(symbol)
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            raise CandleError("response_invalid")
        candles = []
        for r in rows:
            try:
                candles.append(Candle(_parse_rfc3339(r["t"]), float(r["o"]), float(r["h"]), float(r["l"]),
                                      float(r["c"]), float(r["v"])))
            except (KeyError, TypeError, ValueError) as exc:
                raise CandleError("row_invalid") from exc
        candles.sort(key=lambda c: c.ts)
        series = CandleSeries(instrument.replace("/", "-"), "CRYPTO", granularity_s, self.source, tuple(candles),
                              self.classification)
        # Alpaca crypto omits bars with no trades, so sparse gaps are normal; the caller's
        # completeness check (series_metrics) reports them.
        return validate(drop_incomplete(series, now=self.clock()), allow_gaps=1000)


class AlpacaStockCandles:
    """US equity bars from the free IEX feed. Requires APCA_API_KEY_ID / APCA_API_SECRET_KEY."""

    source = "alpaca_iex"
    classification = INDICATIVE  # single exchange, not the consolidated SIP tape

    def __init__(self, http: _Http | None = None, *, key_id: str | None = None, secret: str | None = None,
                 clock=None) -> None:
        self.http = http or _requests_session()
        self.key_id = key_id if key_id is not None else os.environ.get("APCA_API_KEY_ID", "")
        self.secret = secret if secret is not None else os.environ.get("APCA_API_SECRET_KEY", "")
        self.clock = clock or _now_utc

    def fetch(self, instrument: str, *, granularity_s: int, end: datetime | None = None) -> CandleSeries:
        tf = ALPACA_TIMEFRAMES.get(granularity_s)
        if tf is None:
            raise CandleError("granularity_unsupported")
        if not (self.key_id and self.secret):
            raise CandleError("alpaca_credentials_missing")
        symbol = normalize_symbol("alpaca_stock", instrument)
        end_dt = end or self.clock()
        params = {"timeframe": tf, "feed": "iex", "limit": 1000, "adjustment": "raw", "sort": "desc",
                  "start": _rfc3339(end_dt.timestamp() - 1000 * granularity_s * 3), "end": _rfc3339(end_dt.timestamp())}
        resp = self.http.get(f"{ALPACA_DATA_BASE}/v2/stocks/{symbol}/bars", params=params, timeout=10.0,
                             headers={"APCA-API-KEY-ID": self.key_id, "APCA-API-SECRET-KEY": self.secret})
        check_http(resp)
        rows = (resp.json() or {}).get("bars") or []
        candles = []
        for r in rows:
            try:
                candles.append(Candle(_parse_rfc3339(r["t"]), float(r["o"]), float(r["h"]), float(r["l"]),
                                      float(r["c"]), float(r["v"])))
            except (KeyError, TypeError, ValueError) as exc:
                raise CandleError("row_invalid") from exc
        candles.sort(key=lambda c: c.ts)
        series = CandleSeries(symbol, "EQUITY", granularity_s, self.source, tuple(candles), self.classification)
        return validate(drop_incomplete(series, now=self.clock()), allow_gaps=100_000)  # sessions/weekends


def binance_eligibility(operating_country: str | None) -> tuple[bool, str]:
    country = (operating_country if operating_country is not None
               else os.environ.get("CSS_OPERATING_COUNTRY", "")).strip().upper()
    if len(country) != 2 or not country.isalpha():
        return False, "binance_operating_country_unattested"
    if country in BINANCE_RESTRICTED_COUNTRIES:
        return False, f"binance_jurisdiction_restricted:{country}"
    return True, f"attested:{country}"


class BinanceSpotPublicCandles:
    """Binance Spot klines from the public market-data host only (no key, no account access)."""

    source = "binance_spot_public"
    classification = LIVE

    def __init__(self, http: _Http | None = None, *, operating_country: str | None = None, clock=None,
                 base_url: str = BINANCE_PUBLIC_BASE) -> None:
        if base_url.rstrip("/") != BINANCE_PUBLIC_BASE:
            raise CandleError("binance_non_public_host_refused")
        self.eligible, self.eligibility_reason = binance_eligibility(operating_country)
        self.http = http or _requests_session()
        self.clock = clock or _now_utc

    def fetch(self, instrument: str, *, granularity_s: int, end: datetime | None = None) -> CandleSeries:
        if not self.eligible:
            raise CandleError(self.eligibility_reason)  # refused before any request is made
        interval = BINANCE_INTERVALS.get(granularity_s)
        if interval is None:
            raise CandleError("granularity_unsupported")
        symbol = normalize_symbol("binance", instrument)
        params: dict = {"symbol": symbol, "interval": interval, "limit": 1000}
        if end is not None:
            params["endTime"] = int(end.timestamp() * 1000)
        resp = self.http.get(f"{BINANCE_PUBLIC_BASE}/api/v3/klines", params=params, timeout=10.0)
        check_http(resp)
        rows = resp.json()
        if not isinstance(rows, list):
            raise CandleError("response_invalid")
        candles = []
        for r in rows:  # [openTime ms, o, h, l, c, v, closeTime ms, quoteVol, trades, ...]
            if not isinstance(r, list) or len(r) < 7:
                raise CandleError("row_invalid")
            try:
                candles.append(Candle(int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]),
                                      float(r[5])))
            except (TypeError, ValueError) as exc:
                raise CandleError("row_invalid") from exc
        candles.sort(key=lambda c: c.ts)
        series = CandleSeries(instrument.replace("/", "-").upper(), "CRYPTO", granularity_s, self.source,
                              tuple(candles), self.classification)
        return validate(drop_incomplete(series, now=self.clock()), allow_gaps=10)


class BlockedFeed:
    """An asset class with no authorized data feed. Always refuses; never fabricates data."""

    classification = "BLOCKED"

    def __init__(self, asset_class: str, reason: str) -> None:
        self.asset_class = asset_class.upper()
        self.reason = reason
        self.source = f"blocked_{asset_class.lower()}"

    def fetch(self, instrument: str, *, granularity_s: int, end: datetime | None = None) -> CandleSeries:
        raise CandleError(f"feed_blocked:{self.asset_class}:{self.reason}")


OPTIONS_FEED = BlockedFeed("OPTIONS", "no_authorized_options_feed")
FUTURES_FEED = BlockedFeed("FUTURES", "no_authorized_futures_feed")


class ReplayCandleProvider:
    """Deterministic replay: returns cached bars complete at the replay clock, classified REPLAY."""

    classification = REPLAY

    def __init__(self, store: CsvCandleStore, *, source: str, asset_class: str, clock: Callable[[], datetime]) -> None:
        self.store, self.source, self.asset_class, self.clock = store, source, asset_class, clock

    def fetch(self, instrument: str, *, granularity_s: int, end: datetime | None = None) -> CandleSeries:
        full = self.store.load(self.source, instrument, self.asset_class, granularity_s)
        as_of = end or self.clock()
        return drop_incomplete(full, now=as_of)


# --------------------------------------------------------------------------- quality checks
@dataclass(frozen=True)
class Discrepancy:
    overlap_bars: int
    max_bps: float
    median_bps: float
    last_bps: float


def compare_series(a: CandleSeries, b: CandleSeries) -> Discrepancy:
    """Close-to-close deviation on bars both providers report (same open time)."""
    if a.granularity_s != b.granularity_s:
        raise CandleError("granularity_mismatch")
    bmap = {c.ts: c.close for c in b.candles}
    devs = [abs(c.close - bmap[c.ts]) / bmap[c.ts] * 1e4 for c in a.candles if c.ts in bmap]
    if not devs:
        raise CandleError("no_overlapping_bars")
    return Discrepancy(len(devs), max(devs), statistics.median(devs), devs[-1])


@dataclass(frozen=True)
class SeriesMetrics:
    bars: int
    expected_bars: int
    completeness: float
    realised_vol_bps: float  # stdev of bar log-returns, in bps per bar
    median_volume: float
    last_volume: float
    zero_volume_bars: int


def series_metrics(series: CandleSeries) -> SeriesMetrics:
    cs = series.candles
    if len(cs) < 2:
        raise CandleError("insufficient_bars")
    expected = (cs[-1].ts - cs[0].ts) // series.granularity_s + 1
    rets = [math.log(cs[i].close / cs[i - 1].close) for i in range(1, len(cs))]
    vols = [c.volume for c in cs]
    return SeriesMetrics(len(cs), int(expected), len(cs) / expected, statistics.pstdev(rets) * 1e4,
                         statistics.median(vols), vols[-1], sum(1 for v in vols if v == 0))


def check_complete(series: CandleSeries, *, min_completeness: float = 0.98) -> None:
    m = series_metrics(series)
    if m.completeness < min_completeness:
        raise CandleError(f"candles_incomplete:{m.completeness:.3f}")


# --------------------------------------------------------------------------- failover
@dataclass
class FailoverCandleProvider:
    """Try providers in order; record every attempt. Optionally cross-check the chosen series
    against a reference provider and refuse when the last overlapping close deviates too much."""

    providers: Sequence[CandleProvider]
    cross_check: CandleProvider | None = None
    max_discrepancy_bps: float = 50.0
    last_attempts: list[dict] = field(default_factory=list)
    last_discrepancy: Discrepancy | None = None

    @property
    def source(self) -> str:
        return "failover:" + ",".join(getattr(p, "source", "?") for p in self.providers)

    def fetch(self, instrument: str, *, granularity_s: int, end: datetime | None = None) -> CandleSeries:
        self.last_attempts, self.last_discrepancy = [], None
        chosen: CandleSeries | None = None
        for p in self.providers:
            try:
                chosen = p.fetch(instrument, granularity_s=granularity_s, end=end)
                self.last_attempts.append({"source": getattr(p, "source", "?"), "ok": True})
                break
            except (CandleError, OSError, ValueError) as exc:
                self.last_attempts.append({"source": getattr(p, "source", "?"), "ok": False, "reason": str(exc)})
        if chosen is None:
            raise CandleError("all_providers_failed:" + ";".join(
                f"{a['source']}={a.get('reason')}" for a in self.last_attempts))
        if self.cross_check is not None:
            try:
                ref = self.cross_check.fetch(instrument, granularity_s=granularity_s, end=end)
            except (CandleError, OSError, ValueError) as exc:
                raise CandleError(f"cross_check_unavailable:{exc}") from exc
            d = compare_series(chosen, ref)
            self.last_discrepancy = d
            if d.last_bps > self.max_discrepancy_bps:
                raise CandleError(f"cross_provider_discrepancy:{d.last_bps:.1f}bps")
        return chosen


# --------------------------------------------------------------------------- quotes / depth
@dataclass(frozen=True)
class QuoteSnapshot:
    instrument: str
    source: str
    bid: float
    ask: float
    exchange_ts: datetime
    bid_depth_notional: float | None = None  # sum of price*size within depth_bps of mid
    ask_depth_notional: float | None = None

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread_bps(self) -> float:
        return (self.ask - self.bid) / self.mid * 1e4


def _validate_quote(q: QuoteSnapshot, *, now: datetime, max_age_s: float) -> QuoteSnapshot:
    if not all(math.isfinite(v) and v > 0 for v in (q.bid, q.ask)):
        raise CandleError("quote_price_invalid")
    if q.ask < q.bid:
        raise CandleError("quote_crossed")
    age = (now - q.exchange_ts).total_seconds()
    if age > max_age_s:
        raise CandleError("quote_stale")
    if age < -5:
        raise CandleError("quote_from_future")
    return q


def _depth(levels: Sequence[Sequence[Any]], mid: float, within_bps: float) -> float:
    total = 0.0
    for lvl in levels:
        price, size = float(lvl[0]), float(lvl[1])
        if abs(price - mid) / mid * 1e4 <= within_bps:
            total += price * size
    return total


class CoinbaseQuotes:
    source = "coinbase_exchange_public"

    def __init__(self, http: _Http | None = None, *, clock=None, max_age_s: float = 30.0) -> None:
        self.http, self.clock, self.max_age_s = http or _requests_session(), clock or _now_utc, max_age_s

    def quote(self, instrument: str, *, depth_bps: float = 25.0) -> QuoteSnapshot:
        pid = normalize_symbol("coinbase", instrument)
        resp = self.http.get(f"{COINBASE_BASE}/products/{pid}/book", params={"level": 2}, timeout=10.0)
        check_http(resp)
        book = resp.json()
        tick = self.http.get(f"{COINBASE_BASE}/products/{pid}/ticker", timeout=10.0)
        check_http(tick)
        t = tick.json()
        try:
            bid, ask = float(book["bids"][0][0]), float(book["asks"][0][0])
            ts = datetime.fromisoformat(str(t["time"]).replace("Z", "+00:00"))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise CandleError("quote_response_invalid") from exc
        mid = (bid + ask) / 2
        q = QuoteSnapshot(instrument, self.source, bid, ask, ts, _depth(book["bids"], mid, depth_bps),
                          _depth(book["asks"], mid, depth_bps))
        return _validate_quote(q, now=self.clock(), max_age_s=self.max_age_s)


class AlpacaCryptoQuotes:
    source = "alpaca_crypto_public"

    def __init__(self, http: _Http | None = None, *, clock=None, max_age_s: float = 30.0) -> None:
        self.http, self.clock, self.max_age_s = http or _requests_session(), clock or _now_utc, max_age_s

    def quote(self, instrument: str, *, depth_bps: float = 25.0) -> QuoteSnapshot:
        sym = normalize_symbol("alpaca_crypto", instrument)
        resp = self.http.get(f"{ALPACA_DATA_BASE}/v1beta3/crypto/us/latest/orderbooks", params={"symbols": sym},
                             timeout=10.0)
        check_http(resp)
        try:
            ob = resp.json()["orderbooks"][sym]
            bids = [(b["p"], b["s"]) for b in ob["b"]]
            asks = [(a["p"], a["s"]) for a in ob["a"]]
            bid, ask = float(bids[0][0]), float(asks[0][0])
            ts = datetime.fromisoformat(str(ob["t"]).replace("Z", "+00:00"))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise CandleError("quote_response_invalid") from exc
        mid = (bid + ask) / 2
        q = QuoteSnapshot(instrument, self.source, bid, ask, ts, _depth(bids, mid, depth_bps), _depth(asks, mid, depth_bps))
        return _validate_quote(q, now=self.clock(), max_age_s=self.max_age_s)


class BinanceQuotes:
    source = "binance_spot_public"

    def __init__(self, http: _Http | None = None, *, operating_country: str | None = None, clock=None,
                 max_age_s: float = 30.0) -> None:
        self.eligible, self.eligibility_reason = binance_eligibility(operating_country)
        self.http, self.clock, self.max_age_s = http or _requests_session(), clock or _now_utc, max_age_s

    def quote(self, instrument: str, *, depth_bps: float = 25.0) -> QuoteSnapshot:
        if not self.eligible:
            raise CandleError(self.eligibility_reason)
        sym = normalize_symbol("binance", instrument)
        server = self.http.get(f"{BINANCE_PUBLIC_BASE}/api/v3/time", timeout=10.0)
        check_http(server)
        resp = self.http.get(f"{BINANCE_PUBLIC_BASE}/api/v3/depth", params={"symbol": sym, "limit": 100}, timeout=10.0)
        check_http(resp)
        try:
            book = resp.json()
            bid, ask = float(book["bids"][0][0]), float(book["asks"][0][0])
            # The depth snapshot carries no timestamp; use the exchange's server time fetched just before.
            ts = datetime.fromtimestamp(int(server.json()["serverTime"]) / 1000, tz=timezone.utc)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise CandleError("quote_response_invalid") from exc
        mid = (bid + ask) / 2
        q = QuoteSnapshot(instrument, self.source, bid, ask, ts, _depth(book["bids"], mid, depth_bps),
                          _depth(book["asks"], mid, depth_bps))
        return _validate_quote(q, now=self.clock(), max_age_s=self.max_age_s)


# --------------------------------------------------------------------------- clock skew
def measure_clock_skew(server_time: Callable[[], datetime], *, clock: Callable[[], datetime] = _now_utc) -> float:
    """Exchange time minus local time (seconds), using the midpoint of the request."""
    t0 = clock()
    server = server_time()
    t1 = clock()
    local_mid = t0 + (t1 - t0) / 2
    return (server - local_mid).total_seconds()


def coinbase_server_time(http: _Http | None = None) -> Callable[[], datetime]:
    http = http or _requests_session()

    def _get() -> datetime:
        resp = http.get(f"{COINBASE_BASE}/time", timeout=10.0)
        check_http(resp)
        return datetime.fromisoformat(str(resp.json()["iso"]).replace("Z", "+00:00"))
    return _get


def check_clock_skew(skew_s: float, *, max_skew_s: float = 5.0) -> None:
    if not math.isfinite(skew_s) or abs(skew_s) > max_skew_s:
        raise CandleError(f"clock_skew_exceeded:{skew_s:.2f}s")


# --------------------------------------------------------------------------- readiness matrix
def provider_matrix(env: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """Static readiness (no network): what each provider needs and whether it is present.
    A READY row still needs a live probe (tools/css_market_data_matrix.py --probe) to PASS."""
    env = dict(os.environ if env is None else env)
    ok_binance, why_binance = binance_eligibility(env.get("CSS_OPERATING_COUNTRY", ""))
    has_alpaca = bool(env.get("APCA_API_KEY_ID") and env.get("APCA_API_SECRET_KEY"))
    has_oanda = bool(env.get("OANDA_PRACTICE_TOKEN"))
    # Questrade: presence of an operator-authorized OAuth refresh-token reference only (never the value).
    has_questrade = bool(env.get("QUESTRADE_REFRESH_TOKEN") or env.get("QUESTRADE_SECRET_STORE_PROVIDER"))
    return [
        {"provider": "coinbase_exchange_public", "asset_class": "CRYPTO", "classification": LIVE,
         "credentials": "none", "status": "READY", "reason": "public endpoint"},
        {"provider": "alpaca_crypto_public", "asset_class": "CRYPTO", "classification": LIVE,
         "credentials": "none", "status": "READY", "reason": "public endpoint"},
        {"provider": "binance_spot_public", "asset_class": "CRYPTO", "classification": LIVE,
         "credentials": "none", "status": "READY" if ok_binance else "BLOCKED", "reason": why_binance},
        {"provider": "alpaca_iex", "asset_class": "EQUITY", "classification": INDICATIVE,
         "credentials": "APCA_API_KEY_ID/APCA_API_SECRET_KEY",
         "status": "READY" if has_alpaca else "BLOCKED", "reason": "keys present" if has_alpaca else "alpaca_credentials_missing"},
        {"provider": "oanda_practice", "asset_class": "FX", "classification": LIVE,
         "credentials": "OANDA_PRACTICE_TOKEN",
         "status": "READY" if has_oanda else "BLOCKED", "reason": "token present" if has_oanda else "oanda_practice_token_missing"},
        {"provider": "questrade_api", "asset_class": "EQUITY", "classification": "LIVE_IF_ENTITLED_ELSE_DELAYED",
         "credentials": "Questrade OAuth (operator-authorized refresh token)",
         "status": "READY" if has_questrade else "BLOCKED",
         "reason": "token reference present" if has_questrade else "questrade_oauth_authorization_required"},
        {"provider": OPTIONS_FEED.source, "asset_class": "OPTIONS", "classification": "BLOCKED", "credentials": "n/a",
         "status": "BLOCKED", "reason": OPTIONS_FEED.reason},
        {"provider": FUTURES_FEED.source, "asset_class": "FUTURES", "classification": "BLOCKED", "credentials": "n/a",
         "status": "BLOCKED", "reason": FUTURES_FEED.reason},
    ]


def build_provider(name: str, *, http: _Http | None = None, env: Mapping[str, str] | None = None) -> CandleProvider:
    env = dict(os.environ if env is None else env)
    http = http or resilient_http()
    if name == "coinbase":
        return CoinbasePublicCandles(http)
    if name == "alpaca_crypto":
        return AlpacaCryptoPublicCandles(http)
    if name == "alpaca_stock":
        return AlpacaStockCandles(http, key_id=env.get("APCA_API_KEY_ID", ""), secret=env.get("APCA_API_SECRET_KEY", ""))
    if name == "binance":
        return BinanceSpotPublicCandles(http, operating_country=env.get("CSS_OPERATING_COUNTRY", ""))
    if name == "oanda":
        return OandaPracticeCandles(http, token=env.get("OANDA_PRACTICE_TOKEN", ""))
    if name == "options":
        return OPTIONS_FEED
    if name == "futures":
        return FUTURES_FEED
    raise CandleError(f"provider_unknown:{name}")


PROVIDER_NAMES = ("coinbase", "alpaca_crypto", "binance", "alpaca_stock", "oanda", "options", "futures")
SOURCE_BY_NAME = {"coinbase": "coinbase_exchange_public", "alpaca_crypto": "alpaca_crypto_public",
                  "binance": "binance_spot_public", "alpaca_stock": "alpaca_iex", "oanda": "oanda_practice"}

