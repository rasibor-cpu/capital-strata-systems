import pytest
from unittest.mock import patch
from dashboard.mobile.mobile_app import _trade_summary_page

@pytest.fixture
def dummy_ctx():
    return {"user_id": "TEST_USER", "role": "SUPER_USER", "display_name": "Test User"}

def test_trade_summary_page_empty(dummy_ctx):
    with patch("analytics.trade_outcome_ledger.TradeOutcomeLedger.list_trades", return_value=[]):
        html = _trade_summary_page(dummy_ctx, {})
        assert "No closed trades recorded yet" in html

def test_trade_summary_page_populated(dummy_ctx):
    from analytics.trade_outcome_ledger import TradeOutcome
    mock_trade = TradeOutcome(
        trade_id="test1",
        asset_class="CRYPTO",
        symbol="BTC-USD",
        entry_timestamp="2026-06-20T10:00:00Z",
        exit_timestamp="2026-06-20T11:00:00Z",
        holding_seconds=3600,
        entry_reason="MOCK",
        exit_reason="TP",
        entry_price=60000.0,
        exit_price=61000.0,
        quantity=1.0,
        realized_pnl=1000.0,
        max_favorable_excursion=0.0,
        max_adverse_excursion=0.0,
        win_loss="WIN",
        side="BUY",
        amount_traded=60000.0,
        cumulative_account_balance=100000.0,
        engine_mode="SAFE",
        broker_mode="PAPER"
    )
    with patch("analytics.trade_outcome_ledger.TradeOutcomeLedger.list_trades", return_value=[mock_trade]):
        html = _trade_summary_page(dummy_ctx, {})
        assert "BTC-USD" in html
        assert "CRYPTO" in html
        assert "BUY" in html
        assert "1.0" in html
        assert "60000.00" in html
        assert "+1000.00" in html
        assert "100000.00" in html
        assert "TP" in html
