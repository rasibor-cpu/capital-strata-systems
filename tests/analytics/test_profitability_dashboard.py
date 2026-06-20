import pytest
import io
import sys
from unittest.mock import patch, MagicMock
from analytics.trade_outcome_ledger import TradeOutcomeLedger, TradeOutcome, print_profitability_dashboard

@pytest.fixture
def mock_ledger():
    with patch("analytics.trade_outcome_ledger.TradeOutcomeLedger") as mock:
        yield mock

def test_dashboard_displays_profitability_empty_ledger(mock_ledger):
    mock_instance = mock_ledger.return_value
    mock_instance.summarize.return_value = {
        "overall": {},
        "by_asset_class": {},
        "top_winning_symbols": [],
        "top_losing_symbols": []
    }
    
    # Capture stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    print_profitability_dashboard()
    
    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()
    
    assert "=== PROFITABILITY ANALYTICS ===" in output
    assert "Overall:" in output
    assert "* Total Trades:   0" in output
    assert "* FX:" in output
    assert "Top 5 Winning Symbols:" in output
    assert "Top 5 Losing Symbols:" in output


def test_dashboard_displays_populated_ledger(mock_ledger):
    mock_instance = mock_ledger.return_value
    mock_instance.summarize.return_value = {
        "overall": {
            "total_trades": 10,
            "winning_trades": 6,
            "losing_trades": 4,
            "win_rate": 0.6,
            "net_realized_pnl": 500.0,
            "average_win": 100.0,
            "average_loss": 25.0,
            "profit_factor": 4.0
        },
        "by_asset_class": {
            "FX": {
                "total_trades": 10,
                "win_rate": 0.6,
                "net_realized_pnl": 500.0
            }
        },
        "top_winning_symbols": [
            {"symbol": "EUR_USD", "pnl": 300.0},
            {"symbol": "GBP_USD", "pnl": 200.0}
        ],
        "top_losing_symbols": [
            {"symbol": "USD_JPY", "pnl": -100.0}
        ]
    }
    
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    print_profitability_dashboard()
    
    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()
    
    assert "=== PROFITABILITY ANALYTICS ===" in output
    assert "* Total Trades:   10" in output
    assert "* Winning Trades: 6" in output
    assert "* Win Rate %:     60.00%" in output
    assert "* Net Realized PnL: +500.0000" in output
    assert "* EUR_USD: +300.0000" in output
    assert "* USD_JPY: -100.0000" in output


def test_analytics_errors_do_not_interrupt_runtime(mock_ledger):
    mock_ledger.side_effect = Exception("Database disk image is malformed")
    
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    print_profitability_dashboard()
    
    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()
    
    assert "[PROFITABILITY ANALYTICS WARN] Database disk image is malformed" in output
