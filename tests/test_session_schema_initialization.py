from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest

from backend.app.persistence import db


@pytest.fixture()
def isolated_runtime_db(tmp_path, monkeypatch):
    db.close_connection()
    db_path = tmp_path / "fresh_css_runtime.db"
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", db_path)
    yield db_path
    db.close_connection()


def _table_exists(db_path: Path, table_name: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table_name,),
        ).fetchone()

    return row is not None


def test_persistence_service_bootstraps_session_schema(isolated_runtime_db):
    from backend.app.persistence.services.persistence_service import (
        PersistenceService,
    )

    service = PersistenceService()

    assert service.healthcheck()["status"] == "ok"
    assert _table_exists(isolated_runtime_db, "sessions")
    assert _table_exists(isolated_runtime_db, "session_state_history")


def test_trade_decision_orchestrator_initializes_on_fresh_database(
    isolated_runtime_db,
    monkeypatch,
):
    monkeypatch.setenv("CSS_TOTAL_CAPITAL", "50000")

    import backend.intelligence.trade_decision_orchestrator as tdo

    importlib.reload(tdo)
    orchestrator = tdo.TradeDecisionOrchestrator()

    assert orchestrator.capital_allocator.total_capital == 50000.0
    assert orchestrator.session_id
    assert _table_exists(isolated_runtime_db, "sessions")


def test_legal_acceptance_repository_still_initializes_after_bootstrap(
    isolated_runtime_db,
):
    from backend.app.compliance.legal_acceptance_service import (
        LegalAcceptanceService,
    )
    from backend.app.compliance.legal_acceptance_versions import (
        REQUIRED_ACCEPTANCE_TYPES,
    )
    from backend.app.persistence.services.persistence_service import (
        PersistenceService,
    )

    persistence = PersistenceService()
    service = LegalAcceptanceService(store=persistence.legal_acceptances)
    acceptance_type = REQUIRED_ACCEPTANCE_TYPES[0]

    record = service.record_current_acceptance(
        user_id="arp-010-user",
        acceptance_type=acceptance_type,
        audit_reference="ARP-010-TEST",
    )

    assert record.accepted is True
    assert _table_exists(isolated_runtime_db, "legal_acceptances")

