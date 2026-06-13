from __future__ import annotations

import os

import pytest

from backend.app.observability.audit_context import clear_audit_user, set_audit_user
from backend.app.security import live_toggle


def teardown_function() -> None:
    clear_audit_user()


def test_live_toggle_blocks_test_mode_even_for_super_user(monkeypatch) -> None:
    monkeypatch.setenv("REA_ENGINE_MODE", "TEST")
    set_audit_user(user_id=99999, role="SUPER_USER", unit_code="OPS", branch="HQ")

    with pytest.raises(RuntimeError, match="EXECUTION_BLOCKED_TEST_MODE"):
        live_toggle.require_live_allowed()


def test_hardcoded_user_id_is_no_longer_required(monkeypatch) -> None:
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    set_audit_user(user_id=99999, role="SUPER_USER", unit_code="OPS", branch="HQ")

    live_toggle.require_live_allowed()


def test_unauthorized_user_is_blocked(monkeypatch) -> None:
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    set_audit_user(user_id=1369, role="TRADER", unit_code="OPS", branch="HQ")

    with pytest.raises(PermissionError, match="LIVE_EXECUTION_DENIED"):
        live_toggle.require_live_allowed()


def test_missing_context_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    clear_audit_user()

    with pytest.raises(PermissionError, match="LIVE_EXECUTION_DENIED"):
        live_toggle.require_live_allowed()


def test_explicit_live_execution_permission_is_allowed(monkeypatch) -> None:
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")

    live_toggle.require_live_allowed(
        {
            "user_id": "22222",
            "role": "TRADER",
            "role_profile": {
                "can_execute_live_trading": True,
            },
        }
    )


def test_non_super_user_without_live_permission_is_blocked(monkeypatch) -> None:
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")

    with pytest.raises(PermissionError, match="LIVE_EXECUTION_DENIED"):
        live_toggle.require_live_allowed(
            {
                "user_id": "22222",
                "role": "TRADER",
                "role_profile": {
                    "can_use_live_broker_mode": True,
                    "can_execute_live_trading": False,
                },
            }
        )


def test_missing_role_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")

    allowed, reason, ctx = live_toggle.is_live_execution_authorized(
        {"user_id": "22222", "role_profile": {"can_execute_live_trading": False}}
    )

    assert allowed is False
    assert reason == "live_toggle_role_missing"
    assert ctx is not None


def test_live_toggle_does_not_enable_broker_execution_flag(monkeypatch) -> None:
    monkeypatch.setenv("REA_ENGINE_MODE", "LIVE")
    monkeypatch.delenv("OANDA_ENABLE_LIVE_TRADING", raising=False)
    set_audit_user(user_id=99999, role="SUPER_USER", unit_code="OPS", branch="HQ")

    live_toggle.require_live_allowed()

    assert os.getenv("OANDA_ENABLE_LIVE_TRADING") is None
