from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dashboard.runtime.replay_correlation import correlation_key, create_lifecycle_id
from dashboard.runtime.replay_event_envelope import is_replay_event_envelope


TRADE_LIFECYCLE_REPLAY_VIEWER_VERSION = "css.trade_lifecycle.replay_viewer.v1"
DEFAULT_TRADE_LIFECYCLE_REPLAY_PATH = (
    Path(__file__).resolve().parents[2] / "artifacts" / "css_trade_lifecycle_replay.jsonl"
)
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "credential",
    "private",
    "pem",
    "authorization",
    "bearer",
)
_SUMMARY_EVENT_KEYS = {
    "position_exit_booked": "exits_booked",
    "defensive_reduction_applied": "defensive_reductions",
    "realized_pnl_handoff": "realized_pnl_handoffs",
    "capital_released": "capital_releases",
    "locked_profit_updated": "locked_profit_updates",
    "lifecycle_audit_payload_created": "lifecycle_audit_payloads",
}


def get_trade_lifecycle_replay_payload(
    path: str | Path = DEFAULT_TRADE_LIFECYCLE_REPLAY_PATH,
    *,
    event_type: str = "",
    symbol: str = "",
    asset_class: str = "",
    cycle: int | str | None = None,
    correlation_id: str = "",
    subsystem: str = "",
    start_utc: str = "",
    end_utc: str = "",
    limit: int = 250,
) -> dict[str, Any]:
    source_path = Path(path)
    records, malformed_lines = load_trade_lifecycle_replay_records(source_path)
    filtered = filter_trade_lifecycle_replay_records(
        records,
        event_type=event_type,
        symbol=symbol,
        asset_class=asset_class,
        cycle=cycle,
        correlation_id=correlation_id,
        subsystem=subsystem,
        start_utc=start_utc,
        end_utc=end_utc,
    )
    safe_limit = max(0, int(limit or 0))
    limited = tuple(filtered[-safe_limit:]) if safe_limit else ()

    return {
        "payload_version": TRADE_LIFECYCLE_REPLAY_VIEWER_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source_path),
        "source_exists": source_path.exists(),
        "read_only": True,
        "filters": {
            "event_type": str(event_type or ""),
            "symbol": str(symbol or ""),
            "asset_class": str(asset_class or ""),
            "cycle": "" if cycle is None else str(cycle),
            "correlation_id": str(correlation_id or ""),
            "subsystem": str(subsystem or ""),
            "start_utc": str(start_utc or ""),
            "end_utc": str(end_utc or ""),
            "limit": safe_limit,
        },
        "malformed_line_count": malformed_lines,
        "total_loaded_events": len(records),
        "filtered_event_count": len(filtered),
        "returned_event_count": len(limited),
        "summary": summarize_trade_lifecycle_replay_records(filtered, malformed_lines=malformed_lines),
        "events": [normalize_trade_lifecycle_replay_record(record) for record in limited],
    }


def load_trade_lifecycle_replay_records(
    path: str | Path,
) -> tuple[tuple[dict[str, Any], ...], int]:
    source_path = Path(path)
    try:
        lines = source_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return (), 0
    except Exception:
        return (), 0

    records: list[dict[str, Any]] = []
    malformed_lines = 0
    for line in lines:
        try:
            record = json.loads(line)
        except Exception:
            malformed_lines += 1
            continue
        if isinstance(record, dict):
            records.append(_json_safe(record))
        else:
            malformed_lines += 1
    return tuple(records), malformed_lines


def filter_trade_lifecycle_replay_records(
    records: tuple[dict[str, Any], ...],
    *,
    event_type: str = "",
    symbol: str = "",
    asset_class: str = "",
    cycle: int | str | None = None,
    correlation_id: str = "",
    subsystem: str = "",
    start_utc: str = "",
    end_utc: str = "",
) -> tuple[dict[str, Any], ...]:
    event_type_filter = str(event_type or "").strip().lower()
    symbol_filter = str(symbol or "").strip().upper()
    asset_filter = str(asset_class or "").strip().upper()
    cycle_filter = "" if cycle in (None, "") else str(cycle)
    correlation_filter = str(correlation_id or "").strip().upper()
    subsystem_filter = str(subsystem or "").strip().lower()
    start_dt = _parse_timestamp(start_utc)
    end_dt = _parse_timestamp(end_utc)

    filtered: list[dict[str, Any]] = []
    for record in records:
        normalized = normalize_trade_lifecycle_replay_record(record)
        if event_type_filter and normalized["event_type"].lower() != event_type_filter:
            continue
        if symbol_filter and normalized["symbol"].upper() != symbol_filter:
            continue
        if asset_filter and normalized["asset_class"].upper() != asset_filter:
            continue
        if cycle_filter and str(normalized["cycle"]) != cycle_filter:
            continue
        if correlation_filter and normalized["correlation_id"].upper() != correlation_filter:
            continue
        if subsystem_filter and normalized["subsystem"].lower() != subsystem_filter:
            continue

        event_dt = _parse_timestamp(normalized["timestamp_utc"])
        if start_dt and event_dt and event_dt < start_dt:
            continue
        if end_dt and event_dt and event_dt > end_dt:
            continue
        filtered.append(record)
    return tuple(filtered)


def summarize_trade_lifecycle_replay_records(
    records: tuple[dict[str, Any], ...],
    *,
    malformed_lines: int = 0,
) -> dict[str, Any]:
    summary = {
        "total_events": len(records),
        "exits_booked": 0,
        "defensive_reductions": 0,
        "realized_pnl_handoffs": 0,
        "capital_releases": 0,
        "locked_profit_updates": 0,
        "lifecycle_audit_payloads": 0,
        "malformed_lines": malformed_lines,
        "by_event_type": {},
        "by_asset_class": {},
        "by_symbol": {},
        "by_subsystem": {},
        "by_correlation_id": {},
    }

    for record in records:
        normalized = normalize_trade_lifecycle_replay_record(record)
        event_type = normalized["event_type"]
        asset_class = normalized["asset_class"] or "UNKNOWN"
        symbol = normalized["symbol"] or "UNKNOWN"
        subsystem = normalized["subsystem"] or "legacy"
        correlation_id = normalized["correlation_id"] or "UNKNOWN"
        summary["by_event_type"][event_type] = summary["by_event_type"].get(event_type, 0) + 1
        summary["by_asset_class"][asset_class] = summary["by_asset_class"].get(asset_class, 0) + 1
        summary["by_symbol"][symbol] = summary["by_symbol"].get(symbol, 0) + 1
        summary["by_subsystem"][subsystem] = summary["by_subsystem"].get(subsystem, 0) + 1
        summary["by_correlation_id"][correlation_id] = (
            summary["by_correlation_id"].get(correlation_id, 0) + 1
        )
        mapped_key = _SUMMARY_EVENT_KEYS.get(event_type)
        if mapped_key:
            summary[mapped_key] += 1
    return summary


def normalize_trade_lifecycle_replay_record(record: Mapping[str, Any]) -> dict[str, Any]:
    safe_record = _json_safe(record)
    raw_payload = safe_record.get("payload") if isinstance(safe_record.get("payload"), Mapping) else {}
    envelope = safe_record if is_replay_event_envelope(safe_record) else {}
    if not envelope and is_replay_event_envelope(raw_payload):
        envelope = raw_payload

    payload = (
        envelope.get("payload")
        if envelope and isinstance(envelope.get("payload"), Mapping)
        else raw_payload
    )
    identity_payload = payload if isinstance(payload, Mapping) else {}
    event_type = str(
        envelope.get("event_type")
        or safe_record.get("event_type")
        or identity_payload.get("event_type")
        or ""
    )
    symbol = str(
        envelope.get("symbol")
        or safe_record.get("symbol")
        or identity_payload.get("symbol")
        or ""
    )
    asset_class = str(
        envelope.get("asset_class")
        or safe_record.get("asset_class")
        or identity_payload.get("asset_class")
        or ""
    )
    cycle = (
        envelope.get("cycle")
        or safe_record.get("cycle")
        or identity_payload.get("cycle")
        or ""
    )
    mode = str(
        safe_record.get("mode")
        or envelope.get("broker_mode")
        or identity_payload.get("broker_mode")
        or identity_payload.get("mode")
        or "paper"
    )
    broker_mode = str(
        safe_record.get("broker_mode")
        or envelope.get("broker_mode")
        or identity_payload.get("broker_mode")
        or identity_payload.get("mode")
        or ""
    )
    seed_payload = {
        "session_id": safe_record.get("session_id") or identity_payload.get("session_id"),
        "lifecycle_id": envelope.get("lifecycle_id")
        or safe_record.get("lifecycle_id")
        or identity_payload.get("lifecycle_id"),
        "position_id": safe_record.get("position_id") or identity_payload.get("position_id"),
        "symbol": symbol,
        "asset_class": asset_class,
        "cycle": cycle,
    }
    lifecycle_id = str(seed_payload["lifecycle_id"] or create_lifecycle_id(seed_payload))
    correlation_id = str(
        envelope.get("correlation_id")
        or safe_record.get("correlation_id")
        or identity_payload.get("correlation_id")
        or correlation_key({**seed_payload, "lifecycle_id": lifecycle_id})
    )
    timestamp = str(
        envelope.get("timestamp_utc")
        or identity_payload.get("timestamp_utc")
        or safe_record.get("timestamp_utc")
        or safe_record.get("persisted_utc")
        or ""
    )
    return {
        "schema_version": str(envelope.get("schema_version") or safe_record.get("schema_version") or "legacy"),
        "correlation_id": correlation_id,
        "lifecycle_id": lifecycle_id,
        "event_id": str(envelope.get("event_id") or safe_record.get("event_id", "")),
        "parent_event_id": str(envelope.get("parent_event_id") or safe_record.get("parent_event_id", "")),
        "event_type": event_type,
        "subsystem": str(envelope.get("subsystem") or safe_record.get("subsystem") or ""),
        "timestamp_utc": timestamp,
        "persisted_utc": str(safe_record.get("persisted_utc", "")),
        "position_id": str(safe_record.get("position_id") or identity_payload.get("position_id") or ""),
        "symbol": symbol,
        "asset_class": asset_class,
        "mode": mode,
        "broker": str(safe_record.get("broker") or envelope.get("broker") or identity_payload.get("broker", "")),
        "broker_mode": broker_mode,
        "engine_mode": str(
            safe_record.get("engine_mode")
            or envelope.get("engine_mode")
            or identity_payload.get("engine_mode", "")
        ),
        "cycle": cycle,
        "reason": str(identity_payload.get("reason", safe_record.get("reason", ""))),
        "classification": str(
            identity_payload.get("classification", safe_record.get("classification", ""))
        ),
        "realized_pnl": identity_payload.get("realized_pnl", safe_record.get("realized_pnl", 0.0)),
        "payload": _json_safe(identity_payload),
    }


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = str(key)
            if _is_sensitive_key(safe_key):
                safe[safe_key] = "REDACTED"
            else:
                safe[safe_key] = _json_safe(item)
        return safe
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)
