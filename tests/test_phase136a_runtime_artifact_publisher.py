import json
import math
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    ("runtime_cycle", "expected_cycle"),
    [
        (7, 7),
        ("8", 8),
        ("9.0", 9),
    ],
)
def test_runtime_artifact_publisher_accepts_valid_integer_cycles(tmp_path: Path, runtime_cycle, expected_cycle) -> None:
    result = RuntimeArtifactPublisher(artifacts_dir=tmp_path).publish(
        runtime_cycle=runtime_cycle,
        runtime_portfolio_state=_runtime_state(),
        timestamp="2026-06-30T12:00:00+00:00",
    )

    assert result["status"] == "OK"
    assert result["runtime_cycle"] == expected_cycle
    assert result["runtime_cycle_status"] == "OK"
    payload = json.loads((tmp_path / "runtime_portfolio_state.json").read_text(encoding="utf-8"))
    assert payload["runtime_cycle"] == expected_cycle
    assert payload["runtime_cycle_status"] == "OK"
    assert payload["runtime_cycle_reason"] == "runtime_cycle_valid"
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False


@pytest.mark.parametrize(
    ("runtime_cycle", "expected_status", "expected_reason"),
    [
        ("NOT_REPORTED", "NOT_REPORTED", "runtime_cycle_not_reported"),
        (None, "NOT_REPORTED", "runtime_cycle_not_reported"),
        ("", "NOT_REPORTED", "runtime_cycle_empty"),
        ("abc", "UNAVAILABLE", "runtime_cycle_malformed"),
        (-1, "UNAVAILABLE", "runtime_cycle_negative"),
        (math.inf, "UNAVAILABLE", "runtime_cycle_non_finite"),
        (math.nan, "UNAVAILABLE", "runtime_cycle_non_finite"),
    ],
)
def test_runtime_artifact_publisher_fails_closed_for_unavailable_cycles(
    tmp_path: Path,
    runtime_cycle,
    expected_status: str,
    expected_reason: str,
) -> None:
    result = RuntimeArtifactPublisher(artifacts_dir=tmp_path).publish(
        runtime_cycle=runtime_cycle,
        runtime_portfolio_state=_runtime_state(),
        timestamp="2026-06-30T12:00:00+00:00",
    )

    assert result["status"] == "AMBER"
    assert result["runtime_cycle"] is None
    assert result["runtime_cycle_status"] == expected_status
    assert result["runtime_cycle_reason"] == expected_reason
    assert f"runtime_cycle_{expected_reason}" in result["warnings"]
    payload = json.loads((tmp_path / "runtime_portfolio_state.json").read_text(encoding="utf-8"))
    assert payload["runtime_cycle"] is None
    assert payload["runtime_cycle_status"] == expected_status
    assert payload["runtime_cycle_reason"] == expected_reason
    expected_source = "runtime_session" if runtime_cycle is None else "caller"
    assert payload["runtime_cycle_source"] == expected_source
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False


def test_runtime_artifact_publisher_reads_numeric_string_cycle_from_session(tmp_path: Path) -> None:
    session = tmp_path / "css_session_state_pcnrass.json"
    session.write_text(json.dumps({"session": {"cycle_number": "11"}}), encoding="utf-8")

    result = RuntimeArtifactPublisher(
        artifacts_dir=tmp_path,
        session_state_path=session,
    ).publish(runtime_portfolio_state=_runtime_state())

    assert result["runtime_cycle"] == 11
    assert result["runtime_cycle_status"] == "OK"


def test_runtime_artifact_publisher_does_not_crash_when_cycle_unavailable(tmp_path: Path) -> None:
    result = RuntimeArtifactPublisher(artifacts_dir=tmp_path).publish(
        runtime_cycle="NOT_REPORTED",
        runtime_portfolio_state=_runtime_state(),
    )

    assert result["status"] == "AMBER"
    assert result["runtime_cycle"] is None
    assert (tmp_path / "runtime_portfolio_state.json").is_file()
