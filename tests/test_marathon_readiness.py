from __future__ import annotations

from backend.validation.marathon_checklist import MarathonCheckResult, MarathonChecklist
from backend.validation.marathon_readiness import MarathonReadiness


class StaticMarathonReadiness(MarathonReadiness):
    def __init__(self, results: list[MarathonCheckResult]) -> None:
        super().__init__(check_overrides={})
        self._results = results

    def collect_check_results(self):
        return list(self._results)


def _pass(name: str) -> MarathonCheckResult:
    return MarathonCheckResult(check_name=name, passed=True, evidence={"check": name})


def _fail(name: str, message: str = "failed") -> MarathonCheckResult:
    return MarathonCheckResult(check_name=name, passed=False, message=message, evidence={"check": name})


def _warn(name: str, message: str = "warning") -> MarathonCheckResult:
    return MarathonCheckResult(check_name=name, passed=True, warning=True, message=message, evidence={"check": name})


def test_all_checks_pass() -> None:
    readiness = StaticMarathonReadiness([
        _pass("repository_clean"),
        _pass("replay_engine_available"),
        _pass("intelligence_orchestrator_available"),
        _pass("learning_pipeline_available"),
        _pass("alert_system_available"),
        _pass("recovery_manager_available"),
        _pass("notification_dispatcher_available"),
        _pass("paper_mode_configured"),
        _pass("runtime_supervisor_available"),
        _pass("portfolio_guard_available"),
        _pass("adaptive_exit_available"),
    ])

    report = readiness.certify()

    assert report.go_no_go == "GO"
    assert report.checks_failed == ()
    assert len(report.checks_passed) == 11


def test_single_failure() -> None:
    readiness = StaticMarathonReadiness([
        _pass("repository_clean"),
        _pass("replay_engine_available"),
        _fail("intelligence_orchestrator_available", "missing orchestrator"),
    ])

    report = readiness.certify()

    assert report.go_no_go == "NO_GO"
    assert report.checks_failed == ("intelligence_orchestrator_available",)
    assert any("Resolve intelligence_orchestrator_available" in item for item in report.recommendations)


def test_multiple_failures() -> None:
    readiness = StaticMarathonReadiness([
        _pass("repository_clean"),
        _fail("replay_engine_available", "missing replay"),
        _fail("adaptive_exit_available", "missing exit"),
    ])

    report = readiness.certify()

    assert report.go_no_go == "NO_GO"
    assert report.checks_failed == ("replay_engine_available", "adaptive_exit_available")
    assert len(report.recommendations) == 2


def test_warning_only_state() -> None:
    readiness = StaticMarathonReadiness([
        _pass("repository_clean"),
        _warn("paper_mode_configured", "practice environment configured"),
        _pass("replay_engine_available"),
    ])

    report = readiness.certify()

    assert report.go_no_go == "GO"
    assert report.warnings == ("practice environment configured",)
    assert report.checks_failed == ()


def test_deterministic_output() -> None:
    readiness = StaticMarathonReadiness([
        _pass("repository_clean"),
        _warn("paper_mode_configured", "practice environment configured"),
        _pass("replay_engine_available"),
    ])

    assert readiness.certify() == readiness.certify()
