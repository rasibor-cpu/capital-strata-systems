from backend.reconciliation.reconciliation_alerts import build_reconciliation_alert_messages
from backend.reconciliation.reconciliation_models import ReconciliationMismatch


def test_build_reconciliation_alert_messages_keeps_warning_and_critical():
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

    alerts = build_reconciliation_alert_messages(mismatches)

    assert len(alerts) == 2
    assert alerts[0]["severity"] == "WARNING"
    assert alerts[0]["symbol"] == "BTC-USD"
    assert alerts[1]["severity"] == "CRITICAL"
    assert alerts[1]["symbol"] == "ETH-USD"


def test_build_reconciliation_alert_messages_ignores_non_alert_severity():
    mismatches = [
        ReconciliationMismatch(
            symbol="SOL-USD",
            source_a="broker",
            source_b="ledger",
            severity="INFO",
            details="no actionable mismatch",
        )
    ]

    alerts = build_reconciliation_alert_messages(mismatches)

    assert alerts == []