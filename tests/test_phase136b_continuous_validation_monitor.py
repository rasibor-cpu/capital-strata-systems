from pathlib import Path

from backend.monitoring.runtime_health_aggregator import RuntimeHealthAggregator
from backend.validation.continuous_validation_monitor import ContinuousValidationMonitor


def test_continuous_validation_monitor_green_and_persists(tmp_path: Path) -> None:
    result = ContinuousValidationMonitor(artifacts_dir=tmp_path).evaluate(
        runtime_health={"runtime_health": "GREEN"},
        validation_readiness={"readiness_status": "READY"},
        session_continuity={"session_continuity_status": "ACTIVE"},
        artifact_freshness={"freshness_status": "GREEN"},
        supervisor_state={"status": "RUNNING"},
        portfolio_lifecycle={"portfolio_state": "NO_PORTFOLIO"},
        portfolio_decision={"overall_status": "GREEN"},
        advisory_snapshot={"snapshot_status": "OK"},
        persist=True,
    )

    assert result["validation_state"] == "GREEN"
    assert (tmp_path / "runtime_validation_monitor.json").exists()
    assert result["execution_allowed"] is False


def test_continuous_validation_monitor_red_on_reauth_required() -> None:
    result = ContinuousValidationMonitor().evaluate(
        runtime_health={"runtime_health": "GREEN"},
        validation_readiness={"readiness_status": "READY_WITH_CAUTION"},
        session_continuity={"session_continuity_status": "REAUTH_REQUIRED", "warnings": ["session_expired"]},
        artifact_freshness={"freshness_status": "GREEN"},
        supervisor_state={"status": "RUNNING"},
        portfolio_lifecycle={"portfolio_state": "NO_PORTFOLIO"},
        portfolio_decision={"overall_status": "GREEN"},
        advisory_snapshot={"snapshot_status": "OK"},
    )

    assert result["validation_state"] == "RED"
    assert "session_expired" in result["warnings"]


def test_runtime_health_aggregator_consumes_canonical_artifacts() -> None:
    result = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "GREEN"},
        session_validation={"session_status": "GREEN"},
        supervisor_status={"status": "RUNNING"},
        canonical_artifacts={
            "runtime_portfolio_state": {"status": "OK", "portfolio_state": "NO_PORTFOLIO"},
            "portfolio_decision": {"overall_status": "GREEN"},
            "artifact_freshness": {"freshness_status": "GREEN", "artifacts": {}},
            "session_continuity": {"session_continuity_status": "ACTIVE"},
        },
    )

    assert result["status"] == "OK"
    assert result["portfolio_lifecycle_state"] == "NO_PORTFOLIO"
    assert result["execution_allowed"] is False
