from __future__ import annotations

import logging
from decimal import Decimal

import pytest

from dashboard.runtime.dashboard_shadow_compare import compare_dashboard_shadow
from dashboard.runtime.dashboard_state import DashboardState


def test_shadow_compare_matches_numeric_equivalents() -> None:
    comparison = compare_dashboard_shadow(
        {
            "pnl": {
                "realized_pnl": Decimal("10.00"),
                "unrealized_pnl": "2.50",
            },
            "risk": {
                "position_limit": 10,
            },
        },
        {
            "pnl": {
                "realized_pnl": 10.0,
                "unrealized_pnl": Decimal("2.500"),
            },
            "risk": {
                "position_limit": "10",
            },
        },
    )

    assert comparison.matched is True
    assert comparison.compared_count == 3
    assert comparison.divergence_count == 0
    assert comparison.as_dict()["divergences"] == []


def test_shadow_compare_reports_nested_divergences_without_raising(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="dashboard.runtime.dashboard_shadow_compare")

    comparison = compare_dashboard_shadow(
        {
            "execution": {
                "accepted_trade_count": 2,
                "execution_state": "READY",
            },
            "risk": {
                "gate_status": "OPEN",
            },
        },
        {
            "execution": {
                "accepted_trade_count": 3,
            },
            "risk": {
                "gate_status": "CLOSED",
            },
        },
    )

    divergence_payloads = [item.as_dict() for item in comparison.divergences]

    assert comparison.matched is False
    assert comparison.compared_count == 3
    assert comparison.divergence_count == 3
    assert {
        "path": "execution.accepted_trade_count",
        "legacy_value": 2,
        "dashboard_state_value": 3,
        "reason": "value_mismatch",
    } in divergence_payloads
    assert {
        "path": "execution.execution_state",
        "legacy_value": "READY",
        "dashboard_state_value": None,
        "reason": "dashboard_state_value_missing",
    } in divergence_payloads
    assert {
        "path": "risk.gate_status",
        "legacy_value": "OPEN",
        "dashboard_state_value": "CLOSED",
        "reason": "value_mismatch",
    } in divergence_payloads
    assert "Dashboard shadow divergence path=execution.accepted_trade_count" in caplog.text
    assert "Dashboard shadow divergence path=execution.execution_state" in caplog.text
    assert "Dashboard shadow divergence path=risk.gate_status" in caplog.text


def test_shadow_compare_accepts_dashboard_state_inputs() -> None:
    state = DashboardState(
        session_id="SHADOW-SESSION",
        user_id="00017",
        role="TRADER",
        live_or_paper="paper",
    )

    comparison = compare_dashboard_shadow(
        {
            "session_id": "SHADOW-SESSION",
            "user_id": "00017",
            "role": "TRADER",
            "live_or_paper": "paper",
        },
        state,
    )

    assert comparison.matched is True
    assert comparison.compared_count == 4
    assert comparison.divergence_count == 0


def test_shadow_compare_can_compare_explicit_paths() -> None:
    comparison = compare_dashboard_shadow(
        {"pnl": {"net_pnl": 27.5}},
        {"pnl": {"net_pnl": 27.5, "extra_field": "ignored"}},
        paths=("pnl.net_pnl",),
    )

    assert comparison.matched is True
    assert comparison.compared_count == 1
    assert comparison.divergence_count == 0


def test_shadow_compare_rejects_invalid_dashboard_payload_type() -> None:
    with pytest.raises(TypeError, match="dashboard_state must be"):
        compare_dashboard_shadow({"net_pnl": 1.0}, object())
