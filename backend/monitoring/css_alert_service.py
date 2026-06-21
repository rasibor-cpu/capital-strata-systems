import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from backend.monitoring.css_alert_models import CSSAlert, AlertType, AlertSeverity

logger = logging.getLogger(__name__)

class CSSAlertService:
    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir is None:
            self.storage_dir = Path("runtime/alerts")
        else:
            self.storage_dir = Path(storage_dir)
            
        self._ensure_storage_dir()

    def _ensure_storage_dir(self):
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create alert storage directory {self.storage_dir}: {e}")

    def emit_alert(
        self, 
        alert_type: AlertType, 
        severity: AlertSeverity, 
        message: str, 
        source: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> CSSAlert:
        alert = CSSAlert(
            alert_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            alert_type=alert_type,
            severity=severity,
            message=message,
            source=source,
            metadata=metadata or {}
        )
        self._persist_alert(alert)
        return alert

    def emit_engine_alert(self, severity: AlertSeverity, message: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> CSSAlert:
        return self.emit_alert(AlertType.ENGINE, severity, message, source, metadata)

    def emit_trade_alert(self, severity: AlertSeverity, message: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> CSSAlert:
        return self.emit_alert(AlertType.TRADE, severity, message, source, metadata)

    def emit_risk_alert(self, severity: AlertSeverity, message: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> CSSAlert:
        return self.emit_alert(AlertType.RISK, severity, message, source, metadata)

    def emit_broker_alert(self, severity: AlertSeverity, message: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> CSSAlert:
        return self.emit_alert(AlertType.BROKER, severity, message, source, metadata)

    def emit_system_alert(self, severity: AlertSeverity, message: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> CSSAlert:
        return self.emit_alert(AlertType.SYSTEM, severity, message, source, metadata)

    def heartbeat(self, source: str, metadata: Optional[Dict[str, Any]] = None) -> CSSAlert:
        return self.emit_system_alert(AlertSeverity.INFO, "CSSAlertService Heartbeat", source, metadata)

    def _persist_alert(self, alert: CSSAlert):
        try:
            # e.g., 20260621T120000Z_ENGINE_INFO_uuid.json
            safe_ts = alert.timestamp.replace(":", "").replace("-", "").split(".")[0]
            filename = f"{safe_ts}_{alert.alert_type.value}_{alert.severity.value}_{alert.alert_id}.json"
            filepath = self.storage_dir / filename
            
            data = {
                "alert_id": alert.alert_id,
                "timestamp": alert.timestamp,
                "alert_type": alert.alert_type.value,
                "severity": alert.severity.value,
                "message": alert.message,
                "source": alert.source,
                "metadata": alert.metadata
            }
            
            with filepath.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist alert {alert.alert_id}: {e}")
