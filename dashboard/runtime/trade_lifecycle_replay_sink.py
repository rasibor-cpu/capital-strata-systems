from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


TRADE_LIFECYCLE_REPLAY_SINK_VERSION = "css.trade_lifecycle.replay_sink.v1"
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


class TradeLifecycleReplaySinkError(RuntimeError):
    pass


class TradeLifecycleReplaySink:
    def __init__(
        self,
        path: str | Path,
        *,
        strict: bool = False,
    ) -> None:
        self.path = Path(path)
        self.strict = strict

    def record(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        record = self._build_record(payload)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":"), default=str) + "\n")
            return {
                "ok": True,
                "event_id": record["event_id"],
                "path": str(self.path),
            }
        except Exception as exc:
            if self.strict:
                raise TradeLifecycleReplaySinkError(
                    f"Failed to persist trade lifecycle replay event: {exc}"
                ) from exc
            return {
                "ok": False,
                "event_id": record["event_id"],
                "path": str(self.path),
                "error": str(exc),
            }

    def record_many(self, payloads: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
        return tuple(self.record(payload) for payload in payloads)

    def load_recent(self, limit: int = 100) -> tuple[dict[str, Any], ...]:
        return load_trade_lifecycle_replay_events(self.path, limit=limit)

    def _build_record(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        safe_payload = _json_safe(payload)
        event_type = str(safe_payload.get("event_type", "unknown_lifecycle_event"))
        event_id = str(safe_payload.get("event_id") or _event_id(safe_payload))
        return {
            "sink_payload_version": TRADE_LIFECYCLE_REPLAY_SINK_VERSION,
            "event_id": event_id,
            "event_type": event_type,
            "persisted_utc": datetime.now(timezone.utc).isoformat(),
            "position_id": str(safe_payload.get("position_id", "")),
            "symbol": str(safe_payload.get("symbol", "")),
            "asset_class": str(safe_payload.get("asset_class", "")),
            "mode": str(safe_payload.get("mode", "paper")),
            "session_id": str(safe_payload.get("session_id", "")),
            "payload": safe_payload,
        }


def load_trade_lifecycle_replay_events(
    path: str | Path,
    *,
    limit: int = 100,
) -> tuple[dict[str, Any], ...]:
    source_path = Path(path)
    try:
        lines = source_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ()
    except Exception:
        return ()

    events: list[dict[str, Any]] = []
    for line in reversed(lines):
        try:
            record = json.loads(line)
        except Exception:
            continue
        if isinstance(record, dict):
            events.append(record)
        if len(events) >= limit:
            break
    return tuple(reversed(events))


def _event_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()


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
