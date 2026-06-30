import json
from pathlib import Path

from backend.runtime.runtime_artifact_publisher import RuntimeArtifactPublisher


def _runtime_state() -> dict:
    return {
        "status": "OK",
        "portfolio_state": "NO_PORTFOLIO",
        "account": {"equity": 10000, "cash": 9000, "buying_power": 9000, "realized_pnl": 0, "open_pnl": 0, "total_pnl": 0},
        "positions": [],
        "trades": [],
        "asset_allocations": {},
        "advisory_only": True,
        "execution_allowed": False,
    }


def test_runtime_artifact_publisher_writes_canonical_artifacts(tmp_path: Path) -> None:
    result = RuntimeArtifactPublisher(artifacts_dir=tmp_path).publish(
        runtime_cycle=7,
        runtime_portfolio_state=_runtime_state(),
        runtime_advisory_snapshot={"snapshot_status": "OK"},
        portfolio_decision={"overall_status": "GREEN", "portfolio_recommendation": "MAINTAIN"},
        validation_summary={"readiness_status": "READY"},
        timestamp="2026-06-30T12:00:00+00:00",
    )

    assert result["status"] == "OK"
    for filename in (
        "css_account_state_pcnrass.json",
        "runtime_portfolio_state.json",
        "runtime_advisory_snapshot.json",
        "portfolio_snapshot.json",
        "portfolio_decision.json",
        "validation_summary.json",
    ):
        payload = json.loads((tmp_path / filename).read_text(encoding="utf-8"))
        assert payload["runtime_cycle"] == 7
        assert payload["schema_version"] == "136A.1"
        assert payload["source_module"] == "RuntimeArtifactPublisher"
        assert payload["advisory_only"] is True
        assert payload["execution_allowed"] is False


def test_runtime_artifact_publisher_fails_closed_when_inputs_missing(tmp_path: Path) -> None:
    result = RuntimeArtifactPublisher(artifacts_dir=tmp_path).publish(runtime_cycle=1)

    assert result["status"] == "OK"
    decision = json.loads((tmp_path / "portfolio_decision.json").read_text(encoding="utf-8"))
    assert decision["status"] == "DATA UNAVAILABLE"
    assert decision["execution_allowed"] is False
