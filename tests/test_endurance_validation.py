from __future__ import annotations

from copy import deepcopy

import pytest

from backend.validation.endurance_validation import EnduranceValidationEngine, EnduranceValidationError


def _healthy_evidence() -> dict:
    return {
        "cycle_count": 48,
        "runtime_duration_seconds": 172800.0,
        "uptime_pct": 0.99,
        "alerts": [],
        "recovery_events": [],
        "restart_events": [],
        "memory_growth_metric": 0.05,
        "max_drawdown": 0.04,
        "paper_mode_enabled": True,
        "checkpoints": [{"cycle": 24}, {"cycle": 48}],
        "resume_supported": True,
        "runtime_status": "HEALTHY",
        "heartbeat_status": "OK",
    }


def test_endurance_validation_passes_clean_long_run_evidence() -> None:
    engine = EnduranceValidationEngine(
        minimum_cycles=48,
        minimum_runtime_seconds=172800.0,
    )

    result = engine.validate(_healthy_evidence())

    assert result.status == "PASS"
    assert result.go_no_go == "GO"
    assert result.readiness_score == 100.0
    assert result.critical_findings == ()
    assert result.warnings == ()
    assert result.metrics["cycle_count"] == 48


def test_endurance_validation_warns_on_degraded_but_noncritical_evidence() -> None:
    evidence = _healthy_evidence()
    evidence["uptime_pct"] = 0.92
    evidence["alerts"] = [{"severity": "WARNING"}] * 8
    evidence["memory_growth_metric"] = 0.25

    engine = EnduranceValidationEngine(
        minimum_cycles=48,
        minimum_runtime_seconds=172800.0,
    )
    result = engine.validate(evidence)

    assert result.status == "WARNING"
    assert result.go_no_go == "CONDITIONAL_GO"
    assert "uptime_below_target" in result.warnings
    assert "alert_rate_above_target" not in result.critical_findings
    assert result.readiness_score < 100.0


def test_endurance_validation_fails_missing_runtime_or_paper_mode() -> None:
    evidence = _healthy_evidence()
    evidence["cycle_count"] = 2
    evidence["runtime_duration_seconds"] = 3600.0
    evidence["paper_mode_enabled"] = False
    evidence["stop_reason"] = "runtime_unhealthy"
    evidence["runtime_status"] = "CRITICAL"

    engine = EnduranceValidationEngine(
        minimum_cycles=48,
        minimum_runtime_seconds=172800.0,
    )
    result = engine.validate(evidence)

    assert result.status == "FAIL"
    assert result.go_no_go == "NO_GO"
    assert "minimum_cycles_not_met" in result.critical_findings
    assert "paper_mode_disabled" in result.critical_findings
    assert "runtime_unhealthy" in result.critical_findings


def test_endurance_validation_is_read_only() -> None:
    evidence = _healthy_evidence()
    before = deepcopy(evidence)

    EnduranceValidationEngine().validate(evidence)

    assert evidence == before


def test_endurance_validation_rejects_non_mapping_input() -> None:
    with pytest.raises(EnduranceValidationError):
        EnduranceValidationEngine().validate(["not", "mapping"])
