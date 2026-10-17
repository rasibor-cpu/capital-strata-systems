import os
import sys
import pytest
from unittest.mock import patch, MagicMock

os.environ["CSS_TEST_MODE"] = "1"
os.environ["OANDA_API_KEY"] = "mock_key"
os.environ["OANDA_ACCOUNT_ID"] = "mock_acc"
os.environ["OANDA_BASE_URL"] = "http://mock.com"
os.environ["OANDA_ENV"] = "practice"
os.environ["DATA_PROVIDER"] = "SIMULATED"

@pytest.fixture(scope="module")
def dashboard():
    mock_auth = MagicMock()
    mock_auth.await_login_ready_state.return_value = {
        "user_id": "test", 
        "role": "admin", 
        "display_name": "test", 
        "unit_code": "test", 
        "home_branch": "test"
    }
    sys.modules["dashboard.auth.css_sign_on"] = mock_auth
    sys.modules["builtins"].input = lambda prompt: "1"

    import scripts.css_live_dashboard as db
    yield db

_OANDA_NETWORK_ATTEMPTS = []


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    """Test isolation (Grok re-audit R-5): these tests must never reach the OANDA REST host (or any
    other non-loopback host). The adapter's HTTP call fails exactly as an unreachable network does
    (requests.ConnectionError), so its own error handling still runs, without real DNS, sockets
    or backoff sleeps. Any other outbound attempt fails the test loudly."""
    import socket

    import requests

    import backend.app.brokers.oanda_adapter as oanda_adapter

    def offline_request(method, url, **kwargs):
        _OANDA_NETWORK_ATTEMPTS.append((method, url))
        raise requests.ConnectionError("network disabled in unit tests")

    monkeypatch.setattr(oanda_adapter.requests, "request", offline_request)
    monkeypatch.setattr(oanda_adapter.time, "sleep", lambda _s: None)

    loopback = {"127.0.0.1", "::1", "localhost", None}
    real_getaddrinfo, real_connect = socket.getaddrinfo, socket.socket.connect

    def guarded_getaddrinfo(host, *a, **k):
        if host not in loopback:
            raise AssertionError(f"unexpected external DNS lookup in unit test: {host}")
        return real_getaddrinfo(host, *a, **k)

    def guarded_connect(sock, addr, *a, **k):
        if isinstance(addr, tuple) and addr[0] not in loopback:
            raise AssertionError(f"unexpected external connection in unit test: {addr}")
        return real_connect(sock, addr, *a, **k)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture(autouse=True)
def reset_dashboard_state(dashboard):
    dashboard._CSS_SESSION_LOCK.clear()
    dashboard.RECONCILIATION_STATUS = "HEALTHY"
    dashboard.mtm_engine.positions.clear()
    dashboard.SELECTED_BROKER = "OANDA"
    dashboard.BROKER_EXECUTION_ARMED = True
    dashboard.ENGINE_MODE = "EXPANSION"
    dashboard.SESSION_USER_CTX["role_profile"] = {"can_execute_paper_trading": True}

def test_successful_execution_within_bounds(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.place_order") as mock_place:
        mock_place.return_value = {
            "ok": True,
            "data": {
                "orderFillTransaction": {
                    "tradeOpened": {"tradeID": "111"},
                    "price": "1.0020",
                    "time": "2026-06-16T00:00:00Z"
                }
            }
        }
        
        ok, msg, tid, fill_price, etime, slippage = dashboard.attempt_oanda_fx_execution("EUR_USD", expected_price=1.0000)
        
        assert ok is True
        assert tid == "111"
        assert slippage == pytest.approx(0.0020)
        assert mock_place.call_args[1]["price_bound"] == str(1.0000 + dashboard.OANDA_MAX_SLIPPAGE)
        assert not dashboard.is_session_locked()

def test_missing_expected_price(dashboard):
    # This scenario is now handled gracefully by the early return fail-closed block,
    # so we don't even reach place_order.
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.place_order") as mock_place:
        ok, msg, tid, fill_price, etime, slippage = dashboard.attempt_oanda_fx_execution("EUR_USD", expected_price=None)
        
        assert ok is False
        assert msg == "OANDA_BLOCKED_MISSING_EXPECTED_PRICE"
        mock_place.assert_not_called()

def test_price_bound_rejection(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.place_order") as mock_place:
        mock_place.return_value = {
            "ok": False,
            "status": 400,
            "error": "The order was cancelled because it would result in a fill outside the priceBound limits. PRICE_BOUND"
        }
        
        ok, msg, tid, fill_price, etime, slippage = dashboard.attempt_oanda_fx_execution("EUR_USD", expected_price=1.0000)
        
        assert ok is False
        assert dashboard.is_session_locked()
        assert dashboard._CSS_SESSION_LOCK.get("reason") == "OANDA_SLIPPAGE_REJECTION"

def test_slippage_calculation_accuracy(dashboard):
    # Verify exact math
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.place_order") as mock_place:
        mock_place.return_value = {
            "ok": True,
            "data": {
                "orderFillTransaction": {
                    "tradeOpened": {"tradeID": "333"},
                    "price": "1.0049"
                }
            }
        }
        
        ok, msg, tid, fill_price, etime, slippage = dashboard.attempt_oanda_fx_execution("EUR_USD", expected_price=1.0000)
        assert slippage == pytest.approx(0.0049)

def test_execution_exceeding_bounds(dashboard):
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.place_order") as mock_place:
        mock_place.return_value = {
            "ok": True,
            "data": {
                "orderFillTransaction": {
                    "tradeOpened": {"tradeID": "444"},
                    "price": "1.0500"  # Massive 500 pip slippage
                }
            }
        }
        
        ok, msg, tid, fill_price, etime, slippage = dashboard.attempt_oanda_fx_execution("EUR_USD", expected_price=1.0000)
        assert slippage == pytest.approx(0.0500)

def test_missing_expected_price_blocks_execution(dashboard):
    ok, msg, tid, fill_price, etime, slippage = dashboard.attempt_oanda_fx_execution("EUR_USD", expected_price=None)
    assert ok is False
    assert msg == "OANDA_BLOCKED_MISSING_EXPECTED_PRICE"

def test_negative_zero_expected_price_blocks_execution(dashboard):
    ok, msg, tid, fill_price, etime, slippage = dashboard.attempt_oanda_fx_execution("EUR_USD", expected_price=0.0)
    assert ok is False
    assert msg == "OANDA_BLOCKED_MISSING_EXPECTED_PRICE"
    
    ok, msg, tid, fill_price, etime, slippage = dashboard.attempt_oanda_fx_execution("EUR_USD", expected_price=-1.0)
    assert ok is False
    assert msg == "OANDA_BLOCKED_MISSING_EXPECTED_PRICE"

def test_resolve_expected_fx_price_valid(dashboard):
    with patch("backend.data.price_feed.PriceFeed.get_price") as mock_get_price:
        mock_get_price.return_value = 1.0500
        assert dashboard.resolve_expected_fx_price("EUR_USD") == 1.0500

def test_resolve_expected_fx_price_invalid(dashboard):
    with patch("backend.data.price_feed.PriceFeed.get_price") as mock_get_price:
        mock_get_price.return_value = 0.0
        assert dashboard.resolve_expected_fx_price("EUR_USD") is None
        
        mock_get_price.return_value = None
        assert dashboard.resolve_expected_fx_price("EUR_USD") is None
        
        mock_get_price.side_effect = Exception("Network Error")
        assert dashboard.resolve_expected_fx_price("EUR_USD") is None



def test_oanda_calls_are_intercepted_not_sent(dashboard):
    """The open-trade check reaches the adapter, which is answered offline (never the network)."""
    before = len(_OANDA_NETWORK_ATTEMPTS)
    dashboard.get_oanda_open_trade_count()
    assert len(_OANDA_NETWORK_ATTEMPTS) > before
    assert all("mock.com" in url for _m, url in _OANDA_NETWORK_ATTEMPTS)
