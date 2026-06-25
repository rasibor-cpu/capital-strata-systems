from __future__ import annotations

from backend.validation.marathon_summary_report import MarathonSummaryReport


def test_summary_report_deterministic() -> None:
    report = MarathonSummaryReport().build_report(
        marathon_evidence={"cycle_count": 2, "runtime_duration_seconds": 120.0, "trade_statistics": {"trade_count": 4}, "capital_curve": [100000.0, 100020.0], "drawdown_history": [0.0, 2.0]},
        health_summary={"status": "HEALTHY"},
        runtime_statistics={"uptime_pct": 0.98, "average_cycle_duration_seconds": 60.0, "restart_count": 1, "trade_frequency": 0.03, "average_runtime_latency_seconds": 0.4, "average_decision_latency_seconds": 0.2},
        certification_summary={"status": "PASS"},
        trade_forensics=[{"trade_id": "t1"}],
        attribution={"strategy": []},
        strategy_league_table=[{"strategy_id": "alpha", "grade": "GOLD"}],
        opportunity_cost={"summary": {}},
        improvement_recommendations=[{"action": "increase allocation"}],
    )

    assert report["runtime_summary"]["cycle_count"] == 2
    assert report["certification_summary"]["status"] == "PASS"
    assert report["unified_operational_report"]["recommendations"][0]["action"] == "increase allocation"
