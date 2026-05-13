from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


ALERT_PAYLOAD_VERSION = "css.alerts.v1"


@dataclass(frozen=True)
class CSSAlert:
    alert_id: str
    severity: str
    category: str
    message: str
    generated_utc: str
    source: str = "dashboard.runtime.alerting_layer"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_alert_payload(frontend_payload: Mapping[str, Any]) -> dict[str, Any]:
    sections = frontend_payload.get("sections", {})
    if not isinstance(sections, Mapping):
        sections = {}

    alerts: list[CSSAlert] = []
    generated = datetime.now(timezone.utc).isoformat()

    broker = _mapping(sections.get("broker"))
    if broker.get("connected") is False:
        alerts.append(_alert("broker_disconnect", "warning", "broker", "Broker is disconnected", generated))
    if broker.get("missing_credentials") is True:
        alerts.append(_alert("credential_missing", "error", "security", "Broker credentials are missing", generated))

    reconciliation = _mapping(sections.get("broker_reconciliation"))
    if str(reconciliation.get("status", "")).upper() in {"DIVERGED", "BROKER_DEGRADED"}:
        alerts.append(_alert("reconciliation_drift", "error", "broker", "Broker reconciliation drift detected", generated))

    risk = _mapping(sections.get("risk"))
    breaches = risk.get("risk_limits_breached")
    if isinstance(breaches, list) and breaches:
        alerts.append(_alert("risk_breach", "error", "risk", "Risk limit breach detected", generated))
    if _safe_float(risk.get("current_drawdown_pct")) >= 2.0:
        alerts.append(_alert("drawdown", "warning", "risk", "Drawdown threshold reached", generated))

    governance = _mapping(sections.get("governance"))
    if governance.get("session_locked") is True:
        alerts.append(_alert("session_lock", "warning", "session", "Session is locked", generated))
    if governance.get("defensive_mode_active") is True:
        alerts.append(_alert("defensive_mode", "warning", "governance", "Defensive mode is active", generated))

    execution = _mapping(sections.get("execution"))
    if _safe_int(execution.get("rejected_trade_count")) > 0:
        alerts.append(_alert("rejected_orders", "warning", "execution", "Rejected trades require review", generated))

    return {
        "payload_version": ALERT_PAYLOAD_VERSION,
        "generated_utc": generated,
        "alert_count": len(alerts),
        "alerts": [alert.as_dict() for alert in alerts],
    }


def _alert(alert_id: str, severity: str, category: str, message: str, generated: str) -> CSSAlert:
    return CSSAlert(
        alert_id=alert_id,
        severity=severity,
        category=category,
        message=message,
        generated_utc=generated,
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0
