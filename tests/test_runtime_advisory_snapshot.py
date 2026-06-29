from __future__ import annotations

from backend.portfolio.runtime_advisory_snapshot import RuntimeAdvisorySnapshot


def _components(status: str = "OK"):
    names = RuntimeAdvisorySnapshot.REQUIRED_COMPONENTS
    return {name: {"status": status, "advisory_only": True} for name in names}


def test_runtime_advisory_snapshot_lists_available_components() -> None:
    snapshot = RuntimeAdvisorySnapshot().build(
        runtime_state={"status": "OK", "reasons": []},
        advisory_components=_components("OK"),
        portfolio_decision={"overall_status": "GREEN", "missing_inputs": []},
    )

    assert snapshot["snapshot_status"] == "OK"
    assert snapshot["runtime_state_status"] == "OK"
    assert snapshot["portfolio_decision_status"] == "GREEN"
    assert len(snapshot["available_components"]) == len(RuntimeAdvisorySnapshot.REQUIRED_COMPONENTS)
    assert snapshot["missing_components"] == []
    assert snapshot["advisory_only"] is True
    assert snapshot["execution_allowed"] is False


def test_runtime_advisory_snapshot_reports_missing_components() -> None:
    components = _components("OK")
    components["quantitative_metrics"] = {"status": "DATA UNAVAILABLE", "reasons": ["portfolio_return_series_insufficient"]}

    snapshot = RuntimeAdvisorySnapshot().build(
        runtime_state={"status": "OK", "reasons": []},
        advisory_components=components,
        portfolio_decision={"overall_status": "RED", "missing_inputs": ["quantitative_metrics"]},
    )

    assert snapshot["snapshot_status"] == "PARTIAL"
    assert "quantitative_metrics" in snapshot["missing_components"]
    assert "quantitative_metrics:portfolio_return_series_insufficient" in snapshot["missing_input_reasons"]
    assert "portfolio_decision_missing:quantitative_metrics" in snapshot["missing_input_reasons"]


def test_runtime_advisory_snapshot_data_unavailable_without_state_or_components() -> None:
    snapshot = RuntimeAdvisorySnapshot().build(
        runtime_state=None,
        advisory_components={},
        portfolio_decision=None,
    )

    assert snapshot["snapshot_status"] == "DATA UNAVAILABLE"
    assert snapshot["available_components"] == []
    assert set(snapshot["missing_components"]) == set(RuntimeAdvisorySnapshot.REQUIRED_COMPONENTS)
