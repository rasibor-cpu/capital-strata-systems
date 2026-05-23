from __future__ import annotations

from pathlib import Path

from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.broker_balance_reconciliation import (
    BROKER_RECONCILIATION_PAYLOAD_VERSION,
    build_broker_reconciliation_payload,
    reconcile_dashboard_payload,
)
from dashboard.runtime.css_mobile_controls import (
    MOBILE_CONTROL_FILE,
    load_mobile_controls,
    save_mobile_controls,
)
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.frontend_contract import build_frontend_payload
from dashboard.runtime.operator_action_audit_ledger import (
    OperatorActionAuditLedger,
    SUPPORTED_OPERATOR_ACTION_TYPES,
    build_operator_action_audit_record,
)
from dashboard.runtime.payload_validator import FrontendPayloadValidator
from dashboard.runtime.post_pilot_reconciliation_workflow import check_replay_evidence_presence
from dashboard.runtime.session_replay_evidence_export import (
    build_session_replay_evidence_export_payload,
)
from dashboard.runtime.trade_lifecycle_replay_sink import TradeLifecycleReplaySink
from dashboard.runtime.trade_lifecycle_replay_viewer import (
    load_trade_lifecycle_replay_records,
    normalize_trade_lifecycle_replay_record,
)
from dashboard.runtime.web_kill_switch_governance import (
    WEB_KILL_SWITCH_CONFIRMATION_TOKEN,
    engage_web_kill_switch,
)
from dashboard.web.web_app import _dashboard_page, create_app as create_web_app


def test_frontend_contract_includes_phase54_sections() -> None:
    payload = build_frontend_payload(DashboardState())
    sections = payload["sections"]

    assert "operational_identity" in sections
    assert "pilot_safety" in sections
    assert "broker_reconciliation" in sections
    assert sections["pilot_safety"]["live_capital_banner"]["headline"]
    assert FrontendPayloadValidator().validate(payload) is True


def test_broker_reconciliation_includes_dashboard_visibility() -> None:
    report = reconcile_dashboard_payload(DashboardState().to_dict())
    payload = report.as_dict()

    assert payload["payload_version"] == BROKER_RECONCILIATION_PAYLOAD_VERSION
    assert payload["dashboard_visibility"]["visible"] is True
    assert payload["dashboard_visibility"]["headline"]


def test_kill_switch_engagement_is_governed_and_audited(tmp_path: Path, monkeypatch) -> None:
    control_file = tmp_path / "css_mobile_controls.json"
    monkeypatch.setattr(
        "dashboard.runtime.css_mobile_controls.MOBILE_CONTROL_FILE",
        control_file,
    )
    monkeypatch.setattr(
        "dashboard.runtime.web_kill_switch_governance.MOBILE_CONTROL_FILE",
        control_file,
    )
    save_mobile_controls({"runtime_mode": "paper", "orders_enabled": True})
    ledger = OperatorActionAuditLedger()

    rejected = engage_web_kill_switch(
        operator_id="",
        confirmation_token=WEB_KILL_SWITCH_CONFIRMATION_TOKEN,
        ledger=ledger,
    )
    assert rejected["ok"] is False

    engaged = engage_web_kill_switch(
        operator_id="operator-54",
        confirmation_token=WEB_KILL_SWITCH_CONFIRMATION_TOKEN,
        reason="phase54 test",
        ledger=ledger,
    )
    assert engaged["ok"] is True
    assert engaged["kill_switch"]["blocked"] is True
    controls = load_mobile_controls()
    assert controls["live_order_kill_switch"] is True
    assert controls["orders_enabled"] is False
    assert ledger.get_recent(action_type="KILL_SWITCH_ENGAGED")


def test_operator_audit_supports_kill_switch_action_type() -> None:
    assert "KILL_SWITCH_ENGAGED" in SUPPORTED_OPERATOR_ACTION_TYPES
    entry = build_operator_action_audit_record(action_type="KILL_SWITCH_ENGAGED")
    assert entry["action_type"] == "KILL_SWITCH_ENGAGED"
    assert entry["execution_allowed"] is False


def test_check_replay_evidence_uses_trade_lifecycle_sink(tmp_path: Path) -> None:
    sink_path = tmp_path / "replay.jsonl"
    sink = TradeLifecycleReplaySink(sink_path)
    sink.record(
        {
            "event_type": "position_exit_booked",
            "symbol": "BTC-USD",
            "asset_class": "crypto",
            "cycle": 1,
            "mode": "paper",
            "payload": {"symbol": "BTC-USD", "asset_class": "crypto", "cycle": 1},
        }
    )
    records, _ = load_trade_lifecycle_replay_records(sink_path)
    correlation_id = normalize_trade_lifecycle_replay_record(records[0])["correlation_id"]
    export_payload = build_session_replay_evidence_export_payload(
        replay_correlation_ids=[correlation_id],
        replay_path=sink_path,
    )
    assert export_payload["replay_event_count"] >= 1
    assert check_replay_evidence_presence([correlation_id], replay_path=sink_path) == []

    missing_flags = check_replay_evidence_presence(
        ["CORR-UNKNOWN"],
        replay_path=sink_path,
    )
    assert missing_flags == ["REPLAY_CORRELATION_NOT_IN_TRADE_LIFECYCLE"]

    empty_flags = check_replay_evidence_presence([], replay_path=sink_path)
    assert empty_flags == ["REPLAY_EVIDENCE_MISSING"]


def test_phase54_api_routes_exist() -> None:
    app = create_app()
    routes = {getattr(route, "path", ""): route for route in app.routes}

    for path in (
        "/api/v1/operational-identity",
        "/api/v1/live-capital-banner",
        "/api/v1/web-kill-switch/status",
        "/api/v1/web-kill-switch/engage",
        "/api/v1/session-replay-evidence-export",
    ):
        assert path in routes

    engage_route = routes["/api/v1/web-kill-switch/engage"]
    assert "POST" in getattr(engage_route, "methods", set())


def test_dashboard_markup_includes_phase54_safety_controls() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _dashboard_page()

    assert "/dashboard" in routes
    for expected in (
        "live-capital-banner",
        "operational-identity-strip",
        "reconciliation-visibility-panel",
        "kill-switch-panel",
        "LIVE CAPITAL ACTIVE",
        "/api/v1/web-kill-switch/engage",
    ):
        assert expected in markup
