import pytest

from backend.app.compliance.legal_acceptance import (
    AcceptanceBlockReason,
    AcceptanceValidationStatus,
)
from backend.app.compliance.legal_acceptance_service import LegalAcceptanceService
from backend.app.compliance.legal_acceptance_store import InMemoryLegalAcceptanceStore
from backend.app.compliance.legal_acceptance_versions import LEGAL_TERMS
from backend.app.security import auth_gate
from backend.app.security import user_registry


def _use_temp_user_store(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(user_registry, "USER_STORE", str(tmp_path / "users.json"))


def test_admin_password_reset_invalidates_old_password_and_hashes_new_password(
    monkeypatch,
    tmp_path,
    caplog,
) -> None:
    _use_temp_user_store(monkeypatch, tmp_path)
    caplog.set_level("INFO", logger="backend.app.security.user_registry")
    user_registry.create_user(
        user_id=7001,
        display_name="Recovery User",
        role="TRADER",
        unit_code="CORE",
        home_branch="main",
        temp_password="oldpass",
    )

    assert user_registry.reset_password(
        7001,
        "newpass",
        authorized_by_role="SUPER_USER",
    ) is True
    assert "PASSWORD_RESET_COMPLETED | user_id=7001" in caplog.text

    with pytest.raises(RuntimeError, match="bad_password"):
        user_registry.authenticate(7001, "oldpass")

    record = user_registry.authenticate(7001, "newpass")
    assert record.user_id == 7001
    assert record.role == "TRADER"
    assert record.must_change_password is True

    stored = user_registry.load_users()["7001"]
    assert stored["password_hash"] != "newpass"
    assert stored["password_hash"] == user_registry._hash_password("newpass")


def test_password_reset_rejects_unauthorized_role(monkeypatch, tmp_path) -> None:
    _use_temp_user_store(monkeypatch, tmp_path)
    user_registry.create_user(
        user_id=7002,
        display_name="Unauthorized Reset User",
        role="TRADER",
        unit_code="CORE",
        home_branch="main",
        temp_password="oldpass",
    )

    with pytest.raises(PermissionError, match="PASSWORD_RESET_FORBIDDEN"):
        user_registry.reset_password(
            7002,
            "newpass",
            authorized_by_role="TRADER",
        )

    assert user_registry.authenticate(7002, "oldpass").user_id == 7002


def test_password_reset_rejects_unknown_user_and_short_password(
    monkeypatch,
    tmp_path,
) -> None:
    _use_temp_user_store(monkeypatch, tmp_path)

    with pytest.raises(RuntimeError, match="unknown user"):
        user_registry.reset_password(
            9999,
            "newpass",
            authorized_by_role="ADMIN",
        )

    user_registry.create_user(
        user_id=7003,
        display_name="Policy User",
        role="TRADER",
        unit_code="CORE",
        home_branch="main",
        temp_password="oldpass",
    )

    with pytest.raises(RuntimeError, match="min_length=6"):
        user_registry.reset_password(
            7003,
            "short",
            authorized_by_role="ADMIN",
        )


def test_auth_gate_registry_compatibility_preserves_password_change_path(
    monkeypatch,
    tmp_path,
) -> None:
    _use_temp_user_store(monkeypatch, tmp_path)
    user_registry.create_user(
        user_id=7004,
        display_name="Auth Gate User",
        role="TRADER",
        unit_code="CORE",
        home_branch="main",
        temp_password="oldpass",
    )

    user = auth_gate._get_user_any(user_registry, 7004)

    assert user is not None
    assert auth_gate._verify_password_any(user_registry, user, "oldpass") is True
    assert auth_gate._change_password_any(user_registry, 7004, "newpass") is True
    assert auth_gate._verify_password_any(user_registry, user, "oldpass") is False

    refreshed = auth_gate._get_user_any(user_registry, 7004)
    assert refreshed is not None
    assert auth_gate._verify_password_any(user_registry, refreshed, "newpass") is True


def test_password_reset_does_not_change_legal_acceptance_enforcement(
    monkeypatch,
    tmp_path,
) -> None:
    _use_temp_user_store(monkeypatch, tmp_path)
    user_registry.create_user(
        user_id=7005,
        display_name="Legal Acceptance User",
        role="TRADER",
        unit_code="CORE",
        home_branch="main",
        temp_password="oldpass",
    )

    assert user_registry.reset_password(
        7005,
        "newpass",
        authorized_by_role="ADMIN",
    ) is True

    service = LegalAcceptanceService(store=InMemoryLegalAcceptanceStore())
    result = service.validate_acceptance(
        user_id="7005",
        acceptance_type=LEGAL_TERMS,
    )

    assert result.status == AcceptanceValidationStatus.BLOCK
    assert result.block_reason == AcceptanceBlockReason.MISSING_ACCEPTANCE
