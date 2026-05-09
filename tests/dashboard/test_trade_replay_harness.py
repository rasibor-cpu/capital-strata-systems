from __future__ import annotations

import json
from decimal import Decimal

from dashboard.runtime.audit_trail_viewer import mobile_trade_event_to_audit_event
from dashboard.runtime.trade_replay_harness import (
    ACCEPTED_LIFECYCLE_PATH,
    TRADE_REPLAY_PAYLOAD_VERSION,
    compare_expected_to_actual,
    replay_lifecycle_audit,
    replay_mobile_trade_event_file,
)
from engine.execution.lifecycle import build_trade_lifecycle_audit


def test_replay_lifecycle_audit_passes_for_accepted_trade_path() -> None:
    trail = build_trade_lifecycle_audit(
        trade_id="R-001",
        symbol="BTC-USD",
        asset_class="CRYPTO",
        side="BUY",
        mode="paper",
    )

    report = replay_lifecycle_audit(trail.as_dict())
    payload = report.as_dict()

    assert report.passed is True
    assert payload["payload_version"] == TRADE_REPLAY_PAYLOAD_VERSION
    assert payload["expected_step_count"] == len(ACCEPTED_LIFECYCLE_PATH)
    assert payload["actual_step_count"] == len(ACCEPTED_LIFECYCLE_PATH)
    assert payload["steps"][0]["actual_action"] == "SIGNAL_RECEIVED"
    assert json.dumps(payload, sort_keys=True)


def test_replay_lifecycle_audit_passes_for_blocked_trade_path() -> None:
    trail = build_trade_lifecycle_audit(
        trade_id="R-002",
        symbol="EUR_USD",
        asset_class="FX",
        side="SELL",
        mode="live",
        accepted=False,
        reason="risk_gate_blocked",
    )

    report = replay_lifecycle_audit(trail.as_dict())
    payload = report.as_dict()

    assert report.passed is True
    assert payload["actual_step_count"] == 4
    assert payload["steps"][-1]["actual_action"] == "BLOCKED"
    assert payload["steps"][-1]["actual_status"] == "BLOCKED"
    assert payload["steps"][-1]["reason"] == "risk_gate_blocked"


def test_replay_detects_expected_vs_actual_mismatch() -> None:
    report = compare_expected_to_actual(
        expected=[
            {"action": "SIGNAL_RECEIVED", "status": "RECORDED"},
            {"action": "ORDER_SUBMITTED", "status": "RECORDED"},
        ],
        actual=[
            {
                "event_id": "A-1",
                "timestamp_utc": "2026-05-08T20:00:00+00:00",
                "action": "SIGNAL_RECEIVED",
                "status": "RECORDED",
            },
            {
                "event_id": "A-2",
                "timestamp_utc": "2026-05-08T20:00:01+00:00",
                "action": "BLOCKED",
                "status": "BLOCKED",
                "reason": "governance_block",
            },
        ],
        session_id="SESSION-MISMATCH",
    )
    payload = report.as_dict()

    assert report.passed is False
    assert payload["timing"]["total_observed_ms"] == 1000.0
    assert {mismatch["field"] for mismatch in payload["mismatches"]} == {"action", "status"}


def test_mobile_replay_file_is_deterministic_redacted_and_json_safe(tmp_path) -> None:
    event_path = tmp_path / "mobile_events.jsonl"
    rows = [
        {
            "recorded_utc": "2026-05-08T20:00:00+00:00",
            "ok": False,
            "status": "LIVE_CONFIRMATION_REQUIRED",
            "ticket": {
                "ticket_id": "T-1",
                "user_id": "00017",
                "mode": "live",
                "source": "CSS_MOBILE",
            },
            "broker_response": {
                "required_confirmation": "EXECUTE",
                "api_secret": "do-not-export",
            },
            "ledger": {"amount": Decimal("1.25")},
        },
        {
            "recorded_utc": "2026-05-08T20:00:03+00:00",
            "ok": True,
            "status": "PAPER_TICKET_RECORDED",
            "ticket": {
                "ticket_id": "T-2",
                "user_id": "00017",
                "mode": "paper",
                "source": "CSS_MOBILE",
            },
        },
    ]
    event_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True, default=str) for row in rows),
        encoding="utf-8",
    )

    first = replay_mobile_trade_event_file(event_path, session_id="MOBILE-R-1")
    second = replay_mobile_trade_event_file(event_path, session_id="MOBILE-R-1")
    payload = first.as_dict()
    serialized = json.dumps(payload, sort_keys=True)

    assert first.passed is True
    assert first.replay_id == second.replay_id
    assert payload["actual_step_count"] == 2
    assert payload["timing"]["total_observed_ms"] == 3000.0
    assert "do-not-export" not in serialized
    assert "REDACTED" in serialized


def test_replay_audit_events_accepts_frontend_audit_event_shape() -> None:
    event = mobile_trade_event_to_audit_event(
        {
            "recorded_utc": "2026-05-08T20:00:00+00:00",
            "ok": False,
            "status": "MOBILE_AUTHORITY_DENIED",
            "ticket": {"ticket_id": "T-3", "user_id": "00018"},
            "broker_response": {"required": "submit_trade"},
        }
    )

    report = compare_expected_to_actual(
        expected=[
            {
                "action": "MOBILE_AUTHORITY_DENIED",
                "status": "MOBILE_AUTHORITY_DENIED",
                "category": "permission_denial",
            }
        ],
        actual=[event.as_dict()],
        session_id="AUDIT-R-1",
    )

    assert report.passed is True
    assert report.as_dict()["steps"][0]["category"] == "permission_denial"
