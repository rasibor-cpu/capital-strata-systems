from __future__ import annotations

from backend.analytics.performance_reporting_engine import PerformanceReportingEngine


def test_reporting_outputs() -> None:
    engine = PerformanceReportingEngine()
    reports = engine.build_reports(
        performance_metrics={"win_rate": 0.62, "profit_factor": 1.5, "expectancy": 1.2, "average_r": 0.9, "average_hold_time": 25.0, "max_drawdown": 0.1, "recovery_factor": 1.8},
        calibration_report={"audit_trail": [{"pressure": 0.1}]},
        trade_quality_report={"trade_quality_summary": {"t1": 88.0}},
        runtime_health_report={"runtime_healthy": True},
        recovery_report={"operational": True},
        profitability_report={"win_rate": 0.62},
        learning_report={"learning_status": "READY"},
        strategy_ranking_report={"strategy_rankings": [{"strategy_id": "alpha", "score": 1.0}]},
    )

    assert reports["certification_report"]["status"] == "GO"
    assert reports["learning_report"]["learning_status"] == "READY"
    assert reports["trade_quality_report"]["trade_quality_summary"]["t1"] == 88.0


def test_empty_reports() -> None:
    engine = PerformanceReportingEngine()
    reports = engine.build_reports(
        performance_metrics={},
        calibration_report={},
        trade_quality_report={},
        runtime_health_report={},
        recovery_report={},
        profitability_report={},
    )

    assert reports["certification_report"]["status"] == "NO_GO"
    assert reports["strategy_ranking_report"]["strategy_rankings"] == []
