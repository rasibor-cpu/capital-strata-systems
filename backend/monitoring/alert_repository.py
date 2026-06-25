from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AlertRepositoryError(Exception):
    """Raised when alert storage is unreadable or corrupt."""


class AlertRepository:
    """Canonical repository for critical runtime and trading alerts."""

    CRITICAL_EVENT_TYPES = {
        "RUNTIME_FAILURE",
        "SUPERVISOR_RECOVERY",
        "BROKER_DISCONNECT",
        "TRADE_REJECTED",
        "RISK_GATE_BLOCK",
        "LIVE_MODE_BLOCKED",
        "DATA_UNAVAILABLE",
        "PNL_DRAWDOWN",
        "HEARTBEAT_STALE",
    }

    SEVERITIES = {"INFO", "WARNING", "CRITICAL"}

    def __init__(self, storage_dir: str | None = None) -> None:
        self.storage_dir = Path(storage_dir or "runtime/alerts")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def persist_alert(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_payload(payload)
        dedupe_key = str(normalized["dedupe_key"] or "").strip()

        if dedupe_key:
            existing = self._load_existing_by_dedupe_key(dedupe_key)
            if existing is not None:
                return existing

        alert_id = str(normalized.get("alert_id") or uuid.uuid4())
        timestamp = normalized.get("timestamp") or self._utc_timestamp()
        record = {
            "alert_id": alert_id,
            "timestamp": timestamp,
            "severity": normalized["severity"],
            "event_type": normalized["event_type"],
            "source": normalized["source"],
            "message": normalized["message"],
            "details": normalized["details"],
            "acknowledged": bool(normalized.get("acknowledged", False)),
            "dedupe_key": dedupe_key,
        }

        storage_path = self.storage_dir / f"{alert_id}.json"
        try:
            with storage_path.open("w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2, sort_keys=True)
        except Exception as exc:  # pragma: no cover - defensive file failure
            raise AlertRepositoryError(f"Unable to persist alert: {exc}") from exc

        return record

    def load_alerts(self) -> list[dict[str, Any]]:
        if not self.storage_dir.exists():
            return []

        alerts: list[dict[str, Any]] = []
        for path in sorted(self.storage_dir.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except Exception as exc:
                raise AlertRepositoryError(f"Corrupt storage: {path.name}") from exc

            if not isinstance(payload, dict):
                raise AlertRepositoryError(f"Corrupt storage: {path.name}")

            alerts.append(self._normalize_payload(payload, require_existing=True))

        return sorted(alerts, key=lambda item: item["timestamp"], reverse=True)

    def list_recent_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        alerts = self.load_alerts()
        return alerts[: max(0, int(limit))]

    def list_critical_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        alerts = [
            alert for alert in self.load_alerts() if alert.get("severity") == "CRITICAL"
        ]
        return alerts[: max(0, int(limit))]

    def acknowledge_alert(self, alert_id: str) -> bool:
        alert_id = str(alert_id or "").strip()
        if not alert_id:
            return False

        alerts = self.load_alerts()
        for alert in alerts:
            if alert.get("alert_id") == alert_id:
                updated = dict(alert)
                updated["acknowledged"] = True
                self._write_record(updated)
                return True

        return False

    def persist_decision_alerts(
        self,
        canonical_decision: dict[str, Any],
        *,
        previous_decision: dict[str, Any] | None = None,
        rejection_streak: int = 0,
        confidence_threshold: float = 0.45,
        learning_confidence_threshold: float = 0.5,
        concentration_limit: float = 0.7,
    ) -> list[dict[str, Any]]:
        if not isinstance(canonical_decision, dict):
            raise AlertRepositoryError("canonical_decision must be a dictionary")

        emitted: list[dict[str, Any]] = []
        symbol = str(canonical_decision.get("symbol") or "UNKNOWN").strip().upper() or "UNKNOWN"
        strategy = str(canonical_decision.get("selected_strategy") or "UNKNOWN").strip() or "UNKNOWN"
        market_regime = str(canonical_decision.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN"
        decision = str(canonical_decision.get("entry_decision") or "UNKNOWN").strip().upper() or "UNKNOWN"
        confidence = float(canonical_decision.get("confidence", 0.0) or 0.0)
        concentration_score = float(canonical_decision.get("concentration_score", 0.0) or 0.0)
        learning_confidence = float((canonical_decision.get("learning_context") or {}).get("confidence", confidence) or 0.0)
        exit_action = str((canonical_decision.get("exit_plan") or {}).get("action") or "HOLD").strip().upper() or "HOLD"

        if confidence < confidence_threshold:
            emitted.append(
                self.persist_alert(
                    {
                        "severity": "WARNING",
                        "event_type": "TRADE_REJECTED",
                        "source": "canonical_decision",
                        "message": f"Strategy confidence low for {strategy} on {symbol}",
                        "details": {
                            "confidence": confidence,
                            "threshold": confidence_threshold,
                            "strategy": strategy,
                            "symbol": symbol,
                        },
                        "dedupe_key": f"DECISION_CONFIDENCE_LOW:{symbol}:{strategy}:{market_regime}",
                    }
                )
            )

        if isinstance(previous_decision, dict):
            previous_regime = str(previous_decision.get("market_regime") or "").strip().upper()
            if previous_regime and previous_regime != market_regime:
                emitted.append(
                    self.persist_alert(
                        {
                            "severity": "INFO",
                            "event_type": "DATA_UNAVAILABLE",
                            "source": "canonical_decision",
                            "message": f"Market regime changed from {previous_regime} to {market_regime}",
                            "details": {
                                "previous_regime": previous_regime,
                                "current_regime": market_regime,
                                "symbol": symbol,
                            },
                            "dedupe_key": f"REGIME_CHANGE:{symbol}:{previous_regime}:{market_regime}",
                        }
                    )
                )

        if decision != "ALLOW" and rejection_streak >= 3:
            emitted.append(
                self.persist_alert(
                    {
                        "severity": "WARNING",
                        "event_type": "TRADE_REJECTED",
                        "source": "canonical_decision",
                        "message": f"Repeated trade rejections detected for {symbol}",
                        "details": {
                            "entry_decision": decision,
                            "rejection_streak": int(rejection_streak),
                        },
                        "dedupe_key": f"REPEATED_REJECTIONS:{symbol}:{rejection_streak}",
                    }
                )
            )

        if learning_confidence < learning_confidence_threshold:
            emitted.append(
                self.persist_alert(
                    {
                        "severity": "WARNING",
                        "event_type": "DATA_UNAVAILABLE",
                        "source": "canonical_decision",
                        "message": f"Learning confidence degraded for {symbol}",
                        "details": {
                            "learning_confidence": learning_confidence,
                            "threshold": learning_confidence_threshold,
                        },
                        "dedupe_key": f"LEARNING_CONFIDENCE_LOW:{symbol}:{strategy}",
                    }
                )
            )

        if concentration_score > concentration_limit:
            emitted.append(
                self.persist_alert(
                    {
                        "severity": "CRITICAL",
                        "event_type": "RISK_GATE_BLOCK",
                        "source": "canonical_decision",
                        "message": f"Portfolio concentration exceeded for {symbol}",
                        "details": {
                            "concentration_score": concentration_score,
                            "limit": concentration_limit,
                            "symbol": symbol,
                        },
                        "dedupe_key": f"CONCENTRATION_LIMIT:{symbol}:{strategy}:{market_regime}",
                    }
                )
            )

        if exit_action in {"STOP_LOSS", "REDUCE", "TAKE_PROFIT"}:
            emitted.append(
                self.persist_alert(
                    {
                        "severity": "WARNING",
                        "event_type": "TRADE_REJECTED",
                        "source": "canonical_decision",
                        "message": f"Adaptive exit override active ({exit_action}) for {symbol}",
                        "details": {
                            "exit_action": exit_action,
                            "entry_decision": decision,
                        },
                        "dedupe_key": f"ADAPTIVE_EXIT_OVERRIDE:{symbol}:{exit_action}",
                    }
                )
            )

        return emitted

    def _normalize_payload(self, payload: dict[str, Any], require_existing: bool = False) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AlertRepositoryError("Alert payload must be a dictionary")

        severity = str(payload.get("severity") or "").strip().upper()
        if severity not in self.SEVERITIES:
            raise AlertRepositoryError("Invalid severity")

        event_type = str(payload.get("event_type") or "").strip().upper()
        if not event_type:
            raise AlertRepositoryError("Missing event_type")

        source = str(payload.get("source") or "").strip()
        if not source:
            raise AlertRepositoryError("Missing source")

        message = str(payload.get("message") or "").strip()
        if not message:
            raise AlertRepositoryError("Missing message")

        details = payload.get("details")
        if details is None:
            details = {}
        if not isinstance(details, dict):
            raise AlertRepositoryError("Invalid details")

        dedupe_key = str(payload.get("dedupe_key") or "").strip()
        if not dedupe_key and not require_existing:
            dedupe_key = f"{event_type}:{source}:{message}"

        return {
            "alert_id": str(payload.get("alert_id") or ""),
            "timestamp": str(payload.get("timestamp") or self._utc_timestamp()),
            "severity": severity,
            "event_type": event_type,
            "source": source,
            "message": message,
            "details": details,
            "acknowledged": bool(payload.get("acknowledged", False)),
            "dedupe_key": dedupe_key,
        }

    def _load_existing_by_dedupe_key(self, dedupe_key: str) -> dict[str, Any] | None:
        for alert in self.load_alerts():
            if alert.get("dedupe_key") == dedupe_key:
                return alert
        return None

    def _write_record(self, record: dict[str, Any]) -> None:
        storage_path = self.storage_dir / f"{record['alert_id']}.json"
        with storage_path.open("w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)

    def _utc_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()


class AlertCentreCompatibilityAdapter:
    """Compatibility adapter for mobile/runtime alert consumers."""

    def __init__(self, repository: AlertRepository) -> None:
        self.repository = repository

    def build_payload(self, limit: int = 50) -> list[dict[str, Any]]:
        alerts = self.repository.list_recent_alerts(limit=limit)
        return [
            {
                "alert_id": alert["alert_id"],
                "timestamp": alert["timestamp"],
                "severity": alert["severity"],
                "event_type": alert["event_type"],
                "source": alert["source"],
                "message": alert["message"],
                "details": alert["details"],
                "acknowledged": alert["acknowledged"],
                "dedupe_key": alert["dedupe_key"],
            }
            for alert in alerts
        ]
