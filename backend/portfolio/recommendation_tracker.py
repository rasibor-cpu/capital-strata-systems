from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Mapping


class RecommendationTrackerError(RuntimeError):
    """Fail-closed exception for recommendation tracking persistence."""


class RecommendationTracker:
    """Track advisory recommendations and later outcome proxies."""

    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        self.path = os.path.join(storage_dir, "recommendation_tracker.json")

    def record_recommendation(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(snapshot, Mapping):
            return self._status("DATA UNAVAILABLE", "recommendation_snapshot_malformed")
        rows = self._read_rows()
        record = dict(snapshot)
        record.setdefault("id", f"recommendation-{len(rows) + 1}")
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        record.setdefault("advisory_only", True)
        record.setdefault("outcome", None)
        rows.append(record)
        self._write_rows(rows)
        return {"status": "OK", "record": record, "count": len(rows), "advisory_only": True}

    def evaluate_outcome(self, recommendation_id: str, outcome: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(outcome, Mapping):
            return self._status("DATA UNAVAILABLE", "outcome_malformed")
        rows = self._read_rows()
        for row in rows:
            if str(row.get("id")) == str(recommendation_id):
                evaluation = self._evaluate(row, outcome)
                row["outcome"] = dict(outcome)
                row["evaluation"] = evaluation
                self._write_rows(rows)
                return {"status": "OK", "evaluation": evaluation, "advisory_only": True}
        return self._status("DATA UNAVAILABLE", "recommendation_not_found")

    def summary(self) -> dict[str, Any]:
        rows = self._read_rows()
        evaluated = [row for row in rows if isinstance(row.get("evaluation"), dict)]
        hits = sum(1 for row in evaluated if row["evaluation"].get("hit") is True)
        avoided_loss = sum(float(row["evaluation"].get("avoided_loss_proxy", 0.0) or 0.0) for row in evaluated)
        missed = sum(float(row["evaluation"].get("missed_opportunity_proxy", 0.0) or 0.0) for row in evaluated)
        return {
            "status": "OK",
            "total_recommendations": len(rows),
            "evaluated_recommendations": len(evaluated),
            "hit_rate": round((hits / len(evaluated)) * 100.0, 6) if evaluated else None,
            "avoided_loss_proxy": round(avoided_loss, 6),
            "missed_opportunity_proxy": round(missed, 6),
            "advisory_only": True,
        }

    @staticmethod
    def _evaluate(recommendation: Mapping[str, Any], outcome: Mapping[str, Any]) -> dict[str, Any]:
        action = str(recommendation.get("adaptive_recommendation", recommendation.get("recommendation", ""))).upper()
        realized_return = RecommendationTracker._float(outcome.get("realized_return", outcome.get("return", 0.0)))
        drawdown = abs(RecommendationTracker._float(outcome.get("max_drawdown", outcome.get("drawdown", 0.0))))
        defensive = action in {"PAUSE_NEW_TRADES", "REDUCE_RISK", "MAINTAIN"}
        aggressive = action == "INCREASE_RISK"
        hit = (defensive and (realized_return <= 0.0 or drawdown >= 0.05)) or (aggressive and realized_return > 0.0)
        avoided_loss = max(0.0, -realized_return) if defensive else 0.0
        missed_opportunity = max(0.0, realized_return) if defensive and realized_return > 0.0 else 0.0
        return {
            "hit": hit,
            "avoided_loss_proxy": round(avoided_loss, 6),
            "missed_opportunity_proxy": round(missed_opportunity, 6),
            "realized_return": round(realized_return, 6),
            "max_drawdown": round(drawdown, 6),
        }

    def _read_rows(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, list):
                return []
            return [row for row in payload if isinstance(row, dict)]
        except Exception:
            return []

    def _write_rows(self, rows: list[dict[str, Any]]) -> None:
        os.makedirs(self.storage_dir, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=2, sort_keys=True)

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _status(status: str, reason: str) -> dict[str, Any]:
        return {"status": status, "reason": reason, "advisory_only": True}
