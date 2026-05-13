from __future__ import annotations

import json

from dashboard.runtime.replay_correlation import (
    create_correlation_id,
    enrich_with_correlation,
    short_correlation_id,
)
from dashboard.runtime.replay_event_envelope import (
    REPLAY_EVENT_ENVELOPE_SCHEMA_VERSION,
    build_replay_event_envelope,
)
from dashboard.runtime.replay_timeline_builder import build_replay_timelines
from dashboard.runtime.trade_lifecycle_replay_sink import TradeLifecycleReplaySink
from dashboard.runtime.trade_lifecycle_replay_viewer import (
    get_trade_lifecycle_replay_payload,
    load_trade_lifecycle_replay_records,
    normalize_trade_lifecycle_replay_record,
)


def test_correlation_id_is_stable_for_trade_lifecycle_identity() -> None:
    first = create_correlation_id(
        session_id="SESSION-1",
        lifecycle_id="LFC-POS-1",
        symbol="btc-usd",
        asset_class="crypto",
        cycle=7,
    )
    second = create_correlation_id(
        session_id="SESSION-1",
        lifecycle_id="LFC-POS-1",
        symbol="BTC-USD",
        asset_class="CRYPTO",
        cycle="7",
    )
    enriched = enrich_with_correlation(
        {
            "session_id": "SESSION-1",
            "position_id": "POS-1",
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "cycle": 7,
        }
    )

    assert first == second
    assert first.startswith("COR-")
    assert enriched["lifecycle_id"] == "LFC-POS-1"
    assert short_correlation_id(first) == first[:12]


def test_replay_event_envelope_redacts_and_preserves_identity() -> None:
    envelope = build_replay_event_envelope(
        {
            "event_type": "position_exit_booked",
            "position_id": "POS-2",
            "session_id": "SESSION-2",
            "symbol": "ETH-USD",
            "asset_class": "CRYPTO",
            "cycle": 4,
            "timestamp_utc": "2026-05-13T16:00:00+00:00",
            "api_secret": "do-not-leak",
        },
        subsystem="trade_lifecycle",
        source_module="tests.dashboard.test_replay_correlation_lineage",
    )

    assert envelope["schema_version"] == REPLAY_EVENT_ENVELOPE_SCHEMA_VERSION
    assert envelope["event_type"] == "position_exit_booked"
    assert envelope["subsystem"] == "trade_lifecycle"
    assert envelope["correlation_id"].startswith("COR-")
    assert envelope["lifecycle_id"] == "LFC-POS-2"
    assert envelope["payload"]["api_secret"] == "REDACTED"
    assert "do-not-leak" not in json.dumps(envelope, sort_keys=True)


def test_sink_and_viewer_read_legacy_and_envelope_records(tmp_path) -> None:
    sink_path = tmp_path / "lineage.jsonl"
    sink = TradeLifecycleReplaySink(sink_path)
    envelope = build_replay_event_envelope(
        {
            "event_type": "realized_pnl_handoff",
            "position_id": "POS-3",
            "session_id": "SESSION-3",
            "symbol": "EUR_USD",
            "asset_class": "FX",
            "cycle": 9,
            "timestamp_utc": "2026-05-13T16:01:00+00:00",
            "realized_pnl": "2.50",
        },
        subsystem="trade_lifecycle",
        source_module="tests.dashboard.test_replay_correlation_lineage",
    )

    sink.record(
        {
            "event_type": "position_exit_booked",
            "position_id": "POS-LEGACY",
            "session_id": "SESSION-OLD",
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "cycle": 8,
            "timestamp_utc": "2026-05-13T16:00:00+00:00",
        }
    )
    sink.record(envelope)
    with sink_path.open("a", encoding="utf-8") as handle:
        handle.write("malformed replay line\n")

    payload = get_trade_lifecycle_replay_payload(sink_path)
    filtered = get_trade_lifecycle_replay_payload(
        sink_path,
        correlation_id=envelope["correlation_id"],
        subsystem="trade_lifecycle",
    )

    assert payload["total_loaded_events"] == 2
    assert payload["malformed_line_count"] == 1
    assert payload["summary"]["by_subsystem"]["trade_lifecycle"] == 1
    assert filtered["filtered_event_count"] == 1
    assert filtered["events"][0]["schema_version"] == REPLAY_EVENT_ENVELOPE_SCHEMA_VERSION
    assert filtered["events"][0]["subsystem"] == "trade_lifecycle"
    assert filtered["events"][0]["payload"]["session_id"] == "SESSION-3"


def test_timeline_builder_groups_normalized_lineage_records(tmp_path) -> None:
    sink_path = tmp_path / "timeline.jsonl"
    sink = TradeLifecycleReplaySink(sink_path)
    first = build_replay_event_envelope(
        {
            "event_type": "position_exit_booked",
            "position_id": "POS-4",
            "session_id": "SESSION-4",
            "symbol": "GBP_USD",
            "asset_class": "FX",
            "cycle": 10,
            "timestamp_utc": "2026-05-13T16:02:00+00:00",
        },
        subsystem="trade_lifecycle",
        source_module="tests.dashboard.test_replay_correlation_lineage",
    )
    second = build_replay_event_envelope(
        {
            "event_type": "realized_pnl_handoff",
            "position_id": "POS-4",
            "session_id": "SESSION-4",
            "symbol": "GBP_USD",
            "asset_class": "FX",
            "cycle": 10,
            "timestamp_utc": "2026-05-13T16:02:01+00:00",
        },
        subsystem="trade_lifecycle",
        source_module="tests.dashboard.test_replay_correlation_lineage",
        correlation_id=first["correlation_id"],
        lifecycle_id=first["lifecycle_id"],
    )

    sink.record_many((first, second))
    records, malformed = load_trade_lifecycle_replay_records(sink_path)
    normalized = [normalize_trade_lifecycle_replay_record(record) for record in records]
    timeline_payload = build_replay_timelines(records)

    assert malformed == 0
    assert len({event["correlation_id"] for event in normalized}) == 1
    assert timeline_payload["timeline_count"] == 1
    assert timeline_payload["timelines"][0]["event_count"] == 2
    assert timeline_payload["timelines"][0]["event_types"] == [
        "position_exit_booked",
        "realized_pnl_handoff",
    ]
