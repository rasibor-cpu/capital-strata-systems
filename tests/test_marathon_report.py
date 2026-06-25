from __future__ import annotations

from backend.validation.marathon_checklist import MarathonCheckResult, MarathonChecklist
from backend.validation.marathon_report import build_marathon_readiness_report


def test_report_from_checklist() -> None:
    checklist = MarathonChecklist(
        results=(
            MarathonCheckResult(check_name="repository_clean", passed=True),
            MarathonCheckResult(check_name="paper_mode_configured", passed=True, warning=True, message="practice mode"),
            MarathonCheckResult(check_name="replay_engine_available", passed=True),
        )
    )

    report = build_marathon_readiness_report(checklist)

    assert report.overall_status == "GO"
    assert report.go_no_go == "GO"
    assert report.checks_passed == ("repository_clean", "paper_mode_configured", "replay_engine_available")
    assert report.warnings == ("practice mode",)


def test_report_failure_state() -> None:
    checklist = MarathonChecklist(
        results=(
            MarathonCheckResult(check_name="repository_clean", passed=False, message="dirty"),
            MarathonCheckResult(check_name="replay_engine_available", passed=True),
        )
    )

    report = build_marathon_readiness_report(checklist)

    assert report.overall_status == "NO_GO"
    assert report.go_no_go == "NO_GO"
    assert report.checks_failed == ("repository_clean",)
