"""Market candles: validated, provenance-tagged, read-only.

Providers fetch real OHLC data over read-only public/practice endpoints. Nothing here can
place an order. Every series is validated (UTC, strictly increasing, uniform interval, OHLC
consistency, finite positive prices) and carries a SHA-256 digest so calibration artifacts can
pin exactly which data they were fitted on.

Providers
  CoinbasePublicCandles   api.exchange.coinbase.com (no credentials; crypto spot)
  OandaPracticeCandles    api-fxpractice.oanda.com only (practice token; FX). The live
                          trading host is refused.
  CsvCandleStore          local cache/replay so validation is reproducible offline.

More providers (Alpaca crypto/IEX, Binance public spot, failover, cross-provider checks,
quotes/depth, clock skew, blocked options/futures feeds) live in backend.signals.market_data.

Data classification (closeout): every series carries one of LIVE, DELAYED, INDICATIVE, REPLAY
or SYNTHETIC. The producer routes LIVE only by default; REPLAY/SYNTHETIC can never reach a
live-signal decision (backend.signals.producer).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Protocol, Sequence

COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
OANDA_PRACTICE_BASE = "https://api-fxpractice.oanda.com/v3"
OANDA_GRANULARITY = {60: "M1", 300: "M5", 900: "M15", 3600: "H1", 14400: "H4", 86400: "D"}
COINBASE_GRANULARITIES = {60, 300, 900, 3600, 21600, 86400}


LIVE = "LIVE"                # venue's own real-time data (venue-specific, not consolidated)
DELAYED = "DELAYED"          # real data published with a delay
INDICATIVE = "INDICATIVE"    # real but partial/non-executable reference (e.g. IEX-only equities)
REPLAY = "REPLAY"            # cached historical bars replayed deterministically
SYNTHETIC = "SYNTHETIC"      # generated; tests and simulations only
CLASSIFICATIONS = frozenset({LIVE, DELAYED, INDICATIVE, REPLAY, SYNTHETIC})


class CandleError(ValueError):
    """Invalid or unavailable market data; message is a stable reason code."""


@dataclass(frozen=True)
class Candle:
    ts: int  # bar open time, epoch seconds UTC
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class CandleSeries:
    instrument: str
    asset_class: str
    granularity_s: int
    source: str
    candles: tuple[Candle, ...]
    # Not part of the digest: the same bars keep the same digest whether live or replayed.
    classification: str = "UNCLASSIFIED"

    @property
    def digest(self) -> str:
        h = hashlib.sha256(f"{self.instrument}|{self.asset_class}|{self.granularity_s}|{self.source}".encode())
        for c in self.candles:
            h.update(f"|{c.ts},{c.open!r},{c.high!r},{c.low!r},{c.close!r},{c.volume!r}".encode())
        return h.hexdigest()

    def closes(self) -> list[float]:
        return [c.close for c in self.candles]


def validate(series: CandleSeries, *, allow_gaps: int = 0) -> CandleSeries:
    """Strict validation; returns the series or raises CandleError."""
    if series.granularity_s <= 0:
        raise CandleError("granularity_invalid")
    gaps = 0
    prev: Candle | None = None
    for c in series.candles:
        values = (c.open, c.high, c.low, c.close)
        if not all(isinstance(v, float) and math.isfinite(v) and v > 0 for v in values):
            raise CandleError(f"price_invalid:{c.ts}")
        if not (math.isfinite(c.volume) and c.volume >= 0):
            raise CandleError(f"volume_invalid:{c.ts}")
        if c.high < max(c.open, c.close, c.low) or c.low > min(c.open, c.close, c.high):
            raise CandleError(f"ohlc_inconsistent:{c.ts}")
        if c.ts % series.granularity_s:
            raise CandleError(f"bar_misaligned:{c.ts}")
        if prev is not None:
            step = c.ts - prev.ts
            if step <= 0:
                raise CandleError(f"not_strictly_increasing:{c.ts}")
            if step != series.granularity_s:
                gaps += step // series.granularity_s - 1
                if gaps > allow_gaps:
                    raise CandleError(f"gap:{prev.ts}->{c.ts}")
        prev = c
    return series


def drop_incomplete(series: CandleSeries, *, now: datetime) -> CandleSeries:
    """Remove bars that have not closed yet. Exchanges (e.g. Coinbase) return the forming bar;
    using it would compute features on a bar whose close is not final."""
    cutoff = now.timestamp()
    kept = tuple(c for c in series.candles if c.ts + series.granularity_s <= cutoff)
    if len(kept) == len(series.candles):
        return series
    return CandleSeries(series.instrument, series.asset_class, series.granularity_s, series.source, kept,
                        series.classification)


def check_fresh(series: CandleSeries, *, now: datetime, max_bars_stale: int = 2) -> None:
    """The newest complete bar must be recent: stale data never produces a live signal."""
    if not series.candles:
        raise CandleError("no_candles")
    newest_close_time = series.candles[-1].ts + series.granularity_s
    age = now.timestamp() - newest_close_time
    if age < -series.granularity_s:
        raise CandleError("data_from_future")
    if age > max_bars_stale * series.granularity_s:
        raise CandleError("data_stale")


class CandleProvider(Protocol):
    source: str

    def fetch(self, instrument: str, *, granularity_s: int, end: datetime | None = None) -> CandleSeries: ...


class _Http(Protocol):
    def get(self, url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 10.0): ...


def check_http(resp) -> None:
    """Map HTTP failures to stable reason codes. 451 (restricted location) is authoritative and is
    never retried or routed around; 401/403 mean credentials or entitlement are missing."""
    if not hasattr(resp, "status_code"):  # minimal response objects (tests): defer to them
        resp.raise_for_status()
        return
    status = int(resp.status_code or 0)
    if 200 <= status < 300:
        return
    if status == 451:
        raise CandleError("restricted_location")
    if status in (401, 403):
        raise CandleError(f"credentials_rejected:{status}")
    if status == 429:
        raise CandleError("rate_limited")
    raise CandleError(f"http_status:{status}")


def _requests_session() -> _Http:
    import requests

    return requests.Session()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class CoinbasePublicCandles:
    source = "coinbase_exchange_public"
    classification = LIVE

    def __init__(self, http: _Http | None = None, *, asset_class: str = "CRYPTO", clock=None) -> None:
        self.http = http or _requests_session()
        self.asset_class = asset_class
        self.clock = clock or _now_utc

    def fetch(self, instrument: str, *, granularity_s: int, end: datetime | None = None) -> CandleSeries:
        if granularity_s not in COINBASE_GRANULARITIES:
            raise CandleError("granularity_unsupported")
        params: dict = {"granularity": granularity_s}
        if end is not None:
            start = datetime.fromtimestamp(end.timestamp() - 300 * granularity_s, tz=timezone.utc)
            params.update(start=start.isoformat(), end=end.isoformat())
        resp = self.http.get(COINBASE_CANDLES_URL.format(product_id=instrument), params=params, timeout=10.0)
        check_http(resp)
        rows = resp.json()
        if not isinstance(rows, list):
            raise CandleError("response_invalid")
        candles = []
        for row in rows:  # [time, low, high, open, close, volume], newest first
            if not isinstance(row, list) or len(row) < 6:
                raise CandleError("row_invalid")
            ts, low, high, open_, close, vol = row[:6]
            candles.append(Candle(int(ts), float(open_), float(high), float(low), float(close), float(vol)))
        candles.sort(key=lambda c: c.ts)
        series = CandleSeries(instrument, self.asset_class, granularity_s, self.source, tuple(candles), self.classification)
        return validate(drop_incomplete(series, now=self.clock()), allow_gaps=10)


class OandaPracticeCandles:
    """FX candles from the OANDA PRACTICE host only (read-only). Token from OANDA_PRACTICE_TOKEN."""

    source = "oanda_practice"
    # OANDA's own dealer prices (practice environment): real-time but broker-specific, and
    # FX has no consolidated tape. LIVE here means "real-time from this venue", nothing more.
    classification = LIVE

    def __init__(self, http: _Http | None = None, *, token: str | None = None, base_url: str = OANDA_PRACTICE_BASE) -> None:
        if base_url.rstrip("/") != OANDA_PRACTICE_BASE:
            raise CandleError("oanda_non_practice_host_refused")
        self.http = http or _requests_session()
        self.token = token if token is not None else os.environ.get("OANDA_PRACTICE_TOKEN", "")
        self.base_url = base_url

    def fetch(self, instrument: str, *, granularity_s: int, end: datetime | None = None) -> CandleSeries:
        gran = OANDA_GRANULARITY.get(granularity_s)
        if gran is None:
            raise CandleError("granularity_unsupported")
        if not self.token:
            raise CandleError("oanda_practice_token_missing")
        params: dict = {"granularity": gran, "price": "M", "count": 500}
        if end is not None:
            params = {"granularity": gran, "price": "M", "to": end.isoformat(), "count": 500}
        resp = self.http.get(f"{self.base_url}/instruments/{instrument}/candles", params=params,
                             headers={"Authorization": f"Bearer {self.token}"}, timeout=10.0)
        check_http(resp)
        candles = []
        for row in resp.json().get("candles", []):
            if not row.get("complete", False):
                continue  # never use a forming bar
            mid = row["mid"]
            ts = _oanda_ts(str(row["time"]))
            candles.append(Candle(ts, float(mid["o"]), float(mid["h"]), float(mid["l"]), float(mid["c"]),
                                  float(row.get("volume", 0))))
        candles.sort(key=lambda c: c.ts)
        return validate(CandleSeries(instrument.replace("_", "/"), "FX", granularity_s, self.source, tuple(candles),
                                     self.classification), allow_gaps=200)  # FX weekends


def _oanda_ts(raw: str) -> int:
    """OANDA RFC3339 with nanoseconds, always UTC ('...Z'): parse the second-resolution prefix."""
    if not raw.endswith("Z") or len(raw) < 20:
        raise CandleError("timestamp_invalid")
    return int(datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())


class CsvCandleStore:
    """Local cache: one CSV per (source, instrument, granularity). Reproducible offline replay."""

    HEADER = ("ts", "open", "high", "low", "close", "volume")

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def _path(self, source: str, instrument: str, granularity_s: int) -> Path:
        safe = instrument.replace("/", "-").replace("_", "-")
        return self.root / source / f"{safe}_{granularity_s}.csv"

    def save(self, series: CandleSeries) -> Path:
        path = self._path(series.source, series.instrument, series.granularity_s)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = {c.ts: c for c in self.load(series.source, series.instrument, series.asset_class,
                                                series.granularity_s).candles} if path.exists() else {}
        existing.update({c.ts: c for c in series.candles})
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(self.HEADER)
            for ts in sorted(existing):
                c = existing[ts]
                w.writerow([c.ts, repr(c.open), repr(c.high), repr(c.low), repr(c.close), repr(c.volume)])
        meta = path.with_suffix(".meta.json")
        meta.write_text(json.dumps({"instrument": series.instrument, "asset_class": series.asset_class,
                                    "granularity_s": series.granularity_s, "source": series.source}), encoding="utf-8")
        return path

    def load(self, source: str, instrument: str, asset_class: str, granularity_s: int) -> CandleSeries:
        path = self._path(source, instrument, granularity_s)
        if not path.exists():
            raise CandleError("cache_missing")
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        candles = tuple(Candle(int(r["ts"]), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
                               float(r["volume"])) for r in rows)
        return CandleSeries(instrument, asset_class, granularity_s, source, candles, REPLAY)


def merge(parts: Iterable[CandleSeries]) -> CandleSeries:
    parts = list(parts)
    if not parts:
        raise CandleError("no_candles")
    first = parts[0]
    by_ts = {c.ts: c for p in parts for c in p.candles}
    return CandleSeries(first.instrument, first.asset_class, first.granularity_s, first.source,
                        tuple(by_ts[t] for t in sorted(by_ts)), first.classification)


def closes_sequence(series: CandleSeries) -> Sequence[float]:
    return tuple(c.close for c in series.candles)
