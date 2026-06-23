from __future__ import annotations

from typing import List

from backend.reconciliation.position_reconciliation import (
    PositionReconciliationReport,
)
from backend.reconciliation.reconciliation_models import (
    ReconciliationMismatch,
)
from backend.reconciliation.reconciliation_severity import (
    classify_mismatch_severity,
)


def build_mismatches_from_position_report(
    report: PositionReconciliationReport,
) -> List[ReconciliationMismatch]:
    """
    Convert a position reconciliation report into canonical mismatch records.

    Read-only adapter:
    - no broker calls
    - no trade execution
    - no position modification
    - no ledger modification
    """

    mismatches: List[ReconciliationMismatch] = []

    for symbol in report.missing_from_position_manager:
        details = "Broker position missing from position manager"

        severity = classify_mismatch_severity(
            1,
            0,
        )

        mismatches.append(
            ReconciliationMismatch(
                symbol=symbol,
                source_a="broker",
                source_b="position_manager",
                details=details,
                severity=severity,
            )
        )

    for symbol in report.missing_from_ledger:
        details = "Broker position missing from ledger"

        severity = classify_mismatch_severity(
            1,
            0,
        )

        mismatches.append(
            ReconciliationMismatch(
                symbol=symbol,
                source_a="broker",
                source_b="ledger",
                details=details,
                severity=severity,
            )
        )

    return mismatches