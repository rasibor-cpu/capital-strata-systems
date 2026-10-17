"""Grok re-audit F-5 (Alpaca secret forwarded on redirect) and R-2 (public Binance paths follow
redirects): every market-data HTTP client is built on candles._requests_session(), which never
follows a redirect; check_http turns any 3xx into `redirect_refused:<status>`.

Loopback only, SYNTHETIC credentials only: server A answers 302 pointing at server B (a different
host:port); B records whatever reaches it.
"""
from __future__ import annotations

import http.server
import json
import threading

import pytest
import requests

from backend.signals import binance_market_data as bmd
from backend.signals import market_data as md
from backend.signals.binance_market_data import WeightGuard
from backend.signals.candles import CandleError, _requests_session, check_http

SYNTHETIC_KEY_ID = "SYNTHETIC-KEY-ID"
SYNTHETIC_SECRET = "SYNTHETIC-SECRET-must-never-leave"


@pytest.fixture
def servers(monkeypatch):
    for var in ("NO_PROXY", "no_proxy"):
        monkeypatch.setenv(var, "127.0.0.1,localhost")
    received: list[dict] = []

    class B(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            received.append({k.lower(): v for k, v in self.headers.items()})
            body = json.dumps({"bars": [], "serverTime": 1, "symbols": []}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    b = http.server.HTTPServer(("127.0.0.1", 0), B)

    class A(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", f"http://localhost:{b.server_port}/collect{self.path}")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *a):
            pass

    a = http.server.HTTPServer(("127.0.0.1", 0), A)
    for srv in (a, b):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{a.server_port}", f"http://localhost:{b.server_port}", received
    finally:
        a.shutdown()
        b.shutdown()


# ------------------------------------------------------------------------------- F-5 Alpaca
def test_defect_plain_session_forwards_the_alpaca_secret_across_a_redirect(servers):
    """The pre-fix transport (a plain requests.Session) delivers APCA-API-SECRET-KEY to server B."""
    redirecting, _collector, received = servers
    requests.Session().get(f"{redirecting}/v2/stocks/AAPL/bars", timeout=5,
                           headers={"APCA-API-KEY-ID": SYNTHETIC_KEY_ID, "APCA-API-SECRET-KEY": SYNTHETIC_SECRET})
    assert received and received[0].get("apca-api-secret-key") == SYNTHETIC_SECRET


def test_alpaca_stock_candles_never_forward_credentials(servers, monkeypatch):
    redirecting, _collector, received = servers
    monkeypatch.setattr(md, "ALPACA_DATA_BASE", redirecting)
    client = md.AlpacaStockCandles(key_id=SYNTHETIC_KEY_ID, secret=SYNTHETIC_SECRET)  # default transport
    with pytest.raises(CandleError, match="redirect_refused:302"):
        client.fetch("AAPL", granularity_s=86400)
    assert received == []  # server B was never contacted: the secret never left for another host


def test_alpaca_refuses_a_transport_that_follows_redirects():
    with pytest.raises(CandleError, match="credentialed_transport_must_not_follow_redirects"):
        md.AlpacaStockCandles(requests.Session(), key_id=SYNTHETIC_KEY_ID, secret=SYNTHETIC_SECRET)
    with pytest.raises(CandleError, match="credentialed_transport_must_not_follow_redirects"):
        md.AlpacaStockCandles(md.RetryingHttp(requests.Session()), key_id=SYNTHETIC_KEY_ID, secret=SYNTHETIC_SECRET)
    md.AlpacaStockCandles(md.resilient_http(), key_id=SYNTHETIC_KEY_ID, secret=SYNTHETIC_SECRET)  # shipped path


# ------------------------------------------------------------------------------- R-2 Binance public
def test_public_binance_klines_do_not_follow_redirects(servers, monkeypatch):
    redirecting, _collector, received = servers
    monkeypatch.setattr(md, "BINANCE_PUBLIC_BASE", redirecting)
    client = md.BinanceSpotPublicCandles(operating_country="GB", base_url=redirecting, guard=WeightGuard())
    with pytest.raises(CandleError, match="redirect_refused:302"):
        client.fetch("BTC-USDT", granularity_s=3600)
    assert received == []


def test_public_binance_exchange_info_and_quotes_do_not_follow_redirects(servers, monkeypatch):
    redirecting, _collector, received = servers
    monkeypatch.setattr(bmd, "BINANCE_PUBLIC_BASE", redirecting)
    monkeypatch.setattr(md, "BINANCE_PUBLIC_BASE", redirecting)
    with pytest.raises(CandleError, match="redirect_refused:302"):
        bmd.exchange_filters("BTC-USDT", operating_country="GB", guard=WeightGuard())
    with pytest.raises(CandleError, match="redirect_refused:302"):
        md.BinanceQuotes(operating_country="GB", guard=WeightGuard()).quote("BTC-USDT")
    assert received == []


# ------------------------------------------------------------------------------- transport
def test_session_returns_3xx_unfollowed_and_2xx_unchanged(servers):
    redirecting, collector, received = servers
    session = _requests_session()
    resp = session.get(f"{redirecting}/anything", timeout=5, allow_redirects=True)  # caller cannot re-enable
    assert resp.status_code == 302 and received == []
    with pytest.raises(CandleError, match="redirect_refused:302"):
        check_http(resp)
    ok = session.get(f"{collector}/direct", timeout=5)  # normal market-data responses are unaffected
    assert ok.status_code == 200 and ok.json()["serverTime"] == 1
    check_http(ok)


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_every_3xx_is_an_error(status):
    class Resp:
        status_code = status

    with pytest.raises(CandleError, match=f"redirect_refused:{status}"):
        check_http(Resp())
