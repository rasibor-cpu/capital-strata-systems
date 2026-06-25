from __future__ import annotations

from backend.validation.marathon_certification_engine import MarathonCertificationEngine


def test_certification_pass() -> None:
    engine = MarathonCertificationEngine()
    result = engine.certify(
        {"cycle_count": 4, "runtime_duration_seconds": 400.0, "max_drawdown": 0.1},
        health_summary={"status": "HEALTHY"},
        runtime_statistics={"uptime_pct": 0.99, "alert_rate": 0.05, "recovery_rate": 0.05, "trade_count": 8},
    )

    assert result["status"] == "PASS"


def test_certification_pass_with_warnings() -> None:
    engine = MarathonCertificationEngine()
    result = engine.certify(
        {"cycle_count": 4, "runtime_duration_seconds": 400.0, "max_drawdown": 0.1},
        health_summary={"status": "WARNING"},
        runtime_statistics={"uptime_pct": 0.9, "alert_rate": 0.15, "recovery_rate": 0.15, "trade_count": 8},
    )

    assert result["status"] == "PASS_WITH_WARNINGS"


def test_certification_fail() -> None:
    engine = MarathonCertificationEngine()
    result = engine.certify(
        {"cycle_count": 0, "runtime_duration_seconds": 0.0, "max_drawdown": 0.5},
        health_summary={"status": "CRITICAL"},
        runtime_statistics={"uptime_pct": 0.1, "alert_rate": 0.9, "recovery_rate": 0.9, "trade_count": 0},
    )

    assert result["status"] == "FAIL"
