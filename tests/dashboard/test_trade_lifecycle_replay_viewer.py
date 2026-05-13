from __future__ import annotations

import json
from decimal import Decimal

from dashboard.runtime.trade_lifecycle_replay_sink import TradeLifecycleReplaySink
from dashboard.runtime.trade_lifecycle_replay_viewer import (
    TRADE_LIFECYCLE_REPLAY_VIEWER_VERSION,
    filter_trade_lifecycle_replay_records,
    get_trade_lifecycle_replay_payload,
    load_trade_lifecycle_replay_records,
    normalize_trade_lifecycle_replay_record,
    summarize_trade_lifecycle_replay_records,
)


def test_replay_viewer_missing_file_returns_empty_safe_payload(tmp_path) -> None:
    payload = get_trade_lifecycle_replay_payload(tmp_path / "missing.jsonl")

    assert payload["payload_version"] == TRADE_LIFECYCLE_REPLAY_VIEWER_VERSION
    assert payload["source_exists"] is False
    assert payload["total_loaded_events"] == 0
    assert payload["summary"]["total_events"] == 0
    assert payload["events"] == []


def test_replay_viewer_filters_and_summarizes_lifecycle_events(tmp_path) -> None:
    sink_path = tmp_path / "replay.jsonl"
    sink = TradeLifecycleReplaySink(sink_path)
    rows = [
        {
            "event_type": "position_exit_booked",
            "position_id": "POS-1",
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "mode": "paper",
            "session_id": "S1",
            "cycle": 3,
            "timestamp_utc": "2026-05-08T20:00:00+00:00",
            "realized_pnl": Decimal("1.25"),
        },
        {
            "event_type": "realized_pnl_handoff",
            "position_id": "POS-1",
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "mode": "paper",
            "session_id": "S1",
            "cycle": 3,
            "timestamp_utc": "2026-05-08T20:00:01+00:00",
            "realized_pnl": Decimal("1.25"),
        },
        {
            "event_type": "capital_released",
            "position_id": "POS-2",
            "symbol": "EUR_USD",
            "asset_class": "FX",
            "mode": "live",
            "session_id": "S2",
            "cycle": 4,
            "timestamp_utc": "2026-05-08T20:01:00+00:00",
        },
        {
            "event_type": "defensive_reduction_applied",
            "position_id": "POS-3",
            "symbol": "EUR_USD",
            "asset_class": "FX",
            "mode": "paper",
            "session_id": "S2",
            "cycle": 5,
            "timestamp_utc": "2026-05-08T20:02:00+00:00",
        },
        {
            "event_type": "locked_profit_updated",
            "position_id": "POS-3",
            "symbol": "EUR_USD",
            "asset_class": "FX",
            "mode": "paper",
            "session_id": "S2",
            "cycle": 5,
            "timestamp_utc": "2026-05-08T20:02:01+00:00",
        },
        {
            "event_type": "lifecycle_audit_payload_created",
            "position_id": "POS-3",
            "symbol": "EUR_USD",
            "asset_class": "FX",
            "mode": "paper",
            "session_id": "S2",
            "cycle": 5,
            "timestamp_utc": "2026-05-08T20:02:02+00:00",
        },
    ]
    sink.record_many(rows)

    fx_payload = get_trade_lifecycle_replay_payload(
        sink_path,
        symbol="EUR_USD",
        asset_class="FX",
        start_utc="2026-05-08T20:00:30+00:00",
        end_utc="2026-05-08T20:03:00+00:00",
    )
    cycle_payload = get_trade_lifecycle_replay_payload(sink_path, cycle=3)
    event_payload = get_trade_lifecycle_replay_payload(
        sink_path,
        event_type="defensive_reduction_applied",
    )

    assert fx_payload["filtered_event_count"] == 4
    assert fx_payload["summary"]["capital_releases"] == 1
    assert fx_payload["summary"]["defensive_reductions"] == 1
    assert fx_payload["summary"]["locked_profit_updates"] == 1
    assert fx_payload["summary"]["lifecycle_audit_payloads"] == 1
    assert cycle_payload["filtered_event_count"] == 2
    assert cycle_payload["summary"]["exits_booked"] == 1
    assert cycle_payload["summary"]["realized_pnl_handoffs"] == 1
    assert event_payload["filtered_event_count"] == 1
    assert event_payload["events"][0]["event_type"] == "defensive_reduction_applied"
    assert json.dumps(fx_payload, sort_keys=True)


def test_replay_viewer_reports_malformed_lines_and_redacts(tmp_path) -> None:
    sink_path = tmp_path / "replay_with_bad_lines.jsonl"
    sink = TradeLifecycleReplaySink(sink_path)
    sink.record(
        {
            "event_type": "position_exit_booked",
            "position_id": "POS-SECRET",
            "symbol": "ETH-USD",
            "asset_class": "CRYPTO",
            "mode": "paper",
            "session_id": "S3",
            "timestamp_utc": "2026-05-08T20:04:00+00:00",
            "private_key": "do-not-show",
        }
    )
    with sink_path.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")
        handle.write(json.dumps(["not", "a", "dict"]) + "\n")

    records, malformed = load_trade_lifecycle_replay_records(sink_path)
    payload = get_trade_lifecycle_replay_payload(sink_path)
    serialized = json.dumps(payload, sort_keys=True)

    assert len(records) == 1
    assert malformed == 2
    assert payload["malformed_line_count"] == 2
    assert payload["summary"]["malformed_lines"] == 2
    assert "do-not-show" not in serialized
    assert "REDACTED" in serialized


def test_replay_viewer_pure_helpers_match_normalized_shape() -> None:
    records = (
        {
            "event_id": "E1",
            "event_type": "capital_released",
            "persisted_utc": "2026-05-08T20:00:00+00:00",
            "payload": {
                "event_type": "capital_released",
                "symbol": "BTC-USD",
                "asset_class": "CRYPTO",
                "cycle": 8,
                "api_token": "hide-me",
            },
        },
    )

    filtered = filter_trade_lifecycle_replay_records(records, event_type="capital_released", cycle=8)
    normalized = normalize_trade_lifecycle_replay_record(filtered[0])
    summary = summarize_trade_lifecycle_replay_records(filtered)

    assert len(filtered) == 1
    assert normalized["symbol"] == "BTC-USD"
    assert normalized["payload"]["api_token"] == "REDACTED"
    assert summary["capital_releases"] == 1
