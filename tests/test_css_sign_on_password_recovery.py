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


def _enroll_all(users: dict, overrides: dict[str, str] | None = None) -> dict[str, str]:
    answers = {
        question: f"answer-{index}"
        for index, question in enumerate(auth.RECOVERY_QUESTIONS, start=1)
    }
    if overrides:
        answers.update(overrides)
    auth.enroll_all_password_recovery(users, "00000", answers)
    return answers


def test_min_password_length_is_twelve():
    assert auth.MIN_PASSWORD_LENGTH == 12


def test_new_users_always_require_first_password_change(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    actor = {"user_id": "00000", "role": "SUPER_USER"}
    auth.create_user(
        users,
        actor,
        "42",
        "New User",
        "VIEWER",
        "InitialStrong!42",
        must_change_password=False,
    )
    assert users["00042"]["must_change_password"] is True


def test_local_reset_preserves_recovery_and_forces_change(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    answers = _enroll_all(users)
    original_answers = dict(users["00000"]["recovery_answers"])
    users["00000"]["must_change_password"] = False
    auth.save_users(users)

    from tools.css_reset_local_password import reset_local_password
    session_file = tmp_path / "css_auth_session.json"
    session_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(auth, "SESSION_AUTH_FILE", session_file)

    reset_local_password("00000", "ABCDEFGHIJKL")
    reloaded = auth.load_users(auth.USERS_FILE)
    assert auth.verify_password("ABCDEFGHIJKL", reloaded["00000"]["password_hash"]) is True
    assert reloaded["00000"]["must_change_password"] is True
    assert reloaded["00000"]["recovery_answers"] == original_answers
    assert session_file.exists() is False


def test_password_change_preserves_recovery_and_noncredential_state(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    _enroll_all(users)
    record = users["00000"]
    record["must_change_password"] = False
    record["last_password_change"] = auth.datetime.now().isoformat(timespec="seconds")
    record["ui_preferences"] = {"theme": "system", "landing": "home"}
    record["feature_preferences"] = {"reports": True, "market_intelligence": True}

    recovery_before = dict(record["recovery_answers"])
    ui_before = dict(record["ui_preferences"])
    features_before = dict(record["feature_preferences"])

    auth.change_password(
        users,
        "00000",
        "ChangedPassword!42",
        "ChangedPassword!42",
    )

    updated = users["00000"]
    assert auth.verify_password("ChangedPassword!42", updated["password_hash"]) is True
    assert updated["recovery_answers"] == recovery_before
    assert updated["ui_preferences"] == ui_before
    assert updated["feature_preferences"] == features_before
    assert updated["must_change_password"] is False


def test_password_hashes_are_salted_pbkdf2_records():
    first = auth.hash_password("UniquePassword!42")
    second = auth.hash_password("UniquePassword!42")
    assert first.startswith("pbkdf2_sha256$")
    assert second.startswith("pbkdf2_sha256$")
    assert first != second
    assert auth.verify_password("UniquePassword!42", first) is True
    assert auth.verify_password("wrong-password", first) is False


def test_recovery_hashes_are_salted_and_normalized():
    first = auth.hash_recovery_answer("  Toronto  ")
    second = auth.hash_recovery_answer("toronto")
    assert first.startswith("pbkdf2_sha256$")
    assert second.startswith("pbkdf2_sha256$")
    assert first != second
    assert auth.verify_recovery_answer("TORONTO", first) is True
    assert auth.verify_recovery_answer("Ottawa", first) is False


def test_legacy_sha256_password_verifies_and_upgrades_on_login(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    record = users["00000"]
    record["password_hash"] = auth._legacy_sha256("StrongBootstrap!9")
    record["must_change_password"] = False
    record["last_password_change"] = auth.datetime.now().isoformat(timespec="seconds")
    _enroll_all(users)
    ctx = auth.authenticate_credentials(users, "00000", "StrongBootstrap!9")
    assert ctx["user_id"] == "00000"
    assert users["00000"]["password_hash"].startswith("pbkdf2_sha256$")
    assert auth.verify_password("StrongBootstrap!9", users["00000"]["password_hash"]) is True


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
    _enroll_all(users, {auth.RECOVERY_QUESTIONS[0]: "Toronto"})
    record = users["00000"]
    assert auth.recovery_is_configured(record)
    assert record["recovery_question"] == auth.RECOVERY_QUESTIONS[0]
    assert auth.verify_recovery_answer("Toronto", record["recovery_answer_hash"]) is True
    assert "Toronto" not in Path(auth.USERS_FILE).read_text(encoding="utf-8")

    ctx = auth.reset_password_with_recovery(
        users,
        "00000",
        "toronto",
        "RecoveredPass12!",
        "RecoveredPass12!",
        recovery_question=auth.RECOVERY_QUESTIONS[0],
    )
    assert ctx["user_id"] == "00000"
    assert auth.verify_password("RecoveredPass12!", users["00000"]["password_hash"]) is True


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
    _enroll_all(users, {auth.RECOVERY_QUESTIONS[1]: "Central High"})
    with pytest.raises(auth.AuthFailure) as excinfo:
        auth.reset_password_with_recovery(
            users,
            "00000",
            "wrong answer",
            "RecoveredPass12!",
            "RecoveredPass12!",
            recovery_question=auth.RECOVERY_QUESTIONS[1],
        )
    assert excinfo.value.code == "RECOVERY_FAILED"
    assert auth.verify_password("StrongBootstrap!9", users["00000"]["password_hash"]) is True


def test_recovery_reset_obeys_password_history(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    _enroll_all(users, {auth.RECOVERY_QUESTIONS[2]: "Honda Civic"})
    with pytest.raises(auth.PasswordValidationError, match="differ from the current"):
        auth.reset_password_with_recovery(
            users,
            "00000",
            "Honda Civic",
            "StrongBootstrap!9",
            "StrongBootstrap!9",
            recovery_question=auth.RECOVERY_QUESTIONS[2],
        )


def test_recovery_reset_rejects_short_password(tmp_path, monkeypatch):
    users = _seed_user(tmp_path, monkeypatch)
    _enroll_all(users, {auth.RECOVERY_QUESTIONS[0]: "Montreal"})
    with pytest.raises(auth.PasswordValidationError, match="at least 12 characters"):
        auth.reset_password_with_recovery(
            users,
            "00000",
            "Montreal",
            "short",
            "short",
            recovery_question=auth.RECOVERY_QUESTIONS[0],
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
    assert len(auth.RECOVERY_QUESTIONS) == 5
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
