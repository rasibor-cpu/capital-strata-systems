from __future__ import annotations

import json
from decimal import Decimal

from dashboard.runtime.alerting_layer import build_alert_payload
from dashboard.runtime.runtime_event_bus import (
    RUNTIME_EVENT_SCHEMA_VERSION,
    RuntimeEventBus,
    build_runtime_event,
    runtime_event_from_replay_payload,
    runtime_event_from_ws_message,
    runtime_event_to_replay_envelope,
    runtime_event_to_ws_message,
    runtime_events_from_alert_payload,
    safe_json_dumps,
)
from dashboard.runtime.trade_lifecycle_service import TradeLifecycleExecutionStateService
from dashboard.runtime.ws_bridge import build_ws_message_from_runtime_event


def test_runtime_event_creation_is_json_safe_and_redacted() -> None:
    event = build_runtime_event(
        {
            "event_type": "position_exit_booked",
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "cycle": 12,
            "api_secret": "do-not-export",
            "realized_pnl": Decimal("1.25"),
        },
        subsystem="trade_lifecycle",
        severity="warning",
        source_module="tests.dashboard.test_runtime_event_bus",
        correlation_id="COR-TEST",
        timestamp_utc="2026-05-13T17:00:00+00:00",
    )
    serialized = json.dumps(event, sort_keys=True)

    assert event["schema_version"] == RUNTIME_EVENT_SCHEMA_VERSION
    assert event["event_id"].startswith("EVT-")
    assert event["severity"] == "WARNING"
    assert event["correlation_id"] == "COR-TEST"
    assert event["payload"]["realized_pnl"] == "1.25"
    assert event["payload"]["api_secret"] == "REDACTED"
    assert "do-not-export" not in serialized


def test_runtime_event_bus_publish_subscribe_recent_and_clear() -> None:
    bus = RuntimeEventBus(max_recent=3)
    received: list[dict] = []
    subscription_id = bus.subscribe(
        "trade_lifecycle/position_exit_booked",
        handler=received.append,
    )

    matching = build_runtime_event(
        {"event_type": "position_exit_booked", "symbol": "EUR_USD"},
        subsystem="trade_lifecycle",
        correlation_id="COR-MATCH",
    )
    nonmatching = build_runtime_event(
        {"event_type": "risk_update", "symbol": "EUR_USD"},
        subsystem="risk",
        correlation_id="COR-RISK",
    )

    bus.publish(matching)
    bus.publish(nonmatching)

    assert bus.subscription_count() == 1
    assert len(received) == 1
    assert received[0]["correlation_id"] == "COR-MATCH"
    assert bus.get_recent(subsystem="trade_lifecycle")[0]["event_type"] == "position_exit_booked"
    assert bus.get_recent(event_type="risk_update")[0]["subsystem"] == "risk"
    assert bus.unsubscribe(subscription_id) is True
    bus.clear()
    assert bus.get_recent() == ()
    assert bus.subscription_count() == 0


def test_runtime_event_converts_to_replay_envelope_and_preserves_correlation() -> None:
    event = build_runtime_event(
        {
            "event_type": "capital_released",
            "position_id": "POS-1",
            "symbol": "GBP_USD",
            "asset_class": "FX",
            "cycle": 4,
            "token": "hide-me",
        },
        subsystem="trade_lifecycle",
        correlation_id="COR-LINEAGE",
        source_module="tests.dashboard.test_runtime_event_bus",
    )
    envelope = runtime_event_to_replay_envelope(event)

    assert envelope["correlation_id"] == "COR-LINEAGE"
    assert envelope["event_type"] == "capital_released"
    assert envelope["subsystem"] == "trade_lifecycle"
    assert envelope["payload"]["payload"]["token"] == "REDACTED"
    assert "hide-me" not in safe_json_dumps(envelope)


def test_runtime_event_adapters_for_replay_alert_and_websocket() -> None:
    replay_event = runtime_event_from_replay_payload(
        {
            "event_type": "realized_pnl_handoff",
            "subsystem": "trade_lifecycle",
            "correlation_id": "COR-REPLAY",
            "timestamp_utc": "2026-05-13T17:01:00+00:00",
        }
    )
    ws_event = runtime_event_from_ws_message(
        {
            "message_type": "risk_update",
            "section": "risk",
            "generated_at": "2026-05-13T17:02:00+00:00",
            "data": {"risk": {"risk_state": "NORMAL"}},
        }
    )
    ws_message = runtime_event_to_ws_message(ws_event, sequence=9)
    ws_message_from_bridge = build_ws_message_from_runtime_event(ws_event, sequence=10)
    alert_events = runtime_events_from_alert_payload(
        build_alert_payload(
            {
                "sections": {
                    "broker": {
                        "connected": False,
                        "missing_credentials": True,
                    }
                }
            }
        )
    )

    assert replay_event["correlation_id"] == "COR-REPLAY"
    assert ws_event["event_type"] == "risk_update"
    assert ws_message["transport"] == "runtime_event_bus"
    assert ws_message["sequence"] == 9
    assert ws_message_from_bridge["sequence"] == 10
    assert {event["event_type"] for event in alert_events} == {
        "broker_disconnect",
        "credential_missing",
    }
    assert all(event["subsystem"] == "alerting" for event in alert_events)


def test_trade_lifecycle_service_optionally_publishes_runtime_events() -> None:
    class Noop:
        def record_trade(self, **_kwargs) -> None:
            return None

        def release_trade(self, _position_id: str) -> None:
            return None

        def release_cluster_slot(self, _cluster_name: str) -> None:
            return None

        def record_cluster_win(self, _symbol: str, _pnl: float) -> None:
            return None

        def record_forced_exit(self, _position_id: str, _amount: float) -> None:
            return None

        def record_priority_exit(self) -> None:
            return None

        def record_defensive_reduction_exit(self) -> None:
            return None

        def record_recycled_slot(self) -> None:
            return None

    bus = RuntimeEventBus()
    asset_pnls = {"FX": {"EUR_USD": 0.0}}
    service = TradeLifecycleExecutionStateService(
        pnl_tracker=Noop(),
        capital_tracker=Noop(),
        pnl_dict_provider=lambda asset_class: asset_pnls[asset_class],
        cluster_amplifier=Noop(),
        cluster_risk_governor=Noop(),
        locked_profit_ledger=Noop(),
        session_context_provider=lambda: {"session_id": "SESSION-BUS"},
        mode_provider=lambda: "paper",
        event_publisher=bus.publish,
    )

    result = service.book_position_exit(
        {
            "position_id": "POS-BUS",
            "asset_class": "FX",
            "symbol": "EUR_USD",
            "cluster_name": "FX_MAJOR",
            "floating": 3.0,
            "forced_exit": False,
            "broker_tested": False,
            "broker_order_ok": False,
        },
        "TAKE_PROFIT",
    )
    events = bus.get_recent()

    assert result.booked is True
    assert len(events) == len(result.replay_events)
    assert len({event["correlation_id"] for event in events}) == 1
    assert {event["event_type"] for event in events} >= {
        "position_exit_booked",
        "realized_pnl_handoff",
        "locked_profit_updated",
    }
