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
    
    assert "=== STRATEGY INTELLIGENCE ===" in output
    assert "Entry Reason Rankings:" in output
    assert "Asset Class Rankings:" in output
    assert "Symbol Rankings:" in output
    assert "* None" in output

def test_dashboard_displays_populated_rankings(mock_engine):
    mock_instance = mock_engine.return_value
    mock_instance.summarize_rankings.return_value = {
        "by_entry_reason": {
            "SIGNAL_A": {
                "trades": 10,
                "wins": 6,
                "losses": 4,
                "win_rate": 0.6,
                "net_realized_pnl": 500.0,
                "profit_factor": 2.5,
                "expectancy": 50.0,
                "average_duration": 120.0,
                "confidence_trend": "UP",
                "rolling_performance": {"recent_average_return": 0.5, "baseline_average_return": 0.3},
                "lifecycle_recommendation": "PROMOTE",
                "rank": "PROMOTE_CANDIDATE",
            }
        },
        "by_asset_class": {
            "FX": {
                "trades": 4,
                "wins": 2,
                "losses": 2,
                "win_rate": 0.5,
                "net_realized_pnl": -50.0,
                "profit_factor": 0.8,
                "expectancy": -12.5,
                "average_duration": 60.0,
                "confidence_trend": "DOWN",
                "rolling_performance": {"recent_average_return": -0.2, "baseline_average_return": -0.1},
                "lifecycle_recommendation": "WATCH",
                "rank": "WATCHLIST",
            }
        },
        "by_symbol": {
            "EUR_USD": {
                "trades": 8,
                "wins": 2,
                "losses": 6,
                "win_rate": 0.25,
                "net_realized_pnl": -200.0,
                "profit_factor": 0.3,
                "expectancy": -25.0,
                "average_duration": 75.0,
                "confidence_trend": "DOWN",
                "rolling_performance": {"recent_average_return": -0.4, "baseline_average_return": -0.2},
                "lifecycle_recommendation": "DEMOTE",
                "rank": "DEMOTE_CANDIDATE",
            }
        }
    }
    
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    print_strategy_ranking_dashboard()
    
    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()
    
    assert "=== STRATEGY INTELLIGENCE ===" in output
    assert "* SIGNAL_A [PROMOTE]" in output
    assert "Net PnL:   +500.0000" in output
    assert "* FX [WATCH]" in output
    assert "Net PnL:   -50.0000" in output
    assert "* EUR_USD [DEMOTE]" in output
    assert "Net PnL:   -200.0000" in output

def test_dashboard_errors_do_not_interrupt_runtime(mock_engine):
    mock_engine.side_effect = Exception("JSON Decode Error")
    
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    print_strategy_ranking_dashboard()
    
    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()
    
    assert "[STRATEGY RANKING WARN] JSON Decode Error" in output
