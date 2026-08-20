"""CSS forward-state auth/recovery acceptance: password policy and recovery."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from dashboard.auth import css_sign_on as auth


def _seed_user(tmp_path: Path, monkeypatch, password: str = "StrongBootstrap!9") -> dict:
    monkeypatch.setenv("CSS_BOOTSTRAP_ADMIN_PASSWORD", password)
    users_file = tmp_path / "users.json"
    users = auth.load_users(users_file)
    monkeypatch.setattr(auth, "USERS_FILE", users_file)
    return users


def test_min_password_length_is_twelve():
    assert auth.MIN_PASSWORD_LENGTH == 12


def test_password_policy_uses_minimum_not_exact_length():
    source = Path(auth.__file__).read_text(encoding="utf-8")
    assert "MIN_PASSWORD_LENGTH = 12" in source
    assert "len(password) < MIN_PASSWORD_LENGTH" in source
    assert "len(new_password) < MIN_PASSWORD_LENGTH" in source
    assert "len(bootstrap) < MIN_PASSWORD_LENGTH" in source
    assert "len(bootstrap_password) < MIN_PASSWORD_LENGTH" in source
    assert "exactly {MIN_PASSWORD_LENGTH}" not in source
    assert "at least {MIN_PASSWORD_LENGTH} characters" in source
    assert "!= MIN_PASSWORD_LENGTH" not in source


def test_passwords_shorter_than_twelve_rejected():
    with pytest.raises(auth.PasswordValidationError, match="at least 12 characters"):
        auth.validate_initial_password("ShortPass1!")
    user_record = {
        "password_hash": auth.hash_password("CurrentPassword12"),
        "password_history": [],
    }
    with pytest.raises(auth.PasswordValidationError, match="at least 12 characters"):
        auth.validate_new_password(user_record, "ShortPass1!", "ShortPass1!")


def test_passwords_longer_than_twelve_accepted():
    auth.validate_initial_password("LongerThanTwelveChars!")
    user_record = {
        "password_hash": auth.hash_password("CurrentPassword12"),
        "password_history": [],
    }
    auth.validate_new_password(
        user_record,
        "BrandNewLongPassword99",
        "BrandNewLongPassword99",
    )


def test_exact_twelve_character_password_accepted():
    auth.validate_initial_password("Exactly12!!X")
    assert len("Exactly12!!X") == 12


def test_bootstrap_rejects_short_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("CSS_BOOTSTRAP_ADMIN_PASSWORD", "short")
    with pytest.raises(RuntimeError, match="CSS_BOOTSTRAP_REQUIRED"):
        auth.load_users(tmp_path / "users.json")


def test_recovery_configured_and_reset_success(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    auth.configure_password_recovery(
        users,
        "00000",
        "StrongBootstrap!9",
        auth.RECOVERY_QUESTIONS[0],
        "Toronto",
    )
    record = users["00000"]
    assert auth.recovery_is_configured(record)
    assert record["recovery_question"] == auth.RECOVERY_QUESTIONS[0]
    assert record["recovery_answer_hash"] == auth.hash_recovery_answer("Toronto")
    assert "Toronto" not in Path(auth.USERS_FILE).read_text(encoding="utf-8")

    ctx = auth.reset_password_with_recovery(
        users,
        "00000",
        "toronto",
        "RecoveredPass12!",
        "RecoveredPass12!",
    )
    assert ctx["user_id"] == "00000"
    assert users["00000"]["password_hash"] == auth.hash_password("RecoveredPass12!")


def test_recovery_not_configured_fails_closed(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    with pytest.raises(auth.AuthFailure) as excinfo:
        auth.reset_password_with_recovery(
            users,
            "00000",
            "anything",
            "RecoveredPass12!",
            "RecoveredPass12!",
        )
    assert excinfo.value.code == "RECOVERY_NOT_CONFIGURED"


def test_incorrect_recovery_fails_closed(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    auth.configure_password_recovery(
        users,
        "00000",
        "StrongBootstrap!9",
        auth.RECOVERY_QUESTIONS[1],
        "Central High",
    )
    with pytest.raises(auth.AuthFailure) as excinfo:
        auth.reset_password_with_recovery(
            users,
            "00000",
            "wrong answer",
            "RecoveredPass12!",
            "RecoveredPass12!",
        )
    assert excinfo.value.code == "RECOVERY_FAILED"
    assert users["00000"]["password_hash"] == auth.hash_password("StrongBootstrap!9")


def test_recovery_reset_obeys_password_history(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    auth.configure_password_recovery(
        users,
        "00000",
        "StrongBootstrap!9",
        auth.RECOVERY_QUESTIONS[2],
        "Honda Civic",
    )
    with pytest.raises(auth.PasswordValidationError, match="differ from the current"):
        auth.reset_password_with_recovery(
            users,
            "00000",
            "Honda Civic",
            "StrongBootstrap!9",
            "StrongBootstrap!9",
        )


def test_recovery_reset_rejects_short_password(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    auth.configure_password_recovery(
        users,
        "00000",
        "StrongBootstrap!9",
        auth.RECOVERY_QUESTIONS[0],
        "Montreal",
    )
    with pytest.raises(auth.PasswordValidationError, match="at least 12 characters"):
        auth.reset_password_with_recovery(
            users,
            "00000",
            "Montreal",
            "short",
            "short",
        )


def test_recovery_gui_back_cancel_does_not_shutdown_runtime():
    source = inspect.getsource(auth.await_gui_login)
    assert "Forgot Password?" in source
    assert "show_password_recovery" in source
    assert "Back / Cancel" in source
    assert "Configure Recovery" in source
    assert "show_configure_recovery" in source
    assert "RECOVERY_NOT_CONFIGURED" in source
    assert "CSS_SIGN_ON_CANCELLED" in source
    recovery_block = source[
        source.index("def show_password_recovery") : source.index("def show_login")
    ]
    assert '"Back / Cancel", show_login' in recovery_block
    assert "root.destroy" not in recovery_block


def test_recovery_questions_are_fixed_set():
    assert len(auth.RECOVERY_QUESTIONS) >= 3
    assert "What city were you born in?" in auth.RECOVERY_QUESTIONS


def test_configure_recovery_rejects_blank_answer(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    with pytest.raises(auth.PasswordValidationError, match="cannot be blank"):
        auth.configure_password_recovery(
            users,
            "00000",
            "StrongBootstrap!9",
            auth.RECOVERY_QUESTIONS[0],
            "   ",
        )


def test_configure_recovery_rejects_invalid_question(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    with pytest.raises(auth.PasswordValidationError, match="valid recovery question"):
        auth.configure_password_recovery(
            users,
            "00000",
            "StrongBootstrap!9",
            "What is your favorite color?",
            "blue",
        )
