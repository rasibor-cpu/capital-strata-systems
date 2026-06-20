import pytest
import io
import sys
from unittest.mock import patch, MagicMock
from analytics.strategy_ranking_engine import print_strategy_ranking_dashboard

@pytest.fixture
def mock_engine():
    with patch("analytics.strategy_ranking_engine.StrategyRankingEngine") as mock:
        yield mock

def test_dashboard_displays_empty_rankings_safely(mock_engine):
    mock_instance = mock_engine.return_value
    mock_instance.summarize_rankings.return_value = {
        "by_entry_reason": {},
        "by_asset_class": {},
        "by_symbol": {}
    }
    
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    print_strategy_ranking_dashboard()
    
    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()
    
    assert "=== STRATEGY RANKINGS ===" in output
    assert "Entry Reason Rankings:" in output
    assert "Asset Class Rankings:" in output
    assert "Symbol Rankings:" in output
    assert "* None" in output

def test_dashboard_displays_populated_rankings(mock_engine):
    mock_instance = mock_engine.return_value
    mock_instance.summarize_rankings.return_value = {
        "by_entry_reason": {
            "SIGNAL_A": {
                "trade_count": 10,
                "win_rate": 0.6,
                "net_realized_pnl": 500.0,
                "profit_factor": 2.5,
                "rank": "PROMOTE_CANDIDATE"
            }
        },
        "by_asset_class": {
            "FX": {
                "trade_count": 4,
                "win_rate": 0.5,
                "net_realized_pnl": -50.0,
                "profit_factor": 0.8,
                "rank": "INSUFFICIENT_SAMPLE"
            }
        },
        "by_symbol": {
            "EUR_USD": {
                "trade_count": 8,
                "win_rate": 0.25,
                "net_realized_pnl": -200.0,
                "profit_factor": 0.3,
                "rank": "DEMOTE_CANDIDATE"
            }
        }
    }
    
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    print_strategy_ranking_dashboard()
    
    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()
    
    assert "=== STRATEGY RANKINGS ===" in output
    assert "* SIGNAL_A [PROMOTE_CANDIDATE]" in output
    assert "Net PnL:   +500.0000" in output
    assert "* FX [INSUFFICIENT_SAMPLE]" in output
    assert "Net PnL:   -50.0000" in output
    assert "* EUR_USD [DEMOTE_CANDIDATE]" in output
    assert "Net PnL:   -200.0000" in output

def test_dashboard_errors_do_not_interrupt_runtime(mock_engine):
    mock_engine.side_effect = Exception("JSON Decode Error")
    
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    print_strategy_ranking_dashboard()
    
    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()
    
    assert "[STRATEGY RANKING WARN] JSON Decode Error" in output
