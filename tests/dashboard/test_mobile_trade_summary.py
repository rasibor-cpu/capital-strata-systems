import pytest
from bs4 import BeautifulSoup
from dashboard.mobile import mobile_app
from backend.app.persistence.services.session_runtime_service import SessionRuntimeService
from backend.app.persistence.services.pnl_runtime_service import PnlRuntimeService
from backend.app.persistence.services.trade_runtime_service import TradeRuntimeService

TRADER = {
    "user_id": "00017",
    "display_name": "CSS Trader",
    "role": "TRADER",
}

def test_trade_status_page_renders_with_no_session(monkeypatch):
    monkeypatch.setattr(mobile_app, "load_local_env", lambda: None)
    monkeypatch.setattr(SessionRuntimeService, "get_active_sessions", lambda *args, **kwargs: [])
    # If no session, it should render "DATA UNAVAILABLE" and no fake data.
    html = mobile_app._trade_status_page(TRADER, {"created": 1.0})
    
    # Must contain "DATA UNAVAILABLE"
    assert "DATA UNAVAILABLE" in html
    assert "No active CSS runtime session" in html

def test_trade_status_page_renders_with_canonical_data(monkeypatch):
    monkeypatch.setattr(mobile_app, "load_local_env", lambda: None)
    # Mock services to return canonical data
    def mock_get_active_sessions(*args, **kwargs):
        return [{"session_id": "fake-session-123"}]
        
    def mock_get_latest_snapshot(*args, **kwargs):
        return {
            "account_balance": 15000.50,
            "available_cash": 10000.00,
            "buying_power": 10000.00,
            "equity": 15000.50,
            "unrealized_pnl": 500.50,
            "realized_pnl": 100.00,
            "net_pnl": 600.50,
            "open_positions": 2,
            "closed_positions": 1,
            "pending_orders": 0,
            "rejected_orders": 0,
            "winning_positions": 1,
            "losing_positions": 1,
        }
        
    def mock_get_all_session_trades(*args, **kwargs):
        return [
            {
                "trade_id": "TRADE123",
                "symbol": "BTC-USD",
                "direction": "LONG",
                "asset_class": "CRYPTO",
                "status": "open",
                "quantity": "1.0",
                "entry_price": "60000.0",
                "current_price": "60500.0",
                "realized_pnl": "0.0",
                "gate_decision": "PASSED",
                "broker_name": "CSS_PAPER",
                "opened_at": "2026-06-17T01:00:00.000Z",
            }
        ]
        
    monkeypatch.setattr(SessionRuntimeService, "get_active_sessions", mock_get_active_sessions)
    monkeypatch.setattr(PnlRuntimeService, "get_latest_snapshot", mock_get_latest_snapshot)
    monkeypatch.setattr(TradeRuntimeService, "get_all_session_trades", mock_get_all_session_trades)
    
    html = mobile_app._trade_status_page(TRADER, {"created": 1.0})
    
    assert "15000.5" in html
    assert "10000.0" in html
    assert "TRADE123" in html
    assert "BTC-USD" in html
    assert "CSS_PAPER" in html
    assert "CRYPTO" in html
    assert "60500.0" in html
    assert "PASSED" in html
    
    # Should not have DATA UNAVAILABLE since we provided the data
    assert "DATA UNAVAILABLE" not in html

def test_mobile_status_page_does_not_execute_trades(monkeypatch):
    executed = []
    def mock_execute(*args, **kwargs):
        executed.append(True)
    monkeypatch.setattr(mobile_app, "execute_mobile_trade_ticket", mock_execute, raising=False)
    monkeypatch.setattr(mobile_app, "load_local_env", lambda: None)
    monkeypatch.setattr(SessionRuntimeService, "get_active_sessions", lambda *args, **kwargs: [])
    mobile_app._trade_status_page(TRADER, {"created": 1.0})
    assert not executed
