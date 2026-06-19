import json
import pytest
from pathlib import Path
from analytics.trade_outcome_ledger import TradeOutcomeLedger, TradeOutcome

@pytest.fixture
def temp_ledger_file(tmp_path):
    return tmp_path / "trade_outcomes.json"

@pytest.fixture
def ledger(temp_ledger_file):
    return TradeOutcomeLedger(file_path=temp_ledger_file)

def test_empty_ledger_works(ledger):
    assert ledger.list_trades() == []
    summary = ledger.summarize()
    assert summary["total_trades"] == 0
    assert summary["win_rate"] == 0.0

def test_append_trade_works(ledger):
    outcome = TradeOutcome(
        trade_id="T001",
        asset_class="FX",
        symbol="EUR_USD",
        entry_timestamp="2026-06-19T10:00:00Z",
        exit_timestamp="2026-06-19T10:15:00Z",
        holding_seconds=900.0,
        entry_reason="R14F",
        exit_reason="R15B",
        entry_price=1.1000,
        exit_price=1.1020,
        quantity=1000.0,
        realized_pnl=2.0,
        max_favorable_excursion=0.0025,
        max_adverse_excursion=-0.0005,
        win_loss="WIN"
    )
    ledger.append_trade(outcome)
    
    trades = ledger.list_trades()
    assert len(trades) == 1
    assert trades[0].trade_id == "T001"
    assert trades[0].win_loss == "WIN"
    assert trades[0].realized_pnl == 2.0

def test_persistence_works(temp_ledger_file):
    ledger1 = TradeOutcomeLedger(file_path=temp_ledger_file)
    outcome = TradeOutcome(
        trade_id="T002",
        asset_class="CRYPTO",
        symbol="BTC_USD",
        entry_timestamp="2026-06-19T10:00:00Z",
        exit_timestamp="2026-06-19T11:00:00Z",
        holding_seconds=3600.0,
        entry_reason="SIGNAL",
        exit_reason="STOP",
        entry_price=50000.0,
        exit_price=49500.0,
        quantity=0.1,
        realized_pnl=-50.0,
        max_favorable_excursion=0.01,
        max_adverse_excursion=-0.01,
        win_loss="LOSS"
    )
    ledger1.append_trade(outcome)
    
    # Reload in a new instance to prove persistence
    ledger2 = TradeOutcomeLedger(file_path=temp_ledger_file)
    trades = ledger2.list_trades()
    assert len(trades) == 1
    assert trades[0].trade_id == "T002"

def test_corrupt_file_fails_safe(temp_ledger_file):
    # Write invalid JSON
    temp_ledger_file.write_text("{ corrupt json ", encoding="utf-8")
    
    ledger = TradeOutcomeLedger(file_path=temp_ledger_file)
    trades = ledger.list_trades()
    assert trades == []
    
    # Write unexpected JSON structure
    temp_ledger_file.write_text('{"not_an_array": true}', encoding="utf-8")
    trades = ledger.list_trades()
    assert trades == []

def test_summary_math_works(ledger):
    t1 = TradeOutcome("1", "FX", "EUR_USD", "", "", 0, "", "", 1.0, 1.1, 1, 10.0, 0, 0, "WIN")
    t2 = TradeOutcome("2", "FX", "EUR_USD", "", "", 0, "", "", 1.0, 0.9, 1, -5.0, 0, 0, "LOSS")
    t3 = TradeOutcome("3", "FX", "EUR_USD", "", "", 0, "", "", 1.0, 1.2, 1, 20.0, 0, 0, "WIN")
    
    ledger.append_trade(t1)
    ledger.append_trade(t2)
    ledger.append_trade(t3)
    
    summary = ledger.summarize()
    assert summary["total_trades"] == 3
    assert summary["winning_trades"] == 2
    assert summary["losing_trades"] == 1
    assert summary["win_rate"] == round(2/3, 4)
    assert summary["net_realized_pnl"] == 25.0
    assert summary["average_win"] == 15.0  # (10 + 20) / 2
    assert summary["average_loss"] == 5.0  # abs(-5) / 1
    assert summary["profit_factor"] == 6.0 # 30 / 5
