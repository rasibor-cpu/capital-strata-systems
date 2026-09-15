from datetime import datetime, timezone
from decimal import Decimal
import json

from backend.operations import (
    CapacityTelemetry,
    ExecutiveCommandInput,
    build_capacity_summary,
    build_executive_command_snapshot,
    build_executive_operational_report,
    render_executive_operational_report_json,
)


NOW = datetime(2026, 9, 15, 18, 0, tzinfo=timezone.utc)


def snapshot():
    return build_executive_command_snapshot(
        ExecutiveCommandInput(
            observed_at_utc=NOW,
            runtime_health="HEALTHY",
            broker_health="HEALTHY",
            data_freshness="HEALTHY",
            governance_status="PASS",
            security_status="PASS",
            reconciliation_status="PASS",
            backup_status="PASS",
            recovery_status="PASS",
            capacity_status="PASS",
        )
    )


def test_capacity_summary_passes_below_thresholds():
    result = build_capacity_summary(
        CapacityTelemetry(
            cpu_utilization_pct=Decimal("25"),
            memory_utilization_pct=Decimal("35"),
            dashboard_latency_ms=Decimal("75"),
            payload_bytes=1024,
            websocket_latency_ms=Decimal("20"),
        )
    )
    assert result.status == "PASS"
    assert result.warnings == ()


def test_capacity_summary_warns_on_multiple_thresholds():
    result = build_capacity_summary(
        CapacityTelemetry(
            cpu_utilization_pct=Decimal("90"),
            memory_utilization_pct=Decimal("90"),
            dashboard_latency_ms=Decimal("300"),
            payload_bytes=200000,
            websocket_latency_ms=Decimal("150"),
        )
    )
    assert result.status == "WARN"
    assert "CPU_CAPACITY_WARN" in result.warnings
    assert "MEMORY_CAPACITY_WARN" in result.warnings
    assert "DASHBOARD_LATENCY_WARN" in result.warnings
    assert "WEBSOCKET_LATENCY_WARN" in result.warnings
    assert "PAYLOAD_SIZE_WARN" in result.warnings


def test_executive_report_is_deterministic_and_hashes_payload():
    cap = build_capacity_summary(
        CapacityTelemetry(
            cpu_utilization_pct=Decimal("20"),
            memory_utilization_pct=Decimal("30"),
            dashboard_latency_ms=Decimal("60"),
            payload_bytes=4096,
            websocket_latency_ms=Decimal("10"),
        )
    )
    a = build_executive_operational_report(snapshot(), capacity=cap)
    b = build_executive_operational_report(snapshot(), capacity=cap)
    assert a == b
    assert len(a["report_sha256"]) == 64


def test_report_preserves_fail_closed_safety_flags():
    report = build_executive_operational_report(snapshot())
    assert report["safety"] == {
        "execution_allowed": False,
        "broker_execution_armed": False,
        "money_movement_authorized": False,
        "live_trading_authorized": False,
    }


def test_report_json_round_trips():
    report = build_executive_operational_report(snapshot())
    rendered = render_executive_operational_report_json(report)
    assert json.loads(rendered)["report_sha256"] == report["report_sha256"]


def test_report_has_no_execution_surface():
    report = build_executive_operational_report(snapshot())
    prohibited = {
        "submit_order",
        "place_order",
        "withdraw",
        "deposit",
        "transfer",
        "fund_account",
    }
    assert prohibited.isdisjoint(report.keys())
