from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class RuntimeHealthTrendError(RuntimeError):
    """Fail-closed exception for runtime health trend analysis."""


class RuntimeHealthTrend:
    """Maintain rolling operational health trends for advisory validation."""

    WINDOWS = {"1h": timedelta(hours=1), "6h": timedelta(hours=6), "24h": timedelta(hours=24)}
    ORDER = {"GREEN": 0, "AMBER": 1, "RED": 2, "UNKNOWN": 3}

    def __init__(self, *, artifacts_dir: str | Path | None = None) -> None:
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else None
        self.history_path = self.artifacts_dir / "runtime_health_trend_history.json" if self.artifacts_dir else None

    def evaluate(
        self,
        *,
        runtime_health: Mapping[str, Any] | None,
        validation_readiness: Mapping[str, Any] | None,
        artifact_freshness: Mapping[str, Any] | None,
        session_continuity: Mapping[str, Any] | None,
        portfolio_decision: Mapping[str, Any] | None,
        portfolio_lifecycle: Mapping[str, Any] | None,
        history: list[Mapping[str, Any]] | None = None,
        timestamp: str | None = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        sample = {
            "timestamp": ts,
            "runtime_health": self._status(runtime_health, "runtime_health", "overall_operational_health"),
            "validation_readiness": self._readiness(validation_readiness),
            "artifact_freshness": self._status(artifact_freshness, "freshness_status"),
            "session_continuity": self._session(session_continuity),
            "portfolio_decision": self._status(portfolio_decision, "overall_status", "status"),
            "portfolio_lifecycle": self._status(portfolio_lifecycle, "portfolio_state", "lifecycle_status"),
        }
        rows = [dict(item) for item in (history if history is not None else self._read_history()) if isinstance(item, Mapping)]
        rows.append(sample)
        now = self._parse_time(ts) or datetime.now(timezone.utc)
        trends = {name: self._window(rows, now, delta) for name, delta in self.WINDOWS.items()}
        payload = {
            "status": "OK",
            "current": sample,
            "trends": trends,
            "history_count": len(rows),
            "timestamp": ts,
            "advisory_only": True,
            "execution_allowed": False,
        }
        if persist:
            self._persist(rows, now)
        return payload

    def _window(self, rows: list[dict[str, Any]], now: datetime, delta: timedelta) -> dict[str, Any]:
        start = now - delta
        window = [row for row in rows if (self._parse_time(row.get("timestamp")) or now) >= start]
        fields = ["runtime_health", "validation_readiness", "artifact_freshness", "session_continuity", "portfolio_decision", "portfolio_lifecycle"]
        return {
            "sample_count": len(window),
            "statuses": {field: self._worst([str(row.get(field, "UNKNOWN")).upper() for row in window]) for field in fields},
            "degradation_count": len([row for row in window if any(str(row.get(field, "")).upper() in {"AMBER", "RED", "NOT_READY"} for field in fields)]),
        }

    @classmethod
    def _worst(cls, statuses: list[str]) -> str:
        if not statuses:
            return "UNKNOWN"
        normalized = [item if item in cls.ORDER else "UNKNOWN" for item in statuses]
        return max(normalized, key=lambda item: cls.ORDER.get(item, 3))

    @staticmethod
    def _status(payload: Mapping[str, Any] | None, *keys: str) -> str:
        if not isinstance(payload, Mapping):
            return "UNKNOWN"
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return str(value).upper()
        return "UNKNOWN"

    @staticmethod
    def _readiness(payload: Mapping[str, Any] | None) -> str:
        status = RuntimeHealthTrend._status(payload, "readiness_status")
        return {"READY": "GREEN", "READY_WITH_CAUTION": "AMBER", "NOT_READY": "RED"}.get(status, status)

    @staticmethod
    def _session(payload: Mapping[str, Any] | None) -> str:
        status = RuntimeHealthTrend._status(payload, "session_continuity_status")
        return {"ACTIVE": "GREEN", "RESUMED": "GREEN", "EXPIRING_SOON": "AMBER", "EXPIRED": "RED", "REAUTH_REQUIRED": "RED"}.get(status, status)

    def _read_history(self) -> list[dict[str, Any]]:
        if self.history_path is None or not self.history_path.exists():
            return []
        try:
            payload = json.loads(self.history_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        rows = payload.get("history", payload) if isinstance(payload, dict) else payload
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _persist(self, rows: list[dict[str, Any]], now: datetime) -> None:
        if self.history_path is None:
            return
        cutoff = now - self.WINDOWS["24h"]
        kept = [row for row in rows if (self._parse_time(row.get("timestamp")) or now) >= cutoff]
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(json.dumps({"history": kept}, indent=2, sort_keys=True), encoding="utf-8")
