"""Wave 2 Security & Broker Integrity regression tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_ar023_no_hardcoded_bootstrap_password():
    from dashboard.auth import css_sign_on as auth

    assert auth.INITIAL_ADMIN_PASSWORD == ""
    assert "123456" in auth.FORBIDDEN_DEFAULT_PASSWORDS
    assert auth.MIN_PASSWORD_LENGTH >= 12


def test_ar023_bootstrap_required_without_env(tmp_path, monkeypatch):
    from dashboard.auth import css_sign_on as auth

    monkeypatch.delenv("CSS_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="CSS_BOOTSTRAP_REQUIRED"):
        auth.load_users(tmp_path / "users.json")


def test_ar023_forbidden_default_bootstrap_rejected(tmp_path, monkeypatch):
    from dashboard.auth import css_sign_on as auth

    monkeypatch.setenv("CSS_BOOTSTRAP_ADMIN_PASSWORD", "123456")
    with pytest.raises(RuntimeError, match="FORBIDDEN|BOOTSTRAP"):
        auth.load_users(tmp_path / "users.json")


def test_ar023_bootstrap_seeds_with_strong_secret(tmp_path, monkeypatch):
    from dashboard.auth import css_sign_on as auth

    monkeypatch.setenv("CSS_BOOTSTRAP_ADMIN_PASSWORD", "StrongBootstrap!9")
    users = auth.load_users(tmp_path / "users.json")
    assert "00000" in users
    assert users["00000"]["password_hash"] == auth.hash_password("StrongBootstrap!9")
    assert users["00000"]["must_change_password"] is True


def test_ar024_mutation_auth_fail_closed(monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request
    from backend.security.mutation_guard import require_mutation_auth

    monkeypatch.setenv("CSS_HOST_SECURITY_PROFILE", "fail_closed")
    monkeypatch.delenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", raising=False)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mobile/control/pause",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)
    with pytest.raises(HTTPException) as exc:
        require_mutation_auth(request)
    assert exc.value.status_code == 401


def test_ar026_oanda_writes_quarantined(monkeypatch):
    from backend.app.brokers.oanda_adapter import OandaAdapter

    monkeypatch.delenv("CSS_OANDA_LEGACY_WRITES_ENABLED", raising=False)
    adapter = OandaAdapter.__new__(OandaAdapter)
    result = OandaAdapter.place_order(adapter, symbol="EUR_USD", units=1, side="BUY")
    assert result["ok"] is False
    assert result["error"] == "oanda_legacy_writes_quarantined"
    assert result["execution_allowed"] is False

    closed = OandaAdapter.close_trade(adapter, "1")
    assert closed["error"] == "oanda_legacy_writes_quarantined"
    pos = OandaAdapter.close_position(adapter, "EUR_USD")
    assert pos["error"] == "oanda_legacy_writes_quarantined"


def test_ar028_ops_activation_requires_checkers(tmp_path):
    from backend.operations.host_activation import (
        OperationsActivationError,
        activate_operations_service,
    )

    with pytest.raises(OperationsActivationError):
        activate_operations_service(
            artifacts_dir=tmp_path,
            required_checkers=("runtime_heartbeat",),
            register_defaults=False,
        )

    service = activate_operations_service(artifacts_dir=tmp_path)
    state = service.run_diagnostics()
    assert state.payload["overall_status"] == "HEALTHY"
    assert state.payload["health_score"] == 100.0


def test_ar028_empty_diagnostics_critical(tmp_path):
    from backend.common.configuration import OperationsConfig
    from backend.operations.health_monitor import HealthMonitor
    from backend.operations.operational_state_manager import OperationalStateManager
    from backend.operations.operational_timeline import OperationalTimeline
    from backend.operations.operations_service import OperationsService
    from backend.operations.runtime_statistics import RuntimeStatistics

    service = OperationsService(
        config=OperationsConfig(default_source="test"),
        monitor=HealthMonitor(),
        state_manager=OperationalStateManager(file_path=str(tmp_path / "s.json")),
        timeline=OperationalTimeline(file_path=str(tmp_path / "t.json")),
        statistics=RuntimeStatistics(),
    )
    state = service.run_diagnostics()
    assert state.payload["overall_status"] == "CRITICAL"
    assert state.payload["health_score"] == 0.0


def test_ar029_030_observability_tick(tmp_path, monkeypatch):
    from backend.operations.host_activation import (
        activate_operations_service,
        run_host_observability_tick,
    )

    monkeypatch.chdir(tmp_path)
    service = activate_operations_service(artifacts_dir=tmp_path / "ops")
    result = run_host_observability_tick(service)
    assert result["operations_status"] == "HEALTHY"
    assert result["monitoring_production_pager"] is False
    assert result["monitoring_authority"] == "CSSAlertRepository"


def test_ar031_options_empty_registry_blocked():
    from backend.options.options_income_provider_registry import (
        clear_provider_plugins,
        provider_registry_status,
    )

    clear_provider_plugins()
    status = provider_registry_status()
    assert status["market_data_providers"] == []
    assert status["option_chain_providers"] == []
    assert status["holdings_providers"] == []
    assert status["option_chain_status"] == "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED"
    assert status["execution_allowed"] is False
    assert status["advisory_only"] is True


def test_ar032_ambiguous_live_alias_rejected():
    from backend.runtime.broker_environment_profiles import (
        BrokerEnvironmentProfile,
        _normalize_profile,
        _profile_selection_failures,
        profile_mode_alias,
    )

    # Runtime mode alias retains historical live→LIVE_READ_ONLY mapping.
    assert profile_mode_alias("live") is BrokerEnvironmentProfile.LIVE_READ_ONLY
    # Explicit profile selection rejects bare LIVE/PRODUCTION.
    assert _normalize_profile("LIVE") is None
    assert _normalize_profile("PRODUCTION") is None
    assert _normalize_profile("LIVE_READ_ONLY") is BrokerEnvironmentProfile.LIVE_READ_ONLY
    failures = _profile_selection_failures(
        explicit_profile="LIVE",
        cli_profile=None,
        env={},
        selected=None,
    )
    assert "ambiguous_broker_environment_profile_alias" in failures


def test_ar033_live_legacy_credentials_blocked(monkeypatch):
    from backend.app.brokers.credential_loader import (
        CredentialLoadError,
        load_credentials_for_broker,
    )

    monkeypatch.setenv("CSS_SECRET_AUTHORITY_ENFORCE", "1")
    monkeypatch.delenv("CSS_ALLOW_LEGACY_LIVE_CREDENTIALS", raising=False)
    with pytest.raises(CredentialLoadError, match="SECRET_AUTHORITY_REQUIRED"):
        load_credentials_for_broker("oanda", mode="live")

    monkeypatch.delenv("CSS_SECRET_AUTHORITY_ENFORCE", raising=False)
    monkeypatch.setenv("CSS_ENV", "production")
    with pytest.raises(CredentialLoadError, match="SECRET_AUTHORITY_REQUIRED"):
        load_credentials_for_broker("oanda", mode="live")


def test_ar025_canonical_pwa_authority_doc_exists():
    doc = Path("docs/operations/CSS_PWA_CANONICAL_INSTALL.md")
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "canonical" in text.lower()
    assert "https" in text.lower()
    assert "manifest.webmanifest" in text
