from decimal import Decimal

import pytest

from backend.commercialization.cost_to_serve_telemetry import (
    build_cost_to_serve_telemetry,
)


def test_cost_telemetry_preserves_counters_and_decimal_basis():
    telemetry = build_cost_to_serve_telemetry(
        observation_id="OBS-1",
        observed_at="2026-09-09T23:00:00+00:00",
        request_count=7,
        runtime_seconds=Decimal("12.50"),
        infrastructure_cost=Decimal("0.37"),
        cost_basis_refs=("caller:cloud-meter-1",),
    )

    assert telemetry.request_count == 7
    assert telemetry.runtime_seconds == Decimal("12.50")
    assert telemetry.estimated_cost == Decimal("0.37")
    assert telemetry.cost_basis_complete is True


def test_unknown_cost_is_not_zero():
    telemetry = build_cost_to_serve_telemetry(
        observation_id="OBS-2",
        observed_at="2026-09-09T23:00:00+00:00",
    )

    assert telemetry.estimated_cost is None
    assert telemetry.cost_basis_complete is False
    assert telemetry.as_dict()["estimated_cost"] is None


def test_telemetry_is_read_only_and_cannot_affect_commercial_or_execution_paths():
    telemetry = build_cost_to_serve_telemetry(
        observation_id="OBS-3",
        observed_at="2026-09-09T23:00:00+00:00",
        infrastructure_cost="1.25",
        cost_basis_refs=("caller:meter",),
    )

    payload = telemetry.as_dict()
    assert all(payload[key] is False for key in (
        "customer_charge_affected",
        "performance_fee_affected",
        "platform_minimum_affected",
        "trade_decision_affected",
        "execution_affected",
    ))
    assert payload["read_only"] is True


def test_telemetry_does_not_mutate_cost_basis_and_rejects_invalid_values():
    refs = ["caller:meter"]
    telemetry = build_cost_to_serve_telemetry(
        observation_id="OBS-4",
        observed_at="2026-09-09T23:00:00+00:00",
        cost_basis_refs=tuple(refs),
    )
    refs.append("unexpected")

    assert telemetry.cost_basis_refs == ("caller:meter",)
    with pytest.raises(ValueError):
        build_cost_to_serve_telemetry(
            observation_id="OBS-5",
            observed_at="2026-09-09T23:00:00+00:00",
            infrastructure_cost="NaN",
        )