from __future__ import annotations

import json

import pytest

from engine.execution.lifecycle import (
    TradeLifecycleAuditTrail,
    TradeLifecycleStage,
    build_trade_lifecycle_audit,
)


def test_trade_lifecycle_audit_records_full_accepted_path() -> None:
    trail = build_trade_lifecycle_audit(
        trade_id="T-001",
        symbol="BTC-USD",
        asset_class="CRYPTO",
        side="BUY",
        mode="paper",
    )

    assert trail.stages() == (
        "SIGNAL_RECEIVED",
        "GOVERNANCE_CHECKED",
        "RISK_CHECKED",
        "BROKER_ROUTE_SELECTED",
        "ORDER_SUBMITTED",
        "EXECUTION_REPORTED",
        "LEDGER_POSTED",
        "DASHBOARD_PUBLISHED",
    )
    assert trail.as_dict()["event_count"] == 8
    assert json.dumps(trail.as_dict())


def test_trade_lifecycle_audit_records_blocked_path() -> None:
    trail = build_trade_lifecycle_audit(
        trade_id="T-002",
        symbol="EUR_USD",
        asset_class="FX",
        side="SELL",
        mode="live",
        accepted=False,
        reason="risk_gate_blocked",
    )
    payload = trail.as_dict()

    assert trail.stages() == (
        "SIGNAL_RECEIVED",
        "GOVERNANCE_CHECKED",
        "RISK_CHECKED",
        "BLOCKED",
    )
    assert payload["events"][-1]["status"] == "BLOCKED"
    assert payload["events"][-1]["reason"] == "risk_gate_blocked"
    assert payload["events"][-1]["mode"] == "live"


def test_trade_lifecycle_audit_redacts_sensitive_metadata() -> None:
    trail = TradeLifecycleAuditTrail("T-003")
    trail.record(
        TradeLifecycleStage.BROKER_ROUTE_SELECTED,
        symbol="AAPL",
        asset_class="STOCK",
        side="BUY",
        metadata={
            "route": "IBKR",
            "api_key": "SHOULD_NOT_LEAK",
            "nested": {
                "token": "SHOULD_NOT_LEAK_EITHER",
                "safe": "VISIBLE",
            },
        },
    )
    encoded = json.dumps(trail.as_dict())
    metadata = trail.as_dict()["events"][0]["metadata"]

    assert metadata["api_key"] == "REDACTED"
    assert metadata["nested"]["token"] == "REDACTED"
    assert metadata["nested"]["safe"] == "VISIBLE"
    assert "SHOULD_NOT_LEAK" not in encoded
    assert "SHOULD_NOT_LEAK_EITHER" not in encoded


def test_trade_lifecycle_audit_rejects_unknown_stage() -> None:
    trail = TradeLifecycleAuditTrail("T-004")

    with pytest.raises(ValueError):
        trail.record("NOT_A_STAGE")
