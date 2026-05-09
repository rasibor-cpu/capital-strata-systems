from __future__ import annotations

import json
from decimal import Decimal

from dashboard.runtime.audit_trail_viewer import (
    AUDIT_PAYLOAD_VERSION,
    export_audit_events,
    filter_audit_events,
    load_mobile_trade_audit_events,
    mobile_trade_event_to_audit_event,
)


def test_mobile_audit_events_are_classified_and_redacted(tmp_path) -> None:
    event_path = tmp_path / "mobile_events.jsonl"
    event_path.write_text(
        json.dumps(
            {
                "recorded_utc": "2026-05-08T20:00:00+00:00",
                "ok": False,
                "status": "GLOBAL_LIVE_ORDER_KILL_SWITCH_ENGAGED",
                "ticket": {
                    "ticket_id": "ABC123",
                    "user_id": "00017",
                    "source": "CSS_MOBILE",
                },
                "broker_response": {
                    "kill_switch_reason": "global_live_order_kill_switch",
                    "api_secret": "never-export",
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    events = load_mobile_trade_audit_events(event_path)
    exported = export_audit_events(events)
    serialized = json.dumps(exported, sort_keys=True)

    assert len(events) == 1
    assert events[0].category == "kill_switch"
    assert events[0].actor == "00017"
    assert events[0].reason == "global_live_order_kill_switch"
    assert exported["payload_version"] == AUDIT_PAYLOAD_VERSION
    assert "never-export" not in serialized
    assert "REDACTED" in serialized


def test_audit_filters_match_category_status_and_actor() -> None:
    approved = mobile_trade_event_to_audit_event(
        {
            "recorded_utc": "2026-05-08T20:01:00+00:00",
            "ok": True,
            "status": "PAPER_TICKET_RECORDED",
            "ticket": {"ticket_id": "T1", "user_id": "00017"},
        }
    )
    blocked = mobile_trade_event_to_audit_event(
        {
            "recorded_utc": "2026-05-08T20:02:00+00:00",
            "ok": False,
            "status": "MOBILE_AUTHORITY_DENIED",
            "ticket": {"ticket_id": "T2", "user_id": "00018"},
        }
    )

    assert filter_audit_events((approved, blocked), category="approval") == (approved,)
    assert filter_audit_events((approved, blocked), status="AUTHORITY") == (blocked,)
    assert filter_audit_events((approved, blocked), actor="00017") == (approved,)


def test_audit_export_is_json_safe_with_decimal_payloads() -> None:
    event = mobile_trade_event_to_audit_event(
        {
            "recorded_utc": "2026-05-08T20:03:00+00:00",
            "ok": True,
            "status": "PAPER_TICKET_RECORDED",
            "ticket": {"ticket_id": "T3", "user_id": "00017"},
            "ledger": {"amount": Decimal("10.25"), "private_key": "secret"},
        }
    )

    exported = export_audit_events((event,))
    serialized = json.dumps(exported, sort_keys=True)

    assert '"10.25"' in serialized
    assert "secret" not in serialized
    assert "REDACTED" in serialized


def test_audit_loader_ignores_malformed_jsonl(tmp_path) -> None:
    event_path = tmp_path / "mobile_events.jsonl"
    event_path.write_text(
        "\n".join(
            [
                "not-json",
                json.dumps(
                    {
                        "recorded_utc": "2026-05-08T20:04:00+00:00",
                        "ok": False,
                        "status": "LIVE_CONFIRMATION_REQUIRED",
                        "ticket": {"ticket_id": "T4", "user_id": "00017"},
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    events = load_mobile_trade_audit_events(event_path)

    assert len(events) == 1
    assert events[0].category == "governance_block"
