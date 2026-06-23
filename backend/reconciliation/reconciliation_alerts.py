from __future__ import annotations

from typing import Iterable

from backend.reconciliation.reconciliation_models import (
    ReconciliationMismatch,
)
from backend.reconciliation.reconciliation_severity import (
    CRITICAL,
    WARNING,
)


def build_reconciliation_alert_messages(
    mismatches: Iterable[ReconciliationMismatch],
) -> list[dict[str, str]]:
    """
    Convert reconciliation mismatches into alert-ready message payloads.

    This is read-only:
    - no broker calls
    - no trade execution
    - no position modification
    """

    alerts: list[dict[str, str]] = []

    for mismatch in mismatches or []:
        severity = str(mismatch.severity or "").upper()

        if severity not in {WARNING, CRITICAL}:
            continue

        alerts.append(
            {
                "severity": severity,
                "message": (
                    f"Position reconciliation mismatch for "
                    f"{mismatch.symbol}: {mismatch.details}"
                ),
                "source": "backend.reconciliation",
                "symbol": mismatch.symbol,
                "source_a": mismatch.source_a,
                "source_b": mismatch.source_b,
            }
        )

    return alerts