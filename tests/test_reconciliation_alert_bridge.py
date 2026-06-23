from backend.monitoring.css_alert_service import CSSAlertService
from backend.reconciliation.reconciliation_alert_bridge import emit_reconciliation_alerts
from backend.reconciliation.reconciliation_models import ReconciliationMismatch


def test_emit_reconciliation_alerts_persists_warning_and_critical(tmp_path):
    alert_service = CSSAlertService(storage_dir=str(tmp_path))

    mismatches = [
        ReconciliationMismatch(
            symbol="BTC-USD",
            source_a="broker",
            source_b="ledger",
            severity="WARNING",
            details="quantity mismatch",
        ),
        ReconciliationMismatch(
            symbol="ETH-USD",
            source_a="broker",
            source_b="ledger",
            severity="CRITICAL",
            details="missing internal position",
        ),
    ]

    emitted = emit_reconciliation_alerts(mismatches, alert_service)

    files = list(tmp_path.glob("*.json"))

    assert emitted == 2
    assert len(files) == 2


def test_emit_reconciliation_alerts_ignores_info(tmp_path):
    alert_service = CSSAlertService(storage_dir=str(tmp_path))

    mismatches = [
        ReconciliationMismatch(
            symbol="SOL-USD",
            source_a="broker",
            source_b="ledger",
            severity="INFO",
            details="no actionable mismatch",
        )
    ]

    emitted = emit_reconciliation_alerts(mismatches, alert_service)

    assert emitted == 0
    assert list(tmp_path.glob("*.json")) == []