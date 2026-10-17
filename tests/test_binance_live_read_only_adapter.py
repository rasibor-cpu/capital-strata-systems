from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import urlencode

import pytest
import requests

from backend.app.brokers.binance_live_read_only_adapter import (
    SOURCE_BINANCE_LIVE_READ_ONLY,
    BinanceConfigurationError,
    BinanceJurisdictionError,
    BinanceLiveReadOnlyAdapter,
    BinanceReadOnlyError,
    BinanceReadOnlyMethodError,
)


NOW = datetime(2026, 9, 4, 22, 0, tzinfo=timezone.utc)
API_KEY = "test-binance-api-key"
API_SECRET = "test-binance-api-secret-material"
# SYNTHETIC attestation of an operating country Binance serves; the adapter refuses every request
# when the country is unattested or restricted (CA, US, ...).
SYNTHETIC_COUNTRY = "DE"


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class RecordingTransport:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[dict] = []

    def __call__(self, method, url, headers=None, params=None):
        record = {
            "method": method,
            "url": url,
            "headers": dict(headers or {}),
            "params": dict(params or {}),
        }
        self.calls.append(record)
        return self.handler(record)


def _env(**overrides):
    payload = {
        "BINANCE_API_KEY": API_KEY,
        "BINANCE_API_SECRET": API_SECRET,
        "BINANCE_BASE_URL": "https://api.binance.com",
        "CSS_OPERATING_COUNTRY": SYNTHETIC_COUNTRY,
    }
    payload.update(overrides)
    return payload


def _adapter(transport, **env_overrides):
    return BinanceLiveReadOnlyAdapter(
        env=_env(**env_overrides),
        transport=transport,
        now=lambda: NOW,
    )


def test_get_only_enforcement_rejects_non_get_before_network() -> None:
    transport = RecordingTransport(lambda _call: FakeResponse({"serverTime": 1}))
    adapter = _adapter(transport)
    with pytest.raises(BinanceReadOnlyMethodError):
        adapter._request("POST", "/api/v3/order", signed=True)
    with pytest.raises(BinanceReadOnlyMethodError):
        adapter._request("DELETE", "/api/v3/order", signed=True)
    with pytest.raises(BinanceReadOnlyMethodError):
        adapter._request("PUT", "/api/v3/order", signed=True)
    assert transport.calls == []


def test_adapter_exposes_no_write_or_execution_methods() -> None:
    public_methods = {
        name
        for name in dir(BinanceLiveReadOnlyAdapter)
        if not name.startswith("_") and callable(getattr(BinanceLiveReadOnlyAdapter, name))
    }
    forbidden = (
        "submit",
        "place",
        "cancel",
        "modify",
        "replace",
        "withdraw",
        "deposit",
        "transfer",
        "order",
        "leverage",
        "close",
    )
    assert not any(fragment in method.lower() for method in public_methods for fragment in forbidden)
    assert "positions" not in public_methods
    assert "get_positions" not in public_methods


def test_missing_credentials_fail_before_authenticated_network() -> None:
    transport = RecordingTransport(lambda _call: FakeResponse({"balances": []}))
    adapter = BinanceLiveReadOnlyAdapter(env={"CSS_OPERATING_COUNTRY": SYNTHETIC_COUNTRY}, transport=transport, now=lambda: NOW)
    with pytest.raises(BinanceConfigurationError):
        adapter.get_account()
    assert transport.calls == []
    diagnostics = adapter.credential_diagnostics()
    assert diagnostics["credential_status"] == "MISSING"
    assert diagnostics["redacted"] is True
    assert API_SECRET not in str(diagnostics)
    assert "api_key" not in dir(adapter)
    assert "api_secret" not in dir(adapter)


def test_signature_construction_does_not_leak_secret() -> None:
    def handler(call):
        assert call["method"] == "GET"
        assert call["url"] == "https://api.binance.com/api/v3/account"
        assert call["headers"]["X-MBX-APIKEY"] == API_KEY
        assert API_SECRET not in call["url"]
        assert API_SECRET not in call["headers"].values()
        assert API_SECRET not in {str(v) for v in call["params"].values()}
        expected = hmac.new(
            API_SECRET.encode("utf-8"),
            urlencode({"timestamp": int(NOW.timestamp() * 1000)}).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        assert call["params"]["signature"] == expected
        return FakeResponse(
            {
                "accountType": "SPOT",
                "uid": 123,
                "updateTime": 1,
                "balances": [{"asset": "USDT", "free": "1.5", "locked": "0.5"}],
            }
        )

    transport = RecordingTransport(handler)
    adapter = _adapter(transport)
    account = adapter.get_account()
    assert account["source"] == SOURCE_BINANCE_LIVE_READ_ONLY
    assert API_SECRET not in str(account)
    assert API_SECRET not in repr(adapter)


def test_account_balance_parsing_and_affirmative_zero() -> None:
    transport = RecordingTransport(
        lambda _call: FakeResponse(
            {
                "accountType": "SPOT",
                "balances": [
                    {"asset": "BTC", "free": "0.00000000", "locked": "0.00000000"},
                    {"asset": "ETH", "free": "1.25", "locked": "0.25"},
                    {"asset": "USDT", "free": "10", "locked": "0"},
                ],
            }
        )
    )
    rows = _adapter(transport).get_balances()
    btc = next(row for row in rows if row["asset"] == "BTC")
    eth = next(row for row in rows if row["asset"] == "ETH")
    assert btc["available_quantity"] == 0.0
    assert btc["available_quantity_availability"] == "AVAILABLE"
    assert btc["held_quantity"] == 0.0
    assert btc["held_quantity_availability"] == "AVAILABLE"
    assert btc["total_quantity"] == 0.0
    assert btc["total_quantity_provenance"] == "derived_available_plus_held"
    assert btc["market_value"] is None
    assert eth["available_quantity"] == 1.25
    assert eth["held_quantity"] == 0.25
    assert eth["total_quantity"] == 1.5
    assert all(row["provenance"] == SOURCE_BINANCE_LIVE_READ_ONLY for row in rows)
    summary = _adapter(
        RecordingTransport(
            lambda _call: FakeResponse(
                {"accountType": "SPOT", "balances": [{"asset": "BTC", "free": "0.0", "locked": "0.0"}]}
            )
        )
    ).account_summary()
    assert summary["open_positions_availability"] == "UNAVAILABLE"
    assert summary["session_pnl_availability"] == "UNAVAILABLE"
    assert summary["maturity_availability"] == "UNAVAILABLE"


def test_exchange_info_and_ticker_parsing() -> None:
    def handler(call):
        if call["url"].endswith("/api/v3/exchangeInfo"):
            return FakeResponse(
                {
                    "symbols": [
                        {"symbol": "BTCUSDT", "status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT"},
                        {"symbol": "ETHUSDT", "status": "TRADING", "baseAsset": "ETH", "quoteAsset": "USDT"},
                    ]
                }
            )
        if call["url"].endswith("/api/v3/ticker/price"):
            return FakeResponse({"symbol": "BTCUSDT", "price": "65000.1"})
        raise AssertionError(call["url"])

    adapter = _adapter(RecordingTransport(handler))
    products = adapter.get_products()
    assert {row["symbol"] for row in products} == {"BTCUSDT", "ETHUSDT"}
    quote = adapter.get_ticker("BTCUSDT")
    assert quote["price"] == 65000.1
    assert quote["market_value_availability"] == "UNAVAILABLE"


def test_authentication_and_network_failures() -> None:
    adapter = _adapter(RecordingTransport(lambda _call: FakeResponse({"code": -2015, "msg": "Invalid API-key"}, 401)))
    with pytest.raises(BinanceReadOnlyError, match="unauthorized"):
        adapter.get_account()

    def boom(_call):
        raise requests.ConnectionError("dns failure")

    with pytest.raises(BinanceReadOnlyError, match="network"):
        _adapter(RecordingTransport(boom)).server_time()


def test_malformed_responses_fail_closed() -> None:
    adapter = _adapter(RecordingTransport(lambda _call: FakeResponse({"oops": True})))
    with pytest.raises(BinanceReadOnlyError, match="malformed_account_response"):
        adapter.get_account()
    with pytest.raises(BinanceReadOnlyError, match="malformed_exchange_info"):
        _adapter(RecordingTransport(lambda _call: FakeResponse({"symbols": []}))).get_exchange_info()
    with pytest.raises(BinanceReadOnlyError, match="malformed_ticker_response"):
        _adapter(RecordingTransport(lambda _call: FakeResponse({"symbol": "BTCUSDT"}))).get_ticker()


def test_safety_flags_remain_fail_closed() -> None:
    posture = BinanceLiveReadOnlyAdapter(env=_env()).safety_posture()
    assert posture["execution_allowed"] is False
    assert posture["live_trading_blocked"] is True
    assert posture["broker_execution_armed"] is False
    assert posture["advisory_only"] is True
    assert BinanceLiveReadOnlyAdapter.execution_allowed is False
    assert BinanceLiveReadOnlyAdapter.live_trading_blocked is True
    assert BinanceLiveReadOnlyAdapter.broker_execution_armed is False
    assert BinanceLiveReadOnlyAdapter.advisory_only is True


# --------------------------------------------------------------- jurisdiction gate and host allowlist
@pytest.mark.parametrize("country", ["CA", "ca", "US", "", "XX1", None])
def test_restricted_or_unattested_country_sends_no_request_signed_or_not(country) -> None:
    transport = RecordingTransport(lambda _call: FakeResponse({"serverTime": 1, "balances": []}))
    env = _env()
    if country is None:
        env.pop("CSS_OPERATING_COUNTRY")
    else:
        env["CSS_OPERATING_COUNTRY"] = country
    adapter = BinanceLiveReadOnlyAdapter(env=env, transport=transport, now=lambda: NOW)
    assert adapter.eligible is False
    for call in (adapter.get_account, adapter.server_time, adapter.get_exchange_info, adapter.get_ticker):
        with pytest.raises(BinanceJurisdictionError):
            call()
    assert transport.calls == []  # neither the API key nor a signature ever left the process
    assert adapter.credential_diagnostics()["binance_eligible"] is False


@pytest.mark.parametrize("url", [
    "http://api.binance.com",
    "https://evil.example.com",
    "https://api.binance.com.evil.example.com",
    "https://user:pw@api.binance.com",
    "https://api.binance.com:8443",
    "https://api.binance.com/proxy",
    "https://testnet.binance.vision",
    "ftp://api.binance.com",
    "https://api.binance.com:notaport",
    "https://[::1",
])
def test_non_allowlisted_base_url_is_refused_before_any_request(url) -> None:
    transport = RecordingTransport(lambda _call: FakeResponse({"serverTime": 1, "balances": []}))
    for var in ("BINANCE_BASE_URL", "BINANCE_API_URL", "BINANCE_REST_URL"):
        env = _env()
        env.pop("BINANCE_BASE_URL")
        env[var] = url
        adapter = BinanceLiveReadOnlyAdapter(env=env, transport=transport, now=lambda: NOW)
        assert adapter.base_url == "" and adapter.is_configured() is False
        assert adapter.credential_diagnostics()["binance_base_url_rejected"] is True
        with pytest.raises(BinanceConfigurationError, match="binance_base_url_not_allowlisted"):
            adapter._request("GET", "/api/v3/time")
    assert transport.calls == []


@pytest.mark.parametrize("url", ["https://api.binance.com", "https://api1.binance.com/", "https://API-GCP.binance.com"])
def test_allowlisted_binance_hosts_are_accepted(url) -> None:
    transport = RecordingTransport(lambda _call: FakeResponse({"serverTime": 1}))
    adapter = _adapter(transport, BINANCE_BASE_URL=url)
    adapter.server_time()
    assert transport.calls[0]["url"].startswith(f"https://{url.split('//')[1].strip('/').lower()}/api/v3/time")


# --------------------------------------------------------------- Grok final audit F-3 (Unicode look-alikes)
@pytest.mark.parametrize("country", [
    "СА",            # Cyrillic ES + A, renders as "CA"
    "ＣＡ",            # fullwidth "ＣＡ"
    "СA",                 # mixed Cyrillic/Latin "СA"
    "UЅ",                 # "UЅ" (Cyrillic DZE)
    "C​A",                # zero-width space inside
    "KR",                 # Kelvin sign + R (case-folds to "KR")
    "ſE",                 # long s (upper() -> "SE")
    "XX", "ZZ", "QQ",          # ASCII but not assigned ISO 3166-1 alpha-2
    "C A", "CA ", "1A",
])
def test_unicode_confusable_or_unassigned_country_sends_nothing(country) -> None:
    signed = []
    transport = RecordingTransport(lambda _call: FakeResponse({"serverTime": 1, "balances": []}))
    adapter = _adapter(transport, CSS_OPERATING_COUNTRY=country)
    real_new = hmac.new
    try:
        hmac.new = lambda *a, **k: signed.append(1) or real_new(*a, **k)  # spy: no signing may happen
        with pytest.raises(BinanceJurisdictionError):
            adapter.get_account()
    finally:
        hmac.new = real_new
    assert adapter.eligible is False and transport.calls == [] and signed == []


@pytest.mark.parametrize("country", ["DE", "de", " gb ", "Jp"])
def test_valid_ascii_iso_country_is_accepted(country) -> None:
    transport = RecordingTransport(lambda _call: FakeResponse({"serverTime": 1}))
    adapter = _adapter(transport, CSS_OPERATING_COUNTRY=country)
    adapter.server_time()
    assert adapter.eligible is True and len(transport.calls) == 1


def test_eligibility_cannot_be_overridden_after_construction() -> None:
    adapter = _adapter(RecordingTransport(lambda _call: FakeResponse({})), CSS_OPERATING_COUNTRY="CA")
    with pytest.raises(AttributeError):
        adapter.eligible = True
    assert adapter.eligible is False


# --------------------------------------------------------------- Grok final audit F-4 (redirects)
def _two_local_servers():
    """Server A answers every request with a 302 to server B (a different host:port); B records
    whatever headers reach it. Loopback only; synthetic credentials only."""
    import http.server
    import threading

    received = []

    class B(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(dict(self.headers))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"balances": []}')

        def log_message(self, *a):
            pass

    b = http.server.HTTPServer(("127.0.0.1", 0), B)

    class A(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", f"http://localhost:{b.server_port}/collect")
            self.end_headers()

        def log_message(self, *a):
            pass

    a = http.server.HTTPServer(("127.0.0.1", 0), A)
    for srv in (a, b):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    return a, b, received


def test_default_transport_never_forwards_the_api_key_across_a_redirect(monkeypatch) -> None:
    for var in ("NO_PROXY", "no_proxy"):  # loopback traffic must not go through any configured proxy
        monkeypatch.setenv(var, "127.0.0.1,localhost")
    a, b, received = _two_local_servers()
    try:
        adapter = BinanceLiveReadOnlyAdapter(env=_env(), now=lambda: NOW)  # real requests transport
        adapter.base_url = f"http://127.0.0.1:{a.server_port}"  # test only: stand-in for a redirecting host
        with pytest.raises(BinanceReadOnlyError, match="redirect_refused:302"):
            adapter.get_account()
        assert received == []  # server B was never contacted: the key header never left for another host
        # The defect it guards against: a redirect-following GET carries X-MBX-APIKEY to server B.
        requests.get(f"http://127.0.0.1:{a.server_port}/api/v3/account", headers={"X-MBX-APIKEY": API_KEY}, timeout=5)
        assert received and received[0].get("X-MBX-APIKEY") == API_KEY
    finally:
        a.shutdown()
        b.shutdown()


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_every_3xx_is_an_error(status) -> None:
    transport = RecordingTransport(lambda _call: FakeResponse({"serverTime": 1}, status_code=status))
    with pytest.raises(BinanceReadOnlyError, match=f"redirect_refused:{status}"):
        _adapter(transport).get_account()
    assert len(transport.calls) == 1


def test_default_transport_disables_redirects(monkeypatch) -> None:
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return FakeResponse({"serverTime": 1})

    monkeypatch.setattr(requests, "get", fake_get)
    BinanceLiveReadOnlyAdapter(env=_env(), now=lambda: NOW).server_time()
    assert seen.get("allow_redirects") is False
