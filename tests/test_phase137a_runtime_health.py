from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.monitoring.runtime_health_aggregator import RuntimeHealthAggregator
from backend.runtime.runtime_artifact_freshness import RuntimeArtifactFreshnessManager


def test_phase137a_runtime_health_clears_stale_account_after_refresh() -> None:
    result = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "GREEN"},
        session_validation={"session_status": "GREEN", "heartbeat_age": 1},
        supervisor_status={"status": "RUNNING"},
        portfolio_decision={"overall_status": "GREEN"},
        runtime_portfolio_state={
            "status": "OK",
            "portfolio_state": "NO_PORTFOLIO",
            "staleness": {"account_state": {"stale": True}},
        },
        artifact_freshness={
            "freshness_status": "GREEN",
            "warnings": [],
            "artifacts": {"account_state": {"status": "FRESH", "exists": True}},
        },
        session_continuity={"session_continuity_status": "ACTIVE", "warnings": []},
    )

    assert result["runtime_health"] == "GREEN"
    assert "stale_account_state" not in result["warnings"]
    assert result["execution_allowed"] is False


def test_phase137a_runtime_health_stays_amber_for_aging_required_artifact(tmp_path: Path) -> None:
    account = tmp_path / "css_account_state_pcnrass.json"
    session = tmp_path / "css_session_state_pcnrass.json"
    supervisor = tmp_path / "supervisor.json"
    account.write_text("{}", encoding="utf-8")
    session.write_text('{"session":{"engine_mode":"PAPER"}}', encoding="utf-8")
    supervisor.write_text('{"status":"RUNNING"}', encoding="utf-8")
    old = (datetime.now(timezone.utc) - timedelta(seconds=75)).timestamp()
    import os

    os.utime(account, (old, old))

    freshness = RuntimeArtifactFreshnessManager(
        artifacts_dir=tmp_path,
        supervisor_state_path=supervisor,
        thresholds={"account_state": 100},
    ).evaluate(runtime_active=True)

    assert freshness["artifacts"]["account_state"]["status"] == "AGING"
    result = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "GREEN"},
        session_validation={"session_status": "GREEN"},
        supervisor_status={"status": "RUNNING"},
        portfolio_decision={"overall_status": "GREEN"},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "NO_PORTFOLIO"},
        artifact_freshness=freshness,
        session_continuity={"session_continuity_status": "ACTIVE"},
    )
    assert result["runtime_health"] == "AMBER"


def test_phase137a_artifact_freshness_exposes_portfolio_state_alias(tmp_path: Path) -> None:
    (tmp_path / "runtime_portfolio_state.json").write_text("{}", encoding="utf-8")

    result = RuntimeArtifactFreshnessManager(artifacts_dir=tmp_path).evaluate(runtime_active=False)

    assert "portfolio_state" in result["artifacts"]
    assert result["artifacts"]["portfolio_state"]["status"] == result["artifacts"]["runtime_portfolio_state"]["status"]
