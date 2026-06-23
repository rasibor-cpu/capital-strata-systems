from __future__ import annotations

from typing import Iterable

from backend.monitoring.css_alert_models import AlertSeverity
from backend.monitoring.css_alert_service import CSSAlertService
from backend.reconciliation.reconciliation_alerts import (
    build_reconciliation_alert_messages,
)
from backend.reconciliation.reconciliation_models import ReconciliationMismatch


def emit_reconciliation_alerts(
    mismatches: Iterable[ReconciliationMismatch],
    alert_service: CSSAlertService,
) -> int:
    """
    Emit reconciliation mismatch alerts into the CSS runtime alert service.

    This bridge is read-only:
    - no broker calls
    - no trade execution
    - no position modification
    """

    if alert_service is None:
        return 0

    emitted = 0

    for payload in build_reconciliation_alert_messages(mismatches):
        severity = AlertSeverity[payload["severity"]]

        alert_service.emit_risk_alert(
            severity=severity,
            message=payload["message"],
            source=payload["source"],
            metadata={
                "symbol": payload.get("symbol"),
                "source_a": payload.get("source_a"),
                "source_b": payload.get("source_b"),
                "alert_domain": "RECONCILIATION",
            },
        )

        emitted += 1

    return emitted