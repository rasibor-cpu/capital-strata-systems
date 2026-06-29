from __future__ import annotations

from backend.validation.rc1_readiness import RC1ReadinessEvaluator


def _endurance_evidence() -> dict:
    return {
        "cycle_count": 48,
        "runtime_duration_seconds": 172800.0,
        "uptime_pct": 0.99,
        "alerts": [],
        "recovery_events": [],
        "restart_events": [],
        "memory_growth_metric": 0.04,
        "max_drawdown": 0.05,
        "paper_mode_enabled": True,
        "checkpoints": [{"cycle": 48}],
        "resume_supported": True,
        "runtime_status": "HEALTHY",
        "heartbeat_status": "OK",
    }


def test_rc1_readiness_passes_with_clean_validation_bundle() -> None:
    result = RC1ReadinessEvaluator().evaluate(
        endurance_evidence=_endurance_evidence(),
        certification_result={"certification_status": "PASS"},
        optimization_result={"advisory_only": True, "execution_allowed": False},
        regression_result={"passed": True},
    )

    assert result.status == "PASS"
    assert result.go_no_go == "GO"
    assert result.critical_findings == ()
    assert "certification_passed" in result.informational_findings
    assert "optimization_advisory_only" in result.informational_findings
    assert "regression_tests_passed" in result.informational_findings


def test_rc1_readiness_returns_conditional_go_for_certification_warning() -> None:
    result = RC1ReadinessEvaluator().evaluate(
        endurance_evidence=_endurance_evidence(),
        certification_result={"certification_status": "WARNING"},
        optimization_result={"advisory_only": True, "execution_allowed": False},
        regression_result={"passed": True},
    )

    assert result.status == "WARNING"
    assert result.go_no_go == "CONDITIONAL_GO"
    assert "certification_has_warnings" in result.warnings


def test_rc1_readiness_blocks_non_advisory_optimization() -> None:
    result = RC1ReadinessEvaluator().evaluate(
        endurance_evidence=_endurance_evidence(),
        certification_result={"certification_status": "PASS"},
        optimization_result={"advisory_only": False, "execution_allowed": True},
        regression_result={"passed": True},
    )

    assert result.status == "FAIL"
    assert result.go_no_go == "NO_GO"
    assert "optimization_not_advisory_only" in result.critical_findings


def test_rc1_readiness_blocks_failed_regression_or_endurance() -> None:
    evidence = _endurance_evidence()
    evidence["paper_mode_enabled"] = False

    result = RC1ReadinessEvaluator().evaluate(
        endurance_evidence=evidence,
        certification_result={"certification_status": "PASS"},
        optimization_result={"advisory_only": True, "execution_allowed": False},
        regression_result={"passed": False},
    )

    assert result.status == "FAIL"
    assert "paper_mode_disabled" in result.critical_findings
    assert "regression_tests_not_passed" in result.critical_findings


def test_rc1_readiness_is_validation_only() -> None:
    evaluator = RC1ReadinessEvaluator()
    exposed_names = [name.lower() for name in dir(evaluator) + dir(RC1ReadinessEvaluator)]
    forbidden_terms = (
        "submit_order",
        "execute_trade",
        "broker",
        "runtime_supervisor",
        "unified_trade_gate",
        "capital_governor",
    )

    assert not any(
        forbidden in exposed_name
        for forbidden in forbidden_terms
        for exposed_name in exposed_names
    )
