from __future__ import annotations

from backend.validation.marathon_certifier import MarathonCertifier
from backend.validation.marathon_checklist import MarathonCheckResult, MarathonChecklist
from backend.validation.marathon_report import build_marathon_readiness_report
from backend.validation.marathon_snapshot import MarathonSnapshot
from backend.validation.marathon_statistics import build_marathon_statistics


def _readiness(status: str = "GO"):
    if status == "GO":
        results = [MarathonCheckResult(check_name="repository_clean", passed=True)]
    else:
        results = [MarathonCheckResult(check_name="repository_clean", passed=False, message="dirty")]
    return build_marathon_readiness_report(MarathonChecklist(results=tuple(results)))


def _snapshot() -> MarathonSnapshot:
    return MarathonSnapshot(
        timestamp="2026-06-24T12:00:00+00:00",
        uptime_seconds=1.0,
        cycle_number=1,
        paper_balance=100000.0,
        equity=100010.0,
        realized_pnl=1.0,
        unrealized_pnl=0.5,
        approved_trades=1,
        blocked_trades=0,
        open_positions=1,
        alerts=1,
        recoveries=0,
        heartbeat_status="OK",
        decision="ALLOW",
        selected_strategy="alpha",
        market_regime="TRENDING",
        portfolio_exposure=1000.0,
        cycle_duration_seconds=0.2,
        drawdown=0.0,
    )


def test_certification_go() -> None:
    certifier = MarathonCertifier()
    snapshot = _snapshot()
    statistics = build_marathon_statistics([snapshot])

    report = certifier.certify(
        start_time="2026-06-24T12:00:00+00:00",
        end_time="2026-06-24T12:10:00+00:00",
        elapsed_time_seconds=600.0,
        snapshots=[snapshot],
        statistics=statistics,
        readiness_report=_readiness("GO"),
        stop_reason=None,
        replay_summary={"number_of_candidates": 1},
    )

    assert report.go_no_go == "GO"
    assert report.certification_status == "GO"
    assert report.cycles_completed == 1
    assert report.health_summary["readiness_status"] == "GO"


def test_certification_conditional_go() -> None:
    certifier = MarathonCertifier()
    snapshot = _snapshot()
    statistics = build_marathon_statistics([snapshot])

    readiness = build_marathon_readiness_report(
        MarathonChecklist(
            results=(
                MarathonCheckResult(check_name="repository_clean", passed=True),
                MarathonCheckResult(check_name="paper_mode_configured", passed=True, warning=True, message="practice mode"),
            )
        )
    )

    report = certifier.certify(
        start_time="2026-06-24T12:00:00+00:00",
        end_time="2026-06-24T12:10:00+00:00",
        elapsed_time_seconds=600.0,
        snapshots=[snapshot],
        statistics=statistics,
        readiness_report=readiness,
        stop_reason=None,
        replay_summary={"number_of_candidates": 1},
    )

    assert report.go_no_go == "CONDITIONAL_GO"


def test_certification_no_go() -> None:
    certifier = MarathonCertifier()
    snapshot = _snapshot()
    statistics = build_marathon_statistics([snapshot])

    report = certifier.certify(
        start_time="2026-06-24T12:00:00+00:00",
        end_time="2026-06-24T12:10:00+00:00",
        elapsed_time_seconds=600.0,
        snapshots=[snapshot],
        statistics=statistics,
        readiness_report=_readiness("NO_GO"),
        stop_reason="runtime_unhealthy",
        replay_summary={"number_of_candidates": 1},
    )

    assert report.go_no_go == "NO_GO"
    assert report.health_summary["stop_reason"] == "runtime_unhealthy"
