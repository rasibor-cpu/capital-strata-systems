from __future__ import annotations

from backend.validation.validation_readiness_engine import ValidationReadinessEngine


def test_validation_readiness_distinguishes_missing_advisory_inputs() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health={"runtime_health": "GREEN"},
        session_validation={"session_status": "GREEN"},
        portfolio_decision={"overall_status": "RED", "missing_inputs": ["quantitative_metrics"]},
        operational_telemetry={"overall_status": "GREEN"},
        runtime_advisory_snapshot={
            "snapshot_status": "PARTIAL",
            "missing_components": ["quantitative_metrics"],
        },
    )

    assert result["readiness_status"] == "NOT_READY"
    assert "portfolio_advisory_inputs_missing" in result["blockers"]
    assert "portfolio_decision_risk_red" not in result["blockers"]
    assert "runtime_advisory_snapshot_partial" in result["warnings"]
    assert any("Populate runtime-derived advisory inputs" in action for action in result["recommended_actions"])


def test_validation_readiness_distinguishes_genuine_risk_red() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health={"runtime_health": "GREEN"},
        session_validation={"session_status": "GREEN"},
        portfolio_decision={"overall_status": "RED", "missing_inputs": []},
        operational_telemetry={"overall_status": "GREEN"},
        runtime_advisory_snapshot={"snapshot_status": "OK", "missing_components": []},
    )

    assert result["readiness_status"] == "NOT_READY"
    assert "portfolio_decision_risk_red" in result["blockers"]
    assert "portfolio_advisory_inputs_missing" not in result["blockers"]


def test_validation_readiness_allows_ready_with_complete_snapshot() -> None:
    result = ValidationReadinessEngine().evaluate(
        runtime_health={"runtime_health": "GREEN"},
        session_validation={"session_status": "GREEN"},
        portfolio_decision={"overall_status": "GREEN", "missing_inputs": []},
        operational_telemetry={"overall_status": "GREEN"},
        runtime_advisory_snapshot={"snapshot_status": "OK", "missing_components": []},
    )

    assert result["readiness_status"] == "READY"
    assert result["blockers"] == []
    assert result["warnings"] == []
