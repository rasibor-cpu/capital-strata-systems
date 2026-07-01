import json
from pathlib import Path

from backend.runtime.runtime_artifact_publisher import RuntimeArtifactPublisher


def test_phase137a_publisher_refreshes_session_and_metadata(tmp_path: Path) -> None:
    result = RuntimeArtifactPublisher(artifacts_dir=tmp_path).publish(
        runtime_cycle=42,
        account_state={"account_balance": 250.0, "session_id": "session-137"},
        session_state={"session": {"session_id": "session-137", "engine_mode": "PAPER"}},
        runtime_portfolio_state={"status": "OK", "portfolio_state": "NO_PORTFOLIO", "account": {}, "positions": []},
        runtime_advisory_snapshot={"snapshot_status": "OK"},
        portfolio_decision={"overall_status": "GREEN", "portfolio_recommendation": "MAINTAIN"},
        validation_summary={"status": "OK", "readiness_status": "READY"},
        runtime_version="137A-test",
        timestamp="2026-06-30T15:00:00+00:00",
    )

    assert result["status"] == "OK"
    for filename in (
        "css_account_state_pcnrass.json",
        "css_session_state_pcnrass.json",
        "runtime_portfolio_state.json",
        "runtime_advisory_snapshot.json",
        "portfolio_snapshot.json",
        "portfolio_decision.json",
        "validation_summary.json",
    ):
        payload = json.loads((tmp_path / filename).read_text(encoding="utf-8"))
        assert payload["generated_at"] == "2026-06-30T15:00:00+00:00"
        assert payload["runtime_cycle"] == 42
        assert payload["session_id"] == "session-137"
        assert payload["runtime_version"] == "137A-test"
        assert payload["advisory_only"] is True
        assert payload["execution_allowed"] is False


def test_phase137a_runtime_loop_invokes_publisher_after_cycle_accounting() -> None:
    source = Path("scripts/css_live_dashboard.py").read_text(encoding="utf-8")

    assert "from backend.runtime.runtime_artifact_publisher import RuntimeArtifactPublisher" in source
    assert "def pcnrass_publish_runtime_artifacts" in source
    assert "publish_result = pcnrass_publish_runtime_artifacts" in source
    assert source.index("runtime_supervisor.record_cycle") < source.index("publish_result = pcnrass_publish_runtime_artifacts")


def test_phase137a_publisher_fail_closed_when_write_fails(tmp_path: Path) -> None:
    blocked_path = tmp_path / "not_a_directory"
    blocked_path.write_text("blocked", encoding="utf-8")

    result = RuntimeArtifactPublisher(artifacts_dir=blocked_path).publish(runtime_cycle=1)

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False
    assert any("write_failed_" in warning for warning in result["warnings"])
