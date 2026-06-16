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
    with patch("backend.app.brokers.oanda_adapter.OandaAdapter.place_order") as mock_place:
        mock_place.return_value = {
            "ok": True,
            "data": {
                "orderFillTransaction": {
                    "tradeOpened": {"tradeID": "222"},
                    "price": "1.0020"
                }
            }
        }
        
        ok, msg, tid, fill_price, etime, slippage = dashboard.attempt_oanda_fx_execution("EUR_USD", expected_price=None)
        
        assert ok is True
        assert slippage is None
        assert mock_place.call_args[1].get("price_bound") is None

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
    # What if OANDA somehow returned a fill outside our requested bound?
    # Our code doesn't fail closed retroactively on the slippage variable itself, 
    # it relies on OANDA's 400 rejection (which is tested above).
    # But let's verify that the slippage is correctly calculated even if it's large.
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
