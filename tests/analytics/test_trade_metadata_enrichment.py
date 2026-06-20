import pytest
import json
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch
from backend.app.persistence.services.trade_runtime_service import TradeRuntimeService
from analytics.trade_outcome_ledger import TradeOutcome

def test_trade_metadata_enrichment_inference():
    svc = TradeRuntimeService()
    payload = json.dumps({"reason": "TEST", "asset_class": "UNKNOWN", "engine_mode": "SAFE"})
    mock_trade_record = {
        "symbol": "BTC-USD",
        "direction": "LONG",
        "entry_price": 60000.00,
        "quantity": 0.5,
        "broker_mode": "PAPER",
        "raw_payload_json": payload,
        "session_id": "session_1"
    }
    
    with patch("analytics.trade_outcome_ledger.TradeOutcomeLedger.append_trade") as mock_append:
        with patch.object(svc.persistence.trades, "get_trade", return_value=mock_trade_record):
            with patch.object(svc.persistence.trades, "close_trade"):
                svc.close_trade(
                    trade_id="trade_1",
                    exit_price=Decimal("61000.00"),
                    realized_pnl=Decimal("500.00")
                )
    
    assert mock_append.call_count == 1
    trade = mock_append.call_args[0][0]
    assert trade.trade_id == "trade_1"
    assert trade.asset_class == "CRYPTO" # inferred from BTC
    assert trade.side == "BUY" # inferred from LONG
    assert trade.amount_traded == 30000.00 # 60000 * 0.5
    assert trade.broker_mode == "PAPER"
    assert trade.engine_mode == "SAFE"

def test_trade_metadata_options_inference():
    svc = TradeRuntimeService()
    mock_trade_record = {
        "symbol": "SPY-20261231-C-500",
        "direction": "SHORT",
        "entry_price": 5.00,
        "quantity": 10.0,
        "broker_mode": "PAPER",
    }
    
    with patch("analytics.trade_outcome_ledger.TradeOutcomeLedger.append_trade") as mock_append:
        with patch.object(svc.persistence.trades, "get_trade", return_value=mock_trade_record):
            with patch.object(svc.persistence.trades, "close_trade"):
                svc.close_trade(
                    trade_id="trade_2",
                    exit_price=Decimal("4.00"),
                    realized_pnl=Decimal("10.00")
                )
    
    assert mock_append.call_count == 1
    trade = mock_append.call_args[0][0]
    assert trade.trade_id == "trade_2"
    assert trade.asset_class == "OPTIONS" # inferred from -C-
    assert trade.side == "SELL" # inferred from SHORT
    assert trade.amount_traded == 50.00 # 5 * 10




