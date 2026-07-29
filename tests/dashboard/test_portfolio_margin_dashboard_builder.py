from __future__ import annotations

import builtins
import os
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

from dashboard.runtime.portfolio_margin_dashboard_builder import (
    PORTFOLIO_MARGIN_DASHBOARD_BUILDER_VERSION,
    PortfolioMarginDashboardBuilder,
    build_portfolio_margin_dashboard_payload,
)
from engine.risk.margin_state import MarginState
from engine.risk.portfolio_margin_snapshot import PortfolioMarginSnapshot

GENERATED_AT = "2026-07-29T00:00:00+00:00"


def _snapshot(**overrides: Any) -> dict[str, Any]:
    snapshot = {
        "portfolio_equity": 1000.0,
        "portfolio_buying_power": 750.0,
        "portfolio_margin_used": 250.0,
        "portfolio_margin_available": 750.0,
        "portfolio_risk_state": "NORMAL",
        "broker_count": 2,
        "timestamp": "2026-07-29T00:00:01+00:00",
    }
    snapshot.update(overrides)
    return snapshot


def test_import_and_public_api() -> None:
    builder = PortfolioMarginDashboardBuilder()

    assert PORTFOLIO_MARGIN_DASHBOARD_BUILDER_VERSION == (
        "css.portfolio_margin_dashboard_builder.v2"
    )
    assert callable(builder.build_payload)
    assert callable(build_portfolio_margin_dashboard_payload)


def test_deterministic_projection_and_timestamp() -> None:
    canonical = PortfolioMarginSnapshot(
        portfolio_equity=1000.0,
        portfolio_buying_power=700.0,
        portfolio_margin_used=300.0,
        portfolio_margin_available=700.0,
        portfolio_risk_state=MarginState.WARNING,
        broker_count=2,
        timestamp="2026-07-29T00:00:02+00:00",
    )
    first = build_portfolio_margin_dashboard_payload(
        snapshots=[canonical],
        generated_at_utc=GENERATED_AT,
    )
    second = build_portfolio_margin_dashboard_payload(
        snapshots=[canonical],
        generated_at_utc=GENERATED_AT,
    )

    assert first == second
    assert first["generated_at_utc"] == GENERATED_AT
    assert first["status"] == "OK"
    assert first["current_snapshot"]["portfolio_risk_state"] == "WARNING"
    assert first["account_summary"]["margin_utilization_pct"] == 30.0
    assert first["risk_escalation"]["escalation_required"] is True


def test_missing_data_fails_closed_without_zero_safe_defaults() -> None:
    payload = build_portfolio_margin_dashboard_payload(generated_at_utc=GENERATED_AT)

    assert payload["status"] == "DATA_UNAVAILABLE"
    assert payload["readiness_status"] == "BLOCKED"
    assert payload["account_summary"]["equity"] is None
    assert payload["account_summary"]["margin_utilization_pct"] is None
    assert "portfolio_margin_snapshots_missing" in payload["risk_status"]["blockers"]
    assert "PORTFOLIO_MARGIN_DATA_UNAVAILABLE" in payload["warnings"]


def test_malformed_data_fails_closed() -> None:
    payload = build_portfolio_margin_dashboard_payload(
        snapshots=[_snapshot(portfolio_equity=None)],
        generated_at_utc=GENERATED_AT,
    )

    assert payload["status"] == "DATA_UNAVAILABLE"
    assert payload["current_snapshot"] == {}
    assert payload["risk_status"]["fail_closed"] is True
    assert payload["malformed_snapshot_count"] == 1
    assert payload["risk_status"]["blockers"] == ["snapshot_0_missing_portfolio_equity"]


def test_invalid_margin_capacity_fails_closed() -> None:
    payload = build_portfolio_margin_dashboard_payload(
        snapshots=[_snapshot(portfolio_margin_used=0, portfolio_margin_available=0)],
        generated_at_utc=GENERATED_AT,
    )

    assert payload["status"] == "DATA_UNAVAILABLE"
    assert "snapshot_0_invalid_margin_capacity" in payload["risk_status"]["blockers"]


def test_deterministic_ordering_and_trends() -> None:
    payload = build_portfolio_margin_dashboard_payload(
        snapshots=[
            _snapshot(
                portfolio_equity=900,
                portfolio_buying_power=550,
                portfolio_margin_used=450,
                portfolio_margin_available=550,
                portfolio_risk_state="WARNING",
                timestamp="2026-07-29T00:00:03+00:00",
            ),
            _snapshot(timestamp="2026-07-29T00:00:01+00:00"),
        ],
        risk_events=[
            {"risk_state": "WARNING", "escalation_level": 1, "timestamp": "T2"},
            {"risk_state": "NORMAL", "escalation_level": 0, "timestamp": "T1"},
        ],
        generated_at_utc=GENERATED_AT,
    )

    assert [item["timestamp"] for item in payload["snapshots"]] == [
        "2026-07-29T00:00:01+00:00",
        "2026-07-29T00:00:03+00:00",
    ]
    assert [item["timestamp"] for item in payload["risk_events"]] == ["T1", "T2"]
    assert payload["trends"]["margin_utilization_trend"] == "DETERIORATING"
    assert payload["trends"]["buying_power_trend"] == "DETERIORATING"
    assert payload["trends"]["equity_trend"] == "DETERIORATING"
    assert payload["trends"]["risk_state_trend"] == "DETERIORATING"


def test_projection_has_no_runtime_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_side_effect(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("portfolio margin projection attempted a side effect")

    with monkeypatch.context() as side_effect_guard:
        side_effect_guard.setattr(os, "getenv", fail_side_effect)
        side_effect_guard.setattr(os, "putenv", fail_side_effect)
        side_effect_guard.setattr(os, "system", fail_side_effect)
        side_effect_guard.setattr(socket, "socket", fail_side_effect)
        side_effect_guard.setattr(socket, "create_connection", fail_side_effect)
        side_effect_guard.setattr(subprocess, "run", fail_side_effect)
        side_effect_guard.setattr(subprocess, "Popen", fail_side_effect)
        side_effect_guard.setattr(Path, "open", fail_side_effect)
        side_effect_guard.setattr(Path, "read_text", fail_side_effect)
        side_effect_guard.setattr(Path, "write_text", fail_side_effect)
        side_effect_guard.setattr(builtins, "open", fail_side_effect)

        payload = PortfolioMarginDashboardBuilder().build_payload(
            [_snapshot()],
            generated_at_utc=GENERATED_AT,
        )

    assert payload["status"] == "OK"
    assert payload["execution_allowed"] is False
    assert payload["orders_enabled"] is False
    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_filesystem_reads"] is True
    assert payload["source_metadata"]["no_filesystem_writes"] is True
