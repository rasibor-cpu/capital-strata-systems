from backend.analytics import CostRealityEngine, SignalQualityEngine, TradeOutcomeAnalyticsEngine


def test_analytics_engines_smoke() -> None:
    trades = [
        {"pnl": 100.0, "is_closed": True, "opened_at": "2026-05-25T10:00:00Z", "closed_at": "2026-05-25T11:00:00Z", "notional": 10000, "spread_bps": 1.0, "slippage_bps": 0.5, "commission": 2.0},
        {"pnl": -40.0, "is_closed": True, "opened_at": "2026-05-25T12:00:00Z", "closed_at": "2026-05-25T12:30:00Z", "notional": 8000, "spread_bps": 1.2, "slippage_bps": 0.8, "commission": 2.0},
    ]
    signals = [
        {"score": 0.8, "confidence": 0.9, "regime_alignment": 0.7, "persistence": 0.6, "is_false_positive": False},
        {"score": 0.4, "confidence": 0.5, "regime_alignment": 0.3, "persistence": 0.2, "is_false_positive": True},
    ]

    trade_payload = TradeOutcomeAnalyticsEngine().build(trades)
    cost_payload = CostRealityEngine().build(trades)
    signal_payload = SignalQualityEngine().build(signals)

    assert trade_payload["trade_count"] == 2
    assert trade_payload["profit_factor"] > 0.0
    assert "cost_adjusted_profitability" in cost_payload
    assert signal_payload["signal_count"] == 2
