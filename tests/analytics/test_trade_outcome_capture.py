import json
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime

from backend.app.persistence.services.trade_runtime_service import TradeRuntimeService
from analytics.trade_outcome_ledger import TradeOutcomeLedger


@pytest.fixture
def mock_persistence():
    with patch("backend.app.persistence.services.trade_runtime_service.PersistenceService") as mock:
        yield mock

@pytest.fixture
def temp_ledger(tmp_path):
    ledger_path = tmp_path / "trade_outcomes.json"
    return ledger_path

def test_paper_close_captured(mock_persistence, temp_ledger):
    # Setup mock persistence to return a mock trade
    mock_instance = mock_persistence.return_value
    mock_instance.trades.get_trade.return_value = {
        "trade_id": "T1",
        "symbol": "EUR_USD",
        "opened_at": "2026-06-19T10:00:00Z",
        "entry_price": "1.1000",
        "quantity": "1000",
        "raw_payload_json": '{"reason": "SIGNAL", "asset_class": "FX"}'
    }
    
    with patch("analytics.trade_outcome_ledger.TradeOutcomeLedger.__init__", return_value=None), \
         patch("analytics.trade_outcome_ledger.TradeOutcomeLedger.append_trade") as mock_append:
         
        service = TradeRuntimeService()
        service.persistence = mock_instance
        with patch.object(
            service.canonical_lifecycle,
            "persist_closed_trade_outcome",
            return_value={"trade_id": "T1"},
        ):
            service.close_trade(
                trade_id="T1",
                exit_price=Decimal("1.1050"),
                realized_pnl=Decimal("5.0")
            )
        
        # Verify persistence close was called
        mock_instance.trades.close_trade.assert_called_once()
        
        # Verify ledger append was called
        mock_append.assert_called_once()
        outcome = mock_append.call_args[0][0]
        assert outcome.trade_id == "T1"
        assert outcome.asset_class == "FX"
        assert outcome.symbol == "EUR_USD"
        assert outcome.entry_reason == "SIGNAL"
        assert outcome.realized_pnl == 5.0
        assert outcome.win_loss == "WIN"
        assert outcome.exit_reason == "ACCOUNTING_CLOSE"

def test_winning_and_losing_trades_captured(mock_persistence):
    mock_instance = mock_persistence.return_value
    mock_instance.trades.get_trade.return_value = {
        "trade_id": "T2",
        "symbol": "AAPL",
        "opened_at": "2026-06-19T10:00:00Z",
        "entry_price": "150.0",
        "quantity": "10",
    }
    
    with patch("analytics.trade_outcome_ledger.TradeOutcomeLedger.__init__", return_value=None), \
         patch("analytics.trade_outcome_ledger.TradeOutcomeLedger.append_trade") as mock_append:
         
        service = TradeRuntimeService()
        service.persistence = mock_instance
        with patch.object(
            service.canonical_lifecycle,
            "persist_closed_trade_outcome",
            return_value={"trade_id": "ok"},
        ):
            # Losing trade
            service.close_trade(
                trade_id="T2",
                exit_price=Decimal("140.0"),
                realized_pnl=Decimal("-100.0")
            )
            
            outcome_loss = mock_append.call_args[0][0]
            assert outcome_loss.win_loss == "LOSS"
            assert outcome_loss.realized_pnl == -100.0
            
            # Winning trade
            service.close_trade(
                trade_id="T3",
                exit_price=Decimal("160.0"),
                realized_pnl=Decimal("100.0")
            )
            
            outcome_win = mock_append.call_args[0][0]
            assert outcome_win.win_loss == "WIN"
            assert outcome_win.realized_pnl == 100.0

def test_analytics_failure_does_not_interrupt_close_processing(mock_persistence):
    mock_instance = mock_persistence.return_value
    mock_instance.trades.get_trade.side_effect = Exception("Database is on fire")
    
    with patch("analytics.trade_outcome_ledger.TradeOutcomeLedger.append_trade") as mock_append:
        service = TradeRuntimeService()
        service.persistence = mock_instance
        
        # This should not raise an exception, failure is caught and logged
        service.close_trade(
            trade_id="T4",
            exit_price=Decimal("1.0"),
            realized_pnl=Decimal("0.0")
        )
        
        # Original close logic still executed
        mock_instance.trades.close_trade.assert_called_once()
        
        # Ledger was bypassed
        mock_append.assert_not_called()
