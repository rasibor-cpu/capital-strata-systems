import pytest
from unittest.mock import MagicMock
from analytics.trade_outcome_ledger import TradeOutcome
from analytics.strategy_ranking_engine import StrategyRankingEngine, MIN_STRATEGY_SAMPLE_SIZE

def test_empty_ledger():
    mock_ledger = MagicMock()
    mock_ledger.list_trades.return_value = []
    
    engine = StrategyRankingEngine(ledger=mock_ledger)
    res = engine.summarize_rankings()
    
    assert res == {
        "by_entry_reason": {},
        "by_asset_class": {},
        "by_symbol": {}
    }

def test_insufficient_sample():
    mock_ledger = MagicMock()
    # 3 trades -> < 5, lifecycle recommendation remains WATCH
    t = TradeOutcome("1", "FX", "EUR_USD", "", "", 0.0, "SIGNAL_A", "", 1.0, 1.1, 1.0, 10.0, 0.0, 0.0, "WIN")
    mock_ledger.list_trades.return_value = [t, t, t]
    
    engine = StrategyRankingEngine(ledger=mock_ledger)
    res = engine.rank_by_entry_reason()
    
    assert "SIGNAL_A" in res
    assert res["SIGNAL_A"]["trade_count"] == 3
    assert res["SIGNAL_A"]["lifecycle_recommendation"] == "WATCH"
    assert res["SIGNAL_A"]["rank"] == "WATCHLIST"

def test_winning_strategy_group():
    mock_ledger = MagicMock()
    t_win = TradeOutcome("1", "FX", "EUR_USD", "", "", 0.0, "SIGNAL_A", "", 1.0, 1.1, 1.0, 10.0, 0.0, 0.0, "WIN")
    # 5 trades -> >= 5, lifecycle recommendation should promote
    mock_ledger.list_trades.return_value = [t_win] * 5
    
    engine = StrategyRankingEngine(ledger=mock_ledger)
    res = engine.rank_by_entry_reason()
    
    assert "SIGNAL_A" in res
    assert res["SIGNAL_A"]["trade_count"] == 5
    assert res["SIGNAL_A"]["lifecycle_recommendation"] == "PROMOTE"
    assert res["SIGNAL_A"]["rank"] == "PROMOTE_CANDIDATE"

def test_losing_strategy_group():
    mock_ledger = MagicMock()
    t_loss = TradeOutcome("1", "FX", "EUR_USD", "", "", 0.0, "SIGNAL_A", "", 1.0, 0.9, 1.0, -10.0, 0.0, 0.0, "LOSS")
    mock_ledger.list_trades.return_value = [t_loss] * 5
    
    engine = StrategyRankingEngine(ledger=mock_ledger)
    res = engine.rank_by_entry_reason()
    
    assert "SIGNAL_A" in res
    assert res["SIGNAL_A"]["trade_count"] == 5
    assert res["SIGNAL_A"]["lifecycle_recommendation"] == "DEMOTE"
    assert res["SIGNAL_A"]["rank"] == "DEMOTE_CANDIDATE"

def test_mixed_asset_class_ranking():
    mock_ledger = MagicMock()
    t_fx = TradeOutcome("1", "FX", "EUR_USD", "", "", 0.0, "SIGNAL_A", "", 1.0, 1.1, 1.0, 10.0, 0.0, 0.0, "WIN")
    t_crypto = TradeOutcome("2", "CRYPTO", "BTC_USD", "", "", 0.0, "SIGNAL_A", "", 50000.0, 49000.0, 1.0, -1000.0, 0.0, 0.0, "LOSS")
    
    # 5 FX, 5 Crypto
    mock_ledger.list_trades.return_value = [t_fx]*5 + [t_crypto]*5
    
    engine = StrategyRankingEngine(ledger=mock_ledger)
    res = engine.rank_by_asset_class()
    
    assert "FX" in res
    assert res["FX"]["rank"] == "PROMOTE_CANDIDATE"
    
    assert "CRYPTO" in res
    assert res["CRYPTO"]["rank"] == "DEMOTE_CANDIDATE"

def test_failsafe():
    mock_ledger = MagicMock()
    mock_ledger.list_trades.side_effect = Exception("Disk error")
    
    engine = StrategyRankingEngine(ledger=mock_ledger)
    res = engine.summarize_rankings()
    
    assert res == {
        "by_entry_reason": {},
        "by_asset_class": {},
        "by_symbol": {}
    }
