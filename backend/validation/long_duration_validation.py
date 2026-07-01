from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class LongDurationValidationError(RuntimeError):
    """Fail-closed exception for long-duration validation summaries."""


class LongDurationValidation:
    """Build cumulative paper-validation summaries for long runtime windows."""

    WINDOWS = {
        "6h": timedelta(hours=6),
        "12h": timedelta(hours=12),
        "24h": timedelta(hours=24),
        "48h": timedelta(hours=48),
        "7d": timedelta(days=7),
    }

    def __init__(self, *, artifacts_dir: str | Path | None = None) -> None:
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else None

    def summarize(
        self,
        *,
        events: Sequence[Mapping[str, Any]] | None = None,
        current_sample: Mapping[str, Any] | None = None,
        paper_performance: Mapping[str, Any] | None = None,
        timestamp: str | None = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        now = self._parse_time(ts) or datetime.now(timezone.utc)
        rows = [dict(item) for item in (events or []) if isinstance(item, Mapping)]
        if persist:
            rows = self._read_history() + rows
        if isinstance(current_sample, Mapping):
            sample = dict(current_sample)
            sample.setdefault("timestamp", ts)
            rows.append(sample)
        rows = self._dedupe_rows(rows)
        rows = self._prune(rows, now)
        windows = {name: self._window(rows, now, delta) for name, delta in self.WINDOWS.items()}
        payload = {
            "status": "OK",
            "timestamp": ts,
            "windows": windows,
            "history_count": len(rows),
            "paper_performance_summary": dict(paper_performance) if isinstance(paper_performance, Mapping) else {},
            "advisory_only": True,
            "paper_validation_only": True,
            "execution_allowed": False,
        }
        if persist:
            self._persist(payload)
            self._persist_history(rows)
        return payload

    def _window(self, rows: list[dict[str, Any]], now: datetime, delta: timedelta) -> dict[str, Any]:
        start = now - delta
        window = [row for row in rows if (self._parse_time(row.get("timestamp")) or now) >= start]
        uptime = sum(
            self._float(row.get("runtime_uptime", row.get("uptime_seconds", row.get("cycle_duration_seconds", 0.0))))
            for row in window
        )
        return {
            "uptime": round(uptime, 6),
            "restart_count": int(sum(self._float(row.get("restart_count", 0)) for row in window)),
            "recovery_count": int(sum(self._float(row.get("recovery_count", 0)) for row in window)),
            "validation_degradations": len([row for row in window if str(row.get("validation_state", "")).upper() in {"AMBER", "RED"}]),
            "runtime_health_history": [row.get("runtime_health", "UNKNOWN") for row in window],
            "validation_confidence_history": [row.get("validation_confidence", row.get("confidence_score", "UNKNOWN")) for row in window],
            "artifact_health_history": [row.get("artifact_freshness", "UNKNOWN") for row in window],
            "session_continuity_history": [row.get("session_continuity", "UNKNOWN") for row in window],
            "recommendation_stability_history": [row.get("recommendation_stability", "UNKNOWN") for row in window],
            "sample_count": len(window),
        }

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

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _persist(self, payload: Mapping[str, Any]) -> None:
        if self.artifacts_dir is None:
            return
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (self.artifacts_dir / "long_duration_validation.json").write_text(
            json.dumps(dict(payload), indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )

    def _read_history(self) -> list[dict[str, Any]]:
        if self.artifacts_dir is None:
            return []
        path = self.artifacts_dir / "long_duration_validation_history.json"
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        rows = payload.get("history", payload) if isinstance(payload, dict) else payload
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def _persist_history(self, rows: list[dict[str, Any]]) -> None:
        if self.artifacts_dir is None:
            return
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (self.artifacts_dir / "long_duration_validation_history.json").write_text(
            json.dumps({"history": rows}, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )

    def _prune(self, rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
        cutoff = now - self.WINDOWS["7d"]
        return [row for row in rows if (self._parse_time(row.get("timestamp")) or now) >= cutoff]

    @staticmethod
    def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            key = (str(row.get("timestamp", "")), str(row.get("runtime_cycle", row.get("cycle", ""))))
            if key in seen:
                continue
            seen.add(key)
            result.append(row)
        return result
