"""Closeout: read-only market-data providers, failover, quality checks and producer gating.

All network traffic is replaced by recorded-shape fakes; bars here are synthetic and are used
only to verify mechanics. Real-endpoint evidence comes from the css-real-data-evidence workflow.
"""
from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.signals import market_data as md
from backend.signals.candles import (
    INDICATIVE,
    LIVE,
    REPLAY,
    Candle,
    CandleError,
    CandleSeries,
    CoinbasePublicCandles,
    CsvCandleStore,
    drop_incomplete,
)

H = 3600
T0 = 1_760_000_400 - (1_760_000_400 % H)  # 2025-10-09, aligned
NOW = datetime.fromtimestamp(T0 + 10 * H + 600, tz=timezone.utc)  # 10 complete bars, 11th forming


class Resp:
    def __init__(self, payload=None, status=200, headers=None):
        self.payload, self.status_code, self.headers = payload, status, headers or {}

    def json(self):
        return self.payload


class Http:
    """Returns queued responses (or raises queued exceptions) and records every call."""

    def __init__(self, *responses):
        self.queue, self.calls = list(responses), []

    def get(self, url, params=None, headers=None, timeout=10.0):
        self.calls.append({"url": url, "params": params, "headers": headers})
        item = self.queue.pop(0) if len(self.queue) > 1 else self.queue[0]
        if isinstance(item, Exception):
            raise item
        return item


def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bars(n=11, start=100.0):
    out, px = [], start
    for i in range(n):
        o, px = px, px * (1.001 if i % 3 else 0.999)
        out.append((T0 + i * H, o, max(o, px) * 1.001, min(o, px) * 0.999, px, 10.0 + i))
    return out


# --------------------------------------------------------------------------- providers
def test_alpaca_crypto_parses_drops_forming_bar_and_sends_no_credentials():
    rows = [{"t": iso(t), "o": o, "h": h, "l": l, "c": c, "v": v} for t, o, h, l, c, v in bars()]
    http = Http(Resp({"bars": {"BTC/USD": rows}}))
    s = md.AlpacaCryptoPublicCandles(http, clock=lambda: NOW).fetch("BTC-USD", granularity_s=H)
    assert len(s.candles) == 10 and s.candles[-1].ts == T0 + 9 * H  # forming 11th bar removed
    assert s.classification == LIVE and s.source == "alpaca_crypto_public" and s.instrument == "BTC-USD"
    call = http.calls[0]
    assert call["url"] == "https://data.alpaca.markets/v1beta3/crypto/us/bars"
    assert call["params"]["symbols"] == "BTC/USD" and call["headers"] is None
    with pytest.raises(CandleError, match="alpaca_non_data_host_refused"):
        md.AlpacaCryptoPublicCandles(http, base_url="https://paper-api.alpaca.markets")


def test_alpaca_stock_requires_keys_and_is_indicative_not_consolidated():
    with pytest.raises(CandleError, match="alpaca_credentials_missing"):
        md.AlpacaStockCandles(Http(Resp({})), key_id="", secret="").fetch("SPY", granularity_s=H)
    rows = [{"t": iso(t), "o": o, "h": h, "l": l, "c": c, "v": v} for t, o, h, l, c, v in bars()]
    http = Http(Resp({"bars": rows}))
    s = md.AlpacaStockCandles(http, key_id="k", secret="s", clock=lambda: NOW).fetch("SPY", granularity_s=H)
    assert s.classification == INDICATIVE and s.asset_class == "EQUITY"
    assert http.calls[0]["params"]["feed"] == "iex" and http.calls[0]["headers"]["APCA-API-KEY-ID"] == "k"
    with pytest.raises(CandleError, match="credentials_rejected:403"):
        md.AlpacaStockCandles(Http(Resp({}, 403)), key_id="k", secret="s").fetch("SPY", granularity_s=H)


@pytest.mark.parametrize("country,reason", [("", "binance_operating_country_unattested"),
                                            ("CA", "binance_jurisdiction_restricted:CA"),
                                            ("us", "binance_jurisdiction_restricted:US")])
def test_binance_refuses_unattested_or_restricted_jurisdiction_before_any_request(country, reason):
    http = Http(Resp([]))
    with pytest.raises(CandleError, match=reason):
        md.BinanceSpotPublicCandles(http, operating_country=country).fetch("BTC-USDT", granularity_s=H)
    with pytest.raises(CandleError, match=reason):
        md.BinanceQuotes(http, operating_country=country).quote("BTC-USDT")
    assert http.calls == []


def test_binance_public_klines_and_451_is_authoritative():
    rows = [[t * 1000, str(o), str(h), str(l), str(c), str(v), (t + H) * 1000 - 1, "0", 5] for t, o, h, l, c, v in bars()]
    http = Http(Resp(rows))
    s = md.BinanceSpotPublicCandles(http, operating_country="GB", clock=lambda: NOW).fetch("BTC-USDT", granularity_s=H)
    assert len(s.candles) == 10 and s.source == "binance_spot_public" and s.instrument == "BTC-USDT"
    assert http.calls[0]["url"] == "https://data-api.binance.vision/api/v3/klines"
    assert http.calls[0]["params"]["symbol"] == "BTCUSDT"
    blocked = Http(Resp({}, 451))
    with pytest.raises(CandleError, match="^restricted_location$"):
        md.BinanceSpotPublicCandles(blocked, operating_country="GB").fetch("BTC-USDT", granularity_s=H)
    assert len(blocked.calls) == 1  # no alternate host tried
    with pytest.raises(CandleError, match="binance_non_public_host_refused"):
        md.BinanceSpotPublicCandles(http, operating_country="GB", base_url="https://api.binance.com")


def test_coinbase_forming_bar_is_dropped():
    rows = [[t, l, h, o, c, v] for t, o, h, l, c, v in reversed(bars())]
    s = CoinbasePublicCandles(Http(Resp(rows)), clock=lambda: NOW).fetch("BTC-USD", granularity_s=H)
    assert s.candles[-1].ts == T0 + 9 * H and s.classification == LIVE


def test_options_and_futures_feeds_are_explicitly_blocked():
    for name, asset in (("options", "OPTIONS"), ("futures", "FUTURES")):
        with pytest.raises(CandleError, match=f"feed_blocked:{asset}:no_authorized"):
            md.build_provider(name, http=Http(Resp({}))).fetch("ANY", granularity_s=H)


def test_symbol_normalisation():
    assert md.normalize_symbol("coinbase", "btc/usd") == "BTC-USD"
    assert md.normalize_symbol("alpaca_crypto", "BTC-USD") == "BTC/USD"
    assert md.normalize_symbol("binance", "ETH-USDT") == "ETHUSDT"
    assert md.normalize_symbol("oanda", "EUR/USD") == "EUR_USD"
    with pytest.raises(CandleError):
        md.normalize_symbol("alpaca_stock", "BTC-USD")


# --------------------------------------------------------------------------- resilience
def test_retrying_http_backs_off_exponentially_and_honours_retry_after():
    sleeps = []
    inner = Http(Resp({}, 500), Resp({}, 429, {"Retry-After": "3"}), Resp({}, 503), Resp({"ok": 1}))
    http = md.RetryingHttp(inner, min_interval_s=0, sleep=sleeps.append, monotonic=lambda: 0.0)
    assert http.get("https://x.example/a").json() == {"ok": 1}
    assert sleeps == [0.5, 3.0, 6.0] and [a["status"] for a in http.attempts_log] == [500, 429, 503, 200]


@pytest.mark.parametrize("status", [451, 401, 403, 404])
def test_retrying_http_never_retries_restriction_or_credential_failures(status):
    inner = Http(Resp({}, status))
    http = md.RetryingHttp(inner, min_interval_s=0, sleep=lambda _s: None)
    assert http.get("https://x.example/a").status_code == status and len(inner.calls) == 1


def test_retrying_http_connection_errors_exhaust_then_fail_closed():
    inner = Http(ConnectionError("down"))
    sleeps = []
    http = md.RetryingHttp(inner, min_interval_s=0, max_attempts=3, sleep=sleeps.append)
    with pytest.raises(CandleError, match="fetch_failed_after_retries:ConnectionError"):
        http.get("https://x.example/a")
    assert len(inner.calls) == 3 and sleeps == [0.5, 1.0]


def test_retrying_http_rate_limits_per_host():
    clock = {"t": 0.0}
    sleeps = []
    http = md.RetryingHttp(Http(Resp({})), min_interval_s=0.25, sleep=lambda s: (sleeps.append(s), clock.__setitem__("t", clock["t"] + s)),
                           monotonic=lambda: clock["t"])
    http.get("https://a.example/1")
    http.get("https://a.example/2")
    http.get("https://b.example/1")
    assert sleeps == [0.25]


class FixedProvider:
    def __init__(self, source, series=None, error=None):
        self.source, self.series, self.error = source, series, error

    def fetch(self, instrument, *, granularity_s, end=None):
        if self.error:
            raise CandleError(self.error)
        return self.series


def series(source="a", shift=1.0, n=10, classification=LIVE):
    cs = tuple(Candle(t, o * shift, h * shift, l * shift, c * shift, v) for t, o, h, l, c, v in bars(n))
    return CandleSeries("BTC-USD", "CRYPTO", H, source, cs, classification)


def test_failover_records_attempts_and_uses_next_provider():
    fo = md.FailoverCandleProvider([FixedProvider("a", error="rate_limited"), FixedProvider("b", series("b"))])
    s = fo.fetch("BTC-USD", granularity_s=H)
    assert s.source == "b"
    assert fo.last_attempts == [{"source": "a", "ok": False, "reason": "rate_limited"}, {"source": "b", "ok": True}]
    dead = md.FailoverCandleProvider([FixedProvider("a", error="x"), FixedProvider("b", error="y")])
    with pytest.raises(CandleError, match="all_providers_failed:a=x;b=y"):
        dead.fetch("BTC-USD", granularity_s=H)


def test_cross_provider_discrepancy_fails_closed():
    ok = md.FailoverCandleProvider([FixedProvider("a", series("a"))], cross_check=FixedProvider("b", series("b", 1.0002)),
                                   max_discrepancy_bps=10)
    ok.fetch("BTC-USD", granularity_s=H)
    assert ok.last_discrepancy.overlap_bars == 10 and ok.last_discrepancy.last_bps == pytest.approx(2.0, rel=1e-3)
    bad = md.FailoverCandleProvider([FixedProvider("a", series("a"))], cross_check=FixedProvider("b", series("b", 1.01)),
                                    max_discrepancy_bps=10)
    with pytest.raises(CandleError, match="cross_provider_discrepancy"):
        bad.fetch("BTC-USD", granularity_s=H)
    unavailable = md.FailoverCandleProvider([FixedProvider("a", series("a"))], cross_check=FixedProvider("b", error="down"))
    with pytest.raises(CandleError, match="cross_check_unavailable"):
        unavailable.fetch("BTC-USD", granularity_s=H)


def test_series_metrics_and_completeness():
    s = series()
    gapped = replace(s, candles=s.candles[:4] + s.candles[6:])
    m = md.series_metrics(gapped)
    assert (m.bars, m.expected_bars) == (8, 10) and m.completeness == pytest.approx(0.8)
    assert m.realised_vol_bps > 0 and m.median_volume > 0
    md.check_complete(s)
    with pytest.raises(CandleError, match="candles_incomplete"):
        md.check_complete(gapped)


def test_replay_is_deterministic_and_classified_replay(tmp_path):
    store = CsvCandleStore(tmp_path)
    store.save(series("coinbase_exchange_public"))
    as_of = datetime.fromtimestamp(T0 + 5 * H, tz=timezone.utc)
    rp = md.ReplayCandleProvider(store, source="coinbase_exchange_public", asset_class="CRYPTO", clock=lambda: as_of)
    a, b = rp.fetch("BTC-USD", granularity_s=H), rp.fetch("BTC-USD", granularity_s=H)
    assert a.digest == b.digest and len(a.candles) == 5 and a.classification == REPLAY


# --------------------------------------------------------------------------- quotes / skew
def test_coinbase_quote_spread_depth_and_validation():
    book = {"bids": [["100.00", "2"], ["99.99", "1"], ["98.00", "50"]], "asks": [["100.02", "1"], ["101.5", "9"]]}
    tick = {"time": NOW.isoformat().replace("+00:00", "Z")}
    q = md.CoinbaseQuotes(Http(Resp(book), Resp(tick)), clock=lambda: NOW).quote("BTC-USD")
    assert q.spread_bps == pytest.approx(2.0, rel=1e-3)
    assert q.bid_depth_notional == pytest.approx(200 + 99.99) and q.ask_depth_notional == pytest.approx(100.02)
    crossed = {"bids": [["101", "1"]], "asks": [["100", "1"]]}
    with pytest.raises(CandleError, match="quote_crossed"):
        md.CoinbaseQuotes(Http(Resp(crossed), Resp(tick)), clock=lambda: NOW).quote("BTC-USD")
    with pytest.raises(CandleError, match="quote_stale"):
        md.CoinbaseQuotes(Http(Resp(book), Resp(tick)), clock=lambda: NOW + timedelta(minutes=5)).quote("BTC-USD")


def test_alpaca_and_binance_quotes():
    ob = {"orderbooks": {"BTC/USD": {"t": NOW.isoformat(), "b": [{"p": 100.0, "s": 1}], "a": [{"p": 100.1, "s": 2}]}}}
    q = md.AlpacaCryptoQuotes(Http(Resp(ob)), clock=lambda: NOW).quote("BTC-USD")
    assert q.spread_bps == pytest.approx(10.0, rel=1e-2) and q.source == "alpaca_crypto_public"
    server = {"serverTime": int(NOW.timestamp() * 1000)}
    depth = {"bids": [["100", "1"]], "asks": [["100.01", "1"]]}
    http = Http(Resp(server), Resp(depth))
    q2 = md.BinanceQuotes(http, operating_country="GB", clock=lambda: NOW).quote("BTC-USDT")
    assert q2.exchange_ts == NOW and q2.spread_bps == pytest.approx(1.0, rel=1e-2)


def test_clock_skew_measurement_and_guard():
    server = NOW + timedelta(seconds=2)
    assert md.measure_clock_skew(lambda: server, clock=lambda: NOW) == pytest.approx(2.0)
    md.check_clock_skew(2.0)
    with pytest.raises(CandleError, match="clock_skew_exceeded"):
        md.check_clock_skew(-7.5)
    with pytest.raises(CandleError):
        md.check_clock_skew(math.nan)


def test_provider_matrix_reports_blocked_states_without_network():
    rows = {r["provider"]: r for r in md.provider_matrix({"CSS_OPERATING_COUNTRY": "CA"})}
    assert rows["coinbase_exchange_public"]["status"] == "READY"
    assert rows["alpaca_crypto_public"]["status"] == "READY"
    assert rows["binance_spot_public"]["status"] == "BLOCKED" and rows["binance_spot_public"]["reason"].endswith(":CA")
    assert rows["alpaca_iex"]["reason"] == "alpaca_credentials_missing"
    assert rows["oanda_practice"]["reason"] == "oanda_practice_token_missing"
    assert rows["blocked_options"]["status"] == rows["blocked_futures"]["status"] == "BLOCKED"
    secrets_ = {"APCA_API_KEY_ID": "SENTINEL-KEY-1", "APCA_API_SECRET_KEY": "SENTINEL-SECRET-2",
                "OANDA_PRACTICE_TOKEN": "SENTINEL-TOKEN-3"}
    matrix = md.provider_matrix({"CSS_OPERATING_COUNTRY": "GB", **secrets_})
    ready = {r["provider"]: r for r in matrix}
    assert all(ready[p]["status"] == "READY" for p in ("binance_spot_public", "alpaca_iex", "oanda_practice"))
    assert not any(v in repr(matrix) for v in secrets_.values())  # the matrix never echoes secrets


def test_drop_incomplete_keeps_closed_bars_only():
    s = series(n=11)
    assert len(drop_incomplete(s, now=NOW).candles) == 10
    assert drop_incomplete(s, now=NOW + timedelta(hours=1)) is s
