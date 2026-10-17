"""Issue #129: governed Questrade + Binance market data and read-only accounts (no execution).

All network traffic is replaced by fakes (contract tests). Tokens below are labelled synthetic test
values, never real credentials.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from backend.brokers.questrade.advisory_adapter import QuestradeAdvisoryAdapter
from backend.brokers.questrade.configuration import QuestradeSecureConfiguration
from backend.brokers.questrade.contracts import account_hash
from backend.brokers.questrade.errors import WriteMethodBlockedError
from backend.brokers.questrade.get_only_transport import QuestradeGetOnlyHttpTransport
from backend.brokers.questrade.readonly_client import QuestradeHttpResponse, QuestradeReadOnlyClient
from backend.brokers.questrade.token_lifecycle import TokenLifecycle
from backend.signals import market_data as md
from backend.signals.binance_market_data import (
    IN_SYNC,
    OUT_OF_SYNC,
    DepthBook,
    DepthStream,
    WeightGuard,
    exchange_filters,
)
from backend.signals.candles import DELAYED, LIVE, CandleError
from backend.signals.questrade_market_data import QuestradeCandles

REPO = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 16, 20, 0, tzinfo=timezone.utc)
TOKEN_RESPONSE = {"access_token": "synthetic-access-token-not-a-credential",
                  "refresh_token": "synthetic-refresh-token-not-a-credential",
                  "api_server": "https://api01.iq.questrade.com/", "expires_in": 1800}


# =================================================================== Questrade
class FakeQuestrade:
    def __init__(self, *, delay=0, status=200, symbols=None, currency="CAD"):
        self.calls, self.delay, self.status = [], delay, status
        self.symbols = symbols if symbols is not None else [
            {"symbol": "SHOP.TO", "symbolId": 9292, "currency": currency, "listingExchange": "TSX",
             "securityType": "Stock", "description": "SHOPIFY INC"},
            {"symbol": "SHOP", "symbolId": 11111, "currency": "USD", "listingExchange": "NYSE",
             "securityType": "Stock", "description": "SHOPIFY INC"}]

    def send(self, *, method, url, headers, params, timeout_seconds):
        self.calls.append({"method": method, "path": urlsplit(url).path, "params": dict(params)})
        if self.status != 200:
            return QuestradeHttpResponse(self.status, {}, {"Retry-After": "0"})
        path = urlsplit(url).path.removeprefix("/v1")
        if path == "/symbols/search":
            return QuestradeHttpResponse(200, {"symbols": self.symbols})
        if path == "/markets/quotes":
            return QuestradeHttpResponse(200, {"quotes": [{"symbolId": 9292, "delay": self.delay}]})
        if path.startswith("/markets/candles/"):
            if params["interval"] == "OneDay":
                rows = [{"start": f"2026-10-{d:02d}T00:00:00.000000-04:00", "end": f"2026-10-{d + 1:02d}T00:00:00.000000-04:00",
                         "open": 100.0 + d, "high": 102.0 + d, "low": 99.0 + d, "close": 101.0 + d, "volume": 1000}
                        for d in (13, 14, 15)]
            else:
                rows = [{"start": f"2026-10-16T{h:02d}:00:00.000000+00:00", "end": "x", "open": 100.0, "high": 101.0,
                         "low": 99.0, "close": 100.5, "volume": 10} for h in (17, 18, 19)]
            return QuestradeHttpResponse(200, {"candles": rows})
        if path == "/accounts":
            return QuestradeHttpResponse(200, {"accounts": [{"number": "51234567", "type": "TFSA", "status": "Active",
                                                             "isPrimary": True, "clientAccountType": "Individual"}]})
        if path == "/accounts/51234567/orders":
            return QuestradeHttpResponse(200, {"orders": [{"id": 77, "symbol": "SHOP.TO", "symbolId": 9292, "side": "Buy",
                                                           "orderType": "Limit", "state": "Executed", "totalQuantity": 5,
                                                           "filledQuantity": 5, "avgExecPrice": 101.2, "limitPrice": 101.5,
                                                           "creationTime": "2026-10-15T14:00:00-04:00",
                                                           "updateTime": "2026-10-15T14:00:02-04:00",
                                                           "accountNumber": "51234567"}]})
        return QuestradeHttpResponse(404, {})


def _client(fake, *, retries=0):
    tokens = TokenLifecycle(now=NOW)
    assert tokens.record_external_token_response(TOKEN_RESPONSE, allow_record=True)["success"] is True
    return QuestradeReadOnlyClient(tokens, transport=fake, sleeper=lambda _: None, max_retries=retries), tokens


def test_questrade_candles_normalised_with_provenance_and_live_entitlement():
    fake = FakeQuestrade(delay=0)
    client, _ = _client(fake)
    provider = QuestradeCandles(client, clock=lambda: NOW.replace(hour=19, minute=30))
    s = provider.fetch("SHOP.TO", granularity_s=3600)
    assert s.instrument == "SHOP.TO" and s.asset_class == "EQUITY" and s.source == "questrade_api"
    assert s.classification == LIVE and [c.ts % 3600 for c in s.candles] == [0, 0]
    assert len(s.candles) == 2  # the 19:00 bar is still forming at 19:30 -> dropped
    prov = provider.instruments["SHOP.TO"].provenance()
    assert prov["symbol_id"] == 9292 and prov["currency"] == "CAD" and prov["venue"] == "TSX"
    assert prov["entitlement"] == "REAL_TIME"
    assert all(c["method"] == "GET" for c in fake.calls)
    assert fake.calls[-1]["path"] == "/v1/markets/candles/9292" and fake.calls[-1]["params"]["interval"] == "OneHour"


def test_questrade_daily_bars_are_keyed_by_trading_date():
    client, _ = _client(FakeQuestrade())
    s = QuestradeCandles(client, clock=lambda: NOW).fetch("SHOP.TO", granularity_s=86400)
    assert [datetime.fromtimestamp(c.ts, tz=timezone.utc).date().isoformat() for c in s.candles] == [
        "2026-10-13", "2026-10-14", "2026-10-15"]


@pytest.mark.parametrize("delay,expected,entitlement", [(15, DELAYED, "DELAYED_15_MIN"),
                                                        (None, DELAYED, "UNKNOWN_TREATED_AS_DELAYED")])
def test_questrade_delayed_or_unknown_entitlement_is_never_live(delay, expected, entitlement):
    client, _ = _client(FakeQuestrade(delay=delay))
    provider = QuestradeCandles(client, clock=lambda: NOW)
    assert provider.fetch("SHOP.TO", granularity_s=3600).classification == expected
    assert provider.instruments["SHOP.TO"].provenance()["entitlement"] == entitlement


@pytest.mark.parametrize("symbols,reason", [
    ([], "questrade_symbol_not_found"),
    ([{"symbol": "SHOP.TO", "symbolId": 1, "currency": "CAD"}, {"symbol": "SHOP.TO", "symbolId": 2, "currency": "CAD"}],
     "questrade_symbol_ambiguous"),
    ([{"symbol": "SHOP.TO", "symbolId": 1, "currency": ""}], "questrade_currency_missing"),
])
def test_questrade_symbol_resolution_refuses_unknown_ambiguous_or_currencyless(symbols, reason):
    client, _ = _client(FakeQuestrade(symbols=symbols))
    with pytest.raises(CandleError, match=reason):
        QuestradeCandles(client, clock=lambda: NOW).fetch("SHOP.TO", granularity_s=3600)


@pytest.mark.parametrize("status,code", [(401, "QUESTRADE_AUTHORIZATION_REVOKED"), (429, "QUESTRADE_RATE_LIMITED"),
                                         (503, "QUESTRADE_PROVIDER_UNAVAILABLE")])
def test_questrade_unauthorized_rate_limited_and_outage_fail_closed(status, code):
    client, _ = _client(FakeQuestrade(status=status))
    with pytest.raises(CandleError, match=f"questrade:{code}"):
        QuestradeCandles(client, clock=lambda: NOW).fetch("SHOP.TO", granularity_s=3600)


def test_questrade_without_authorization_makes_no_request():
    fake = FakeQuestrade()
    client = QuestradeReadOnlyClient(TokenLifecycle(now=NOW), transport=fake, sleeper=lambda _: None)
    with pytest.raises(CandleError, match="questrade:QUESTRADE_ACCESS_TOKEN_REQUIRED"):
        QuestradeCandles(client, clock=lambda: NOW).fetch("SHOP.TO", granularity_s=3600)
    assert fake.calls == []
    row = {r["provider"]: r for r in md.provider_matrix({})}["questrade_api"]
    assert row["status"] == "BLOCKED" and row["reason"] == "questrade_oauth_authorization_required"


def test_questrade_order_history_is_read_only_and_masks_the_account():
    fake = FakeQuestrade()
    client, tokens = _client(fake)
    config = QuestradeSecureConfiguration(refresh_token_ref="vault:questrade/refresh", token_store_id="vault:questrade/tokens",
                                          secret_store_provider="WINDOWS_CREDENTIAL_MANAGER")
    adapter = QuestradeAdvisoryAdapter(token_lifecycle=tokens, configuration=config, client=client)
    assert adapter.get_accounts()["success"] is True
    assert adapter.select_account(account_hash("51234567"))["success"] is True
    history = adapter.get_order_history(start_time="2026-10-01T00:00:00-04:00", end_time="2026-10-16T00:00:00-04:00")
    assert history["status"] == "ACCOUNT_READY" and history["order_count"] == 1 and history["execution_allowed"] is False
    (order,) = history["orders"]
    assert order["state"] == "Executed" and order["filled_quantity"] == 5 and order["provenance"] == "QUESTRADE_ORDER_HISTORY"
    text = json.dumps(history, default=str)
    assert "51234567" not in text and TOKEN_RESPONSE["access_token"] not in text
    assert {c["method"] for c in fake.calls} == {"GET"}
    with pytest.raises(ValueError):
        adapter.get_order_history(state_filter="Everything")


def test_questrade_cannot_write_orders_by_any_path():
    fake = FakeQuestrade()
    client, _ = _client(fake)
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        result = client.request("/accounts/51234567/orders", method=method)
        assert result.success is False and result.failure_code == "QUESTRADE_WRITE_METHOD_BLOCKED"
    assert client.request("/accounts/51234567/orders/impact").failure_code == "QUESTRADE_PATH_NOT_ALLOWLISTED"
    assert fake.calls == []  # nothing was sent
    with pytest.raises(WriteMethodBlockedError):
        QuestradeGetOnlyHttpTransport().send(method="POST", url="https://api01.iq.questrade.com/v1/accounts/1/orders",
                                             headers={}, params={}, timeout_seconds=1)


# =================================================================== Binance
class NeverCalledHttp:
    def get(self, *a, **k):
        raise AssertionError("no request may be made for an ineligible jurisdiction")


class Resp:
    def __init__(self, payload, status=200, headers=None):
        self.payload, self.status_code, self.headers = payload, status, headers or {}

    def json(self):
        return self.payload


class FakeHttp:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


EXCHANGE_INFO = {"symbols": [{"symbol": "BTCUSDT", "status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT",
                              "filters": [{"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                                          {"filterType": "LOT_SIZE", "stepSize": "0.00001", "minQty": "0.00001"},
                                          {"filterType": "NOTIONAL", "minNotional": "5.0"}]}]}


@pytest.mark.parametrize("country", ["CA", "US", "", "Canada"])
def test_binance_refuses_ineligible_or_unattested_jurisdiction_before_any_request(country):
    with pytest.raises(CandleError, match="binance_(jurisdiction_restricted|operating_country_unattested)"):
        exchange_filters("BTC-USDT", operating_country=country, http=NeverCalledHttp())
    with pytest.raises(CandleError):
        DepthStream("BTC-USDT", country, snapshot=None, connect=None)


def test_binance_exchange_filters_from_public_host():
    http = FakeHttp(Resp(EXCHANGE_INFO, headers={"X-MBX-USED-WEIGHT-1M": "20"}))
    f = exchange_filters("BTC-USDT", operating_country="GB", http=http)
    assert (f.tick_size, f.step_size, f.min_qty, f.min_notional, f.trading) == (0.01, 0.00001, 0.00001, 5.0, True)
    assert http.calls[0][0] == "https://data-api.binance.vision/api/v3/exchangeInfo"


@pytest.mark.parametrize("drop,patch", [("NOTIONAL", None), (None, ("PRICE_FILTER", "tickSize", "0")),
                                        (None, ("LOT_SIZE", "stepSize", "nan"))])
def test_binance_missing_or_invalid_filters_fail_closed(drop, patch):
    info = json.loads(json.dumps(EXCHANGE_INFO))
    filters = info["symbols"][0]["filters"]
    if drop:
        info["symbols"][0]["filters"] = [f for f in filters if f["filterType"] != drop]
    if patch:
        next(f for f in filters if f["filterType"] == patch[0])[patch[1]] = patch[2]
    with pytest.raises(CandleError, match="binance_exchange_info_invalid"):
        exchange_filters("BTC-USDT", operating_country="GB", http=FakeHttp(Resp(info)), guard=WeightGuard())


def test_binance_weight_budget_and_ban_backoff():
    t = {"now": 0.0}
    guard = WeightGuard(clock=lambda: t["now"])
    guard.after_response(Resp({}, headers={"X-MBX-USED-WEIGHT-1M": "4900"}))
    with pytest.raises(CandleError, match="weight_budget_exhausted"):
        guard.before_request()
    guard = WeightGuard(clock=lambda: t["now"])
    with pytest.raises(CandleError, match="binance_ip_banned"):
        guard.after_response(Resp({}, status=418, headers={"Retry-After": "120"}))
    t["now"] = 119.0
    with pytest.raises(CandleError, match="backoff_in_effect"):
        guard.before_request()
    t["now"] = 121.0
    guard.before_request()  # allowed again only after the server's Retry-After
    with pytest.raises(CandleError, match="restricted_location"):
        WeightGuard().get(FakeHttp(Resp({}, status=451)), "https://data-api.binance.vision/api/v3/time", {})


def test_weight_budget_recovers_after_the_window_rolls_over():
    t = {"now": 0.0}
    guard = WeightGuard(clock=lambda: t["now"])
    guard.after_response(Resp({}, headers={"X-MBX-USED-WEIGHT-1M": "4800"}))
    t["now"] = 59.0
    with pytest.raises(CandleError, match="weight_budget_exhausted"):
        guard.before_request()
    t["now"] = 61.0
    guard.before_request()  # window rolled over: no permanent lock-out (review H1)
    assert guard.used == 0
    stale = WeightGuard(clock=lambda: 10_000.0, used=4800)  # reviewer's repro
    stale.before_request()


def test_default_weight_guard_is_shared_across_calls(monkeypatch):
    from backend.signals import binance_market_data as bmd
    t = {"now": 0.0}
    monkeypatch.setattr(bmd, "_DEFAULT_GUARD", WeightGuard(clock=lambda: t["now"]))
    with pytest.raises(CandleError, match="binance_ip_banned"):
        exchange_filters("BTC-USDT", operating_country="GB", http=FakeHttp(Resp({}, status=418, headers={"Retry-After": "120"})))
    fetch = bmd.public_snapshot_fetcher(operating_country="GB", http=NeverCalledHttp())
    with pytest.raises(CandleError, match="backoff_in_effect"):
        asyncio.run(fetch("BTCUSDT"))  # refused with zero HTTP calls (review M1)


def test_klines_and_quotes_share_the_default_weight_guard(monkeypatch):
    """Review A-M5: market_data's Binance klines, time and depth calls go through the per-process guard."""
    from backend.signals import binance_market_data as bmd
    t = {"now": 0.0}
    monkeypatch.setattr(bmd, "_DEFAULT_GUARD", WeightGuard(clock=lambda: t["now"]))
    with pytest.raises(CandleError, match="binance_ip_banned"):
        md.BinanceSpotPublicCandles(FakeHttp(Resp({}, status=418, headers={"Retry-After": "120"})),
                                    operating_country="GB").fetch("BTC-USDT", granularity_s=3600)
    with pytest.raises(CandleError, match="backoff_in_effect"):
        md.BinanceQuotes(NeverCalledHttp(), operating_country="GB").quote("BTC-USDT")  # zero HTTP calls
    with pytest.raises(CandleError, match="backoff_in_effect"):
        md.BinanceSpotPublicCandles(NeverCalledHttp(), operating_country="GB").fetch("BTC-USDT", granularity_s=3600)
    t["now"] = 121.0
    with pytest.raises(CandleError, match="binance_rate_limited"):
        md.BinanceQuotes(FakeHttp(Resp({}, status=429, headers={"Retry-After": "30"})),
                         operating_country="GB").quote("BTC-USDT")
    with pytest.raises(CandleError, match="backoff_in_effect"):
        exchange_filters("BTC-USDT", operating_country="GB", http=NeverCalledHttp())


def test_weight_guard_is_consistent_across_threads():
    """Review A-L3: one guard shared by to_thread workers keeps a consistent budget and back-off."""
    import threading
    guard = WeightGuard(clock=lambda: 0.0)
    errors, barrier = [], threading.Barrier(16)

    def worker(i):
        barrier.wait()
        try:
            guard.after_response(Resp({}, headers={"X-MBX-USED-WEIGHT-1M": str(i)}))
            if i == 7:
                guard.after_response(Resp({}, status=418, headers={"Retry-After": "300"}))
        except CandleError as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert errors == ["binance_ip_banned"] and guard.blocked_until == 300.0
    assert 0 <= guard.used <= 15
    with pytest.raises(CandleError, match="backoff_in_effect"):
        guard.before_request()


def _snapshot(last=100):
    return {"lastUpdateId": last, "bids": [["99.0", "1.0"], ["98.0", "2.0"]], "asks": [["101.0", "1.0"], ["102.0", "1.0"]]}


def test_depth_book_sequencing_drop_bridge_apply_and_gap():
    book = DepthBook("BTCUSDT")
    with pytest.raises(CandleError, match="awaiting_snapshot"):
        book.apply({"U": 1, "u": 2})
    book.load_snapshot(_snapshot(100))
    assert book.apply({"U": 90, "u": 100, "b": [["99.0", "5"]]}) is False  # covered by snapshot
    assert book.apply({"U": 95, "u": 103, "b": [["99.0", "0"]], "a": [["100.5", "1"]], "E": 1}) is True  # bridges 101
    assert book.best() == (98.0, 100.5) and book.last_update_id == 103
    assert book.apply({"U": 104, "u": 104, "b": [["99.5", "1"]]}) is True
    with pytest.raises(CandleError, match="sequence_gap"):
        book.apply({"U": 106, "u": 107})  # 105 missing
    assert book.state == OUT_OF_SYNC and book.gaps == 1
    with pytest.raises(CandleError, match="binance_depth_unavailable"):
        book.best()


def test_depth_book_first_event_must_bridge_the_snapshot_and_crossed_book_is_refused():
    book = DepthBook("BTCUSDT")
    book.load_snapshot(_snapshot(100))
    with pytest.raises(CandleError, match="sequence_gap"):
        book.apply({"U": 105, "u": 110})  # snapshot too old: events 101-104 missing
    book.load_snapshot(_snapshot(100))
    with pytest.raises(CandleError, match="crossed_book"):
        book.apply({"U": 101, "u": 101, "b": [["105.0", "1"]]})


class FakeConn:
    def __init__(self, messages, *, hang=False):
        self.messages, self.hang, self.closed = list(messages), hang, False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.messages:
            return json.dumps(self.messages.pop(0))
        if self.hang:
            await asyncio.sleep(3600)
        raise StopAsyncIteration

    async def close(self):
        self.closed = True


def _stream(conns, snapshots, **kw):
    conns, snapshots = list(conns), list(snapshots)

    async def connect(url):
        assert url == "wss://data-stream.binance.vision/ws/btcusdt@depth@100ms"
        c = conns.pop(0)
        if isinstance(c, Exception):
            raise c
        return c

    async def snapshot(symbol):
        return snapshots.pop(0)

    async def no_sleep(_):
        return None

    return DepthStream("BTC-USDT", "GB", snapshot=snapshot, connect=connect, sleep=no_sleep, **kw)


def test_depth_stream_resyncs_after_a_gap_with_a_new_snapshot():
    first = FakeConn([{"s": "BTCUSDT", "U": 101, "u": 101}, {"s": "BTCUSDT", "U": 103, "u": 103}])  # gap at 102
    second = FakeConn([{"s": "BTCUSDT", "U": 200, "u": 201}, {"s": "BTCUSDT", "U": 202, "u": 202}])
    stream = _stream([first, second], [_snapshot(100), _snapshot(200)])
    book = asyncio.run(stream.run(lambda b: None, max_updates=3))
    assert book.state == IN_SYNC and book.last_update_id == 202 and first.closed
    assert [e["event"] for e in stream.log] == ["CONNECTED", "SESSION_ENDED", "RECONNECT", "CONNECTED"]
    assert stream.log[1]["reason"] == "binance_depth_sequence_gap"


def test_depth_stream_stale_feed_and_reconnect_exhaustion_fail_closed():
    stream = _stream([FakeConn([], hang=True), ConnectionError("down"), ConnectionError("down")],
                     [_snapshot()], stale_after_s=0.05, max_reconnects=2)
    with pytest.raises(CandleError, match="reconnects_exhausted"):
        asyncio.run(stream.run(lambda b: None))
    assert stream.log[1] == {"event": "SESSION_ENDED", "reason": "binance_stream_stale"}
    assert stream.book.state == OUT_OF_SYNC


# =================================================================== no execution path
def test_new_market_data_modules_have_no_order_path():
    for rel in ("backend/signals/binance_market_data.py", "backend/signals/questrade_market_data.py"):
        source = (REPO / rel).read_text(encoding="utf-8")
        for forbidden in ("/api/v3/order", "/sapi/", "X-MBX-APIKEY", "signature", ".post(", ".delete(", ".put("):
            assert forbidden not in source, (rel, forbidden)
