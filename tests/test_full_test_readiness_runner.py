import os
import sqlite3

import backend.app.persistence.migrations.runner as migration_runner
import backend.app.persistence.repositories.base_repository as base_repository
from backend.app.persistence.services.persistence_service import PersistenceService
from backend.commercialization.full_test_runner import FullTestReadinessRunner


def test_full_test_runner_reaches_test_ready_without_production_authority(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)
    monkeypatch.setenv("CSS_FULL_TEST_MODE", "1")

    try:
        service = PersistenceService()
        report = FullTestReadinessRunner(service).run(
            validated_commit_sha="TEST-SHA-001",
            test_count=1964,
        )
        assert report.ready_for_full_testing is True
        assert report.production_commercial_ready is False
        assert report.uat_complete is True
        assert report.launch_dossier_complete is True
        assert report.sandbox_payment_succeeded is True
        assert report.sandbox_notification_succeeded is True
        assert report.trading_execution_authority is False
        assert report.broker_execution_authority is False
        assert report.money_movement_to_external_provider is False
        assert any(
            "PAYMENT_PROVIDER_NOT_PRODUCTION_ENVIRONMENT" in reason
            for reason in report.production_block_reason_codes
        )
    finally:
        conn.close()


def test_synthetic_fixture_requires_explicit_full_test_mode(monkeypatch):
    monkeypatch.delenv("CSS_FULL_TEST_MODE", raising=False)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(base_repository, "get_connection", lambda: conn)
    monkeypatch.setattr(migration_runner, "get_connection", lambda: conn)

    try:
        service = PersistenceService()
        try:
            FullTestReadinessRunner(service).run(
                validated_commit_sha="TEST-SHA-001",
                test_count=1,
            )
        except RuntimeError as exc:
            assert "CSS_FULL_TEST_MODE=1" in str(exc)
        else:
            raise AssertionError("full-test fixture must fail closed")
    finally:
        conn.close()
