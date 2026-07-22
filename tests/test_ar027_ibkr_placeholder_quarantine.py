"""AR-027 — IBKR placeholder quarantine (fail-closed readiness)."""

from __future__ import annotations

from backend.app.brokers.canonical_tier1 import (
    get_canonical_broker_registry,
    reset_canonical_broker_registry_for_tests,
)
from backend.app.persistence.services.broker_reconciliation_service import (
    BrokerReconciliationService,
)
from backend.brokers.ibkr.ibkr_adapter import IBKRAdapter
from backend.brokers.ibkr.ibkr_runtime_manager import IBKRRuntimeManager


def setup_function() -> None:
    reset_canonical_broker_registry_for_tests()


def test_ibkr_adapter_never_reports_ready_or_connected() -> None:
    adapter = IBKRAdapter()
    assert adapter.connect() is False
    assert adapter.is_connected() is False

    health = adapter.health_check()
    assert health["ibkr_ready"] is False
    assert health["connected"] is False
    assert health["implementation_status"] == "PLACEHOLDER"
    assert health["placeholder"] is True

    snapshot = adapter.get_account_snapshot()
    assert snapshot["ibkr_ready"] is False
    assert snapshot["connected"] is False
    assert snapshot["placeholder"] is True


def test_ibkr_runtime_manager_is_not_healthy_after_initialize() -> None:
    manager = IBKRRuntimeManager(paper_trading=True)
    assert manager.initialize() is False
    assert manager.is_healthy() is False
    health = manager.get_runtime_health()
    assert health["ibkr_ready"] is False
    assert health["connected"] is False


def test_reconciliation_service_does_not_claim_ibkr_ready() -> None:
    result = BrokerReconciliationService().reconcile_against_broker_state(
        session_id="ar027-test",
        broker_positions=[],
    )
    assert result["ibkr_ready"] is False


def test_ibkr_remains_roadmap_excluded_from_tier1() -> None:
    registry = get_canonical_broker_registry()
    assert "IBKR" not in registry.list_brokers()
    assert registry.is_roadmap_excluded("IBKR")
