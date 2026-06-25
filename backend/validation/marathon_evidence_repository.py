from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable, Mapping


class MarathonEvidenceRepositoryError(RuntimeError):
    """Fail-closed exception for marathon evidence storage."""


class MarathonEvidenceRepository:
    """JSON-backed repository for marathon runtime evidence."""

    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path)

    def create_storage(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.storage_path.exists():
                self._atomic_write(self._empty_run())
            else:
                self.load_run()
        except MarathonEvidenceRepositoryError:
            raise
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise MarathonEvidenceRepositoryError(f"Unable to create evidence storage: {exc}") from exc

    def record_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_event(event)
        run = self.load_run()
        run["events"].append(normalized)
        self._atomic_write(run)
        return normalized

    def record_snapshot(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_snapshot(snapshot)
        run = self.load_run()
        run["snapshots"].append(normalized)
        self._atomic_write(run)
        return normalized

    def load_run(self) -> dict[str, Any]:
        try:
            if not self.storage_path.exists():
                return self._empty_run()
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            return self._validate_run(raw)
        except MarathonEvidenceRepositoryError:
            raise
        except Exception as exc:
            raise MarathonEvidenceRepositoryError(f"Unable to load marathon evidence: {exc}") from exc

    def summarize(self) -> dict[str, Any]:
        run = self.load_run()
        events = list(run["events"])
        snapshots = list(run["snapshots"])

        heartbeat_events = [event for event in events if event["event_type"] == "HEARTBEAT"]
        restart_events = [event for event in events if event["event_type"] == "RESTART"]
        recovery_events = [event for event in events if event["event_type"] == "RECOVERY"]
        alert_events = [event for event in events if event["event_type"] == "ALERT"]
        strategy_events = [event for event in events if event["event_type"] == "STRATEGY_SELECTION"]
        regime_events = [event for event in events if event["event_type"] == "REGIME_TRANSITION"]

        runtime_duration_seconds = round(
            sum(float(snapshot.get("runtime_duration_seconds", snapshot.get("cycle_duration_seconds", 0.0))) for snapshot in snapshots),
            8,
        )
        capital_curve = [float(snapshot.get("equity", 0.0)) for snapshot in snapshots]
        drawdown_history = [float(snapshot.get("drawdown", 0.0)) for snapshot in snapshots]
        decision_latencies = [self._payload_float(snapshot.get("decision_latency_seconds", 0.0)) for snapshot in snapshots]
        runtime_latencies = [self._payload_float(snapshot.get("runtime_latency_seconds", 0.0)) for snapshot in snapshots]
        trade_statistics = self._aggregate_trade_statistics(snapshots)

        return {
            "run_id": run["run_id"],
            "cycle_count": len(snapshots),
            "runtime_duration_seconds": runtime_duration_seconds,
            "heartbeat_history": heartbeat_events,
            "restart_events": restart_events,
            "recovery_events": recovery_events,
            "alerts": alert_events,
            "trade_statistics": trade_statistics,
            "capital_curve": capital_curve,
            "drawdown_history": drawdown_history,
            "strategy_selections": strategy_events,
            "regime_transitions": regime_events,
            "decision_latency_seconds": self._average(decision_latencies),
            "runtime_latency_seconds": self._average(runtime_latencies),
            "events": events,
            "snapshots": snapshots,
            "counts": {
                "heartbeat": len(heartbeat_events),
                "restart": len(restart_events),
                "recovery": len(recovery_events),
                "alert": len(alert_events),
                "strategy_selection": len(strategy_events),
                "regime_transition": len(regime_events),
            },
        }

    def _empty_run(self) -> dict[str, Any]:
        return {
            "run_id": "",
            "created_at": self._utc_now(),
            "updated_at": self._utc_now(),
            "events": [],
            "snapshots": [],
        }

    def _atomic_write(self, payload: Mapping[str, Any]) -> None:
        normalized = self._validate_run(dict(payload))
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.storage_path.parent, delete=False) as tmp:
                json.dump(normalized, tmp, indent=2, sort_keys=True)
                tmp.write("\n")
                tmp_name = tmp.name
            os.replace(tmp_name, self.storage_path)
        except Exception as exc:
            raise MarathonEvidenceRepositoryError(f"Unable to persist marathon evidence: {exc}") from exc

    def _validate_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise MarathonEvidenceRepositoryError("Marathon evidence storage must be a JSON object")

        run_id = str(payload.get("run_id") or "").strip()
        created_at = str(payload.get("created_at") or self._utc_now()).strip()
        updated_at = str(payload.get("updated_at") or self._utc_now()).strip()
        events = payload.get("events", [])
        snapshots = payload.get("snapshots", [])

        if not isinstance(events, list) or not isinstance(snapshots, list):
            raise MarathonEvidenceRepositoryError("Marathon evidence events and snapshots must be lists")

        normalized_events = [self._normalize_event(event) for event in events]
        normalized_snapshots = [self._normalize_snapshot(snapshot) for snapshot in snapshots]

        return {
            "run_id": run_id,
            "created_at": created_at,
            "updated_at": updated_at,
            "events": normalized_events,
            "snapshots": normalized_snapshots,
        }

    def _normalize_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(event, Mapping):
            raise MarathonEvidenceRepositoryError("Event must be a mapping")
        event_type = str(event.get("event_type") or "").strip().upper()
        if not event_type:
            raise MarathonEvidenceRepositoryError("Event type must be non-empty")
        payload = event.get("payload", {})
        if not isinstance(payload, Mapping):
            raise MarathonEvidenceRepositoryError("Event payload must be a mapping")
        return {
            "event_type": event_type,
            "timestamp": str(event.get("timestamp") or self._utc_now()).strip(),
            "payload": self._normalize_mapping(payload),
        }

    def _normalize_snapshot(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(snapshot, Mapping):
            raise MarathonEvidenceRepositoryError("Snapshot must be a mapping")
        cycle_number = int(snapshot.get("cycle_number", 0) or 0)
        timestamp = str(snapshot.get("timestamp") or "").strip()
        if cycle_number <= 0:
            raise MarathonEvidenceRepositoryError("Snapshot cycle_number must be positive")
        if not timestamp:
            raise MarathonEvidenceRepositoryError("Snapshot timestamp must be non-empty")

        normalized = self._normalize_mapping(snapshot)
        normalized["cycle_number"] = cycle_number
        normalized["timestamp"] = timestamp
        for field in (
            "runtime_duration_seconds",
            "cycle_duration_seconds",
            "heartbeat_age_seconds",
            "restart_count",
            "recovery_count",
            "alert_count",
            "trade_count",
            "approved_trades",
            "blocked_trades",
            "capital",
            "equity",
            "drawdown",
            "decision_latency_seconds",
            "runtime_latency_seconds",
            "realized_pnl",
            "unrealized_pnl",
            "portfolio_exposure",
        ):
            if field in normalized:
                normalized[field] = self._payload_float(normalized[field])
        if "trade_statistics" in normalized:
            if not isinstance(normalized["trade_statistics"], Mapping):
                raise MarathonEvidenceRepositoryError("trade_statistics must be a mapping")
            normalized["trade_statistics"] = self._normalize_mapping(normalized["trade_statistics"])
        return normalized

    @staticmethod
    def _normalize_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
        return {str(key): value for key, value in payload.items()}

    @staticmethod
    def _payload_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise MarathonEvidenceRepositoryError("Evidence numeric field must be numeric") from exc

    def _aggregate_trade_statistics(self, snapshots: list[dict[str, Any]]) -> dict[str, Any]:
        totals = defaultdict(float)
        for snapshot in snapshots:
            trade_statistics = snapshot.get("trade_statistics")
            if isinstance(trade_statistics, Mapping):
                for key, value in trade_statistics.items():
                    if isinstance(value, (int, float)):
                        totals[str(key)] += float(value)
            elif isinstance(snapshot, Mapping):
                for key in ("trade_count", "approved_trades", "blocked_trades", "realized_pnl", "unrealized_pnl"):
                    if key in snapshot and isinstance(snapshot[key], (int, float)):
                        totals[key] += float(snapshot[key])
        return {key: round(value, 8) for key, value in sorted(totals.items())}

    @staticmethod
    def _average(values: Iterable[float]) -> float:
        values_list = [float(value) for value in values]
        return round(sum(values_list) / len(values_list), 8) if values_list else 0.0

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
