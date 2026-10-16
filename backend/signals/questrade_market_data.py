"""Questrade market data for the CSS signal pipeline (READ-ONLY; issue #129).

Uses the existing allowlisted, GET-only QuestradeReadOnlyClient (OAuth access token from the
operator-authorized TokenLifecycle; tokens are never logged). Nothing here can place, change or
cancel an order.

  QuestradeCandles   historical bars for Canadian / US listed equities -> CandleSeries
                     symbol -> symbolId discovery, normalised metadata (currency, listing
                     exchange, security type) and data entitlement: a quote delay of 0 is
                     classified LIVE, anything else (or unknown) DELAYED - never upgraded.

Failures map to stable reason codes `questrade:<FAILURE_CODE>` (e.g. ACCESS_TOKEN_REQUIRED,
AUTHORIZATION_REVOKED, RATE_LIMITED, PATH_NOT_ALLOWLISTED); no data is ever fabricated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from backend.signals.candles import DELAYED, LIVE, Candle, CandleError, CandleSeries, _now_utc, drop_incomplete, validate

SOURCE = "questrade_api"
QUESTRADE_INTERVALS = {60: "OneMinute", 300: "FiveMinutes", 900: "FifteenMinutes", 1800: "HalfHour",
                       3600: "OneHour", 14400: "FourHours", 86400: "OneDay"}
MAX_CANDLES_PER_REQUEST = 2000


@dataclass(frozen=True)
class QuestradeInstrument:
    symbol: str
    symbol_id: int
    currency: str
    listing_exchange: str
    security_type: str
    description: str
    delay_minutes: int | None  # None: entitlement unknown

    @property
    def classification(self) -> str:
        return LIVE if self.delay_minutes == 0 else DELAYED

    def provenance(self) -> dict[str, Any]:
        return {"source": SOURCE, "daily_bar_key": "trading_date_00:00Z", "symbol": self.symbol, "symbol_id": self.symbol_id, "currency": self.currency,
                "venue": self.listing_exchange, "security_type": self.security_type,
                "entitlement": "REAL_TIME" if self.delay_minutes == 0 else (
                    f"DELAYED_{self.delay_minutes}_MIN" if self.delay_minutes else "UNKNOWN_TREATED_AS_DELAYED"),
                "classification": self.classification}


def _payload(client: Any, path: str, params: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    result = client.request(path, params=dict(params or {}))
    if not result.success:
        raise CandleError(f"questrade:{result.failure_code or 'UNAVAILABLE'}")
    return result.payload


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _parse_ts(raw: Any, granularity_s: int) -> int:
    try:
        dt = datetime.fromisoformat(str(raw))
    except ValueError as exc:
        raise CandleError("row_invalid") from exc
    if dt.tzinfo is None:
        raise CandleError("row_invalid")  # an offset is mandatory: no guessing the exchange time zone
    if granularity_s == 86400:
        # A daily bar starts at the exchange's local midnight (e.g. 00:00-04:00). It is keyed by its
        # trading date (00:00 UTC of that local date) so it aligns with the pipeline's day grid.
        return int(datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc).timestamp())
    return int(dt.timestamp())  # intraday bars must align exactly, or validation refuses them


class QuestradeCandles:
    source = SOURCE

    def __init__(self, client: Any, *, clock: Callable[[], datetime] | None = None) -> None:
        if client is None:
            raise CandleError("questrade_client_required")
        self.client = client
        self.clock = clock or _now_utc
        self.instruments: dict[str, QuestradeInstrument] = {}

    def resolve(self, instrument: str) -> QuestradeInstrument:
        """Exact symbol match only (e.g. 'SHOP.TO', 'AAPL'); ambiguous or unknown symbols refuse."""
        symbol = str(instrument or "").strip().upper()
        if symbol in self.instruments:
            return self.instruments[symbol]
        rows = _payload(self.client, "/symbols/search", {"prefix": symbol}).get("symbols") or []
        exact = [r for r in rows if isinstance(r, Mapping) and str(r.get("symbol", "")).upper() == symbol]
        if not exact:
            raise CandleError("questrade_symbol_not_found")
        if len({r.get("symbolId") for r in exact}) != 1:
            raise CandleError("questrade_symbol_ambiguous")
        row = exact[0]
        try:
            symbol_id = int(row["symbolId"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CandleError("questrade_symbol_invalid") from exc
        quotes = _payload(self.client, "/markets/quotes", {"ids": str(symbol_id)}).get("quotes") or []
        delay = None
        if quotes and isinstance(quotes[0], Mapping) and isinstance(quotes[0].get("delay"), (int, float)):
            delay = int(quotes[0]["delay"])
        info = QuestradeInstrument(symbol, symbol_id, str(row.get("currency") or ""),
                                   str(row.get("listingExchange") or ""), str(row.get("securityType") or ""),
                                   str(row.get("description") or ""), delay)
        if not info.currency:
            raise CandleError("questrade_currency_missing")  # never assume CAD or USD
        self.instruments[symbol] = info
        return info

    def fetch(self, instrument: str, *, granularity_s: int, end: datetime | None = None) -> CandleSeries:
        interval = QUESTRADE_INTERVALS.get(granularity_s)
        if interval is None:
            raise CandleError("granularity_unsupported")
        info = self.resolve(instrument)
        end_dt = end or self.clock()
        start_dt = end_dt - timedelta(seconds=granularity_s * MAX_CANDLES_PER_REQUEST)
        rows = _payload(self.client, f"/markets/candles/{info.symbol_id}",
                        {"startTime": _iso(start_dt), "endTime": _iso(end_dt), "interval": interval}).get("candles")
        if not isinstance(rows, list):
            raise CandleError("response_invalid")
        candles = []
        for r in rows:
            if not isinstance(r, Mapping):
                raise CandleError("row_invalid")
            try:
                candles.append(Candle(_parse_ts(r["start"], granularity_s), float(r["open"]), float(r["high"]), float(r["low"]),
                                      float(r["close"]), float(r.get("volume") or 0.0)))
            except (KeyError, TypeError, ValueError) as exc:
                raise CandleError("row_invalid") from exc
        candles.sort(key=lambda c: c.ts)
        series = CandleSeries(info.symbol, "EQUITY", granularity_s, self.source, tuple(candles), info.classification)
        # exchange sessions, weekends and holidays leave gaps; bars themselves are validated strictly
        return validate(drop_incomplete(series, now=self.clock()), allow_gaps=100_000)
