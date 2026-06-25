from __future__ import annotations

from backend.analytics.opportunity_cost_engine import OpportunityCostEngine


def test_opportunity_cost_for_rejected_trade() -> None:
    report = OpportunityCostEngine().analyze_rejected_trades([
        {"trade_id": "t1", "rejection_reason": "LOW_CONFIDENCE", "confidence": 0.4, "expected_pnl": 15.0, "realized_pnl": 16.0},
        {"trade_id": "t2", "rejection_reason": "BAD_REGIME", "confidence": 0.7, "expected_pnl": -2.0, "realized_pnl": -2.0},
    ])

    assert report["summary"]["rejected_trade_count"] == 2
    assert report["opportunity_costs"][0]["threshold_implication"] == "relax_acceptance_threshold"
