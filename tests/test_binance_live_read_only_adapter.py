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
    BinanceLiveReadOnlyAdapter,
    BinanceReadOnlyError,
    BinanceReadOnlyMethodError,
)


NOW = datetime(2026, 9, 4, 22, 0, tzinfo=timezone.utc)
API_KEY = "test-binance-api-key"
API_SECRET = "test-binance-api-secret-material"


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
    adapter = BinanceLiveReadOnlyAdapter(env={}, transport=transport, now=lambda: NOW)
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
