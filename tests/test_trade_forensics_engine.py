from __future__ import annotations

from backend.analytics.trade_forensics_engine import TradeForensicsEngine


def test_trade_forensic_explanation() -> None:
    explanation = TradeForensicsEngine().explain_trade({
        "trade_id": "t1",
        "strategy_id": "alpha",
        "market_regime": "TRENDING",
        "confidence": 0.8,
        "quality_score": 88.0,
        "position_size": 1000.0,
        "capital_allocation": 2000.0,
        "holding_time_seconds": 1800.0,
        "realized_pnl": 12.5,
        "expected_pnl": 10.0,
        "entry_reason": "trend alignment",
        "exit_reason": "take_profit",
    })

    assert explanation["decision_optimal"] is True
    assert explanation["trade_quality"] == "A"
    assert explanation["entry_reason"] == "trend alignment"
