from __future__ import annotations

from datetime import datetime

import pytest

from dashboard.auth import css_sign_on


def _record(password: str) -> dict:
    return {
        "user_id": "00001",
        "display_name": "New User",
        "role": "TRADER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "password_hash": css_sign_on.hash_password(password),
        "must_change_password": False,
        "last_password_change": datetime.now().isoformat(timespec="seconds"),
        "password_history": [],
        "failed_attempts": 0,
        "locked": False,
        "locked_at": None,
        "lockout_until": None,
        "lockout_seconds": 0,
        "lockout_started_at": None,
        "recovery_question": None,
        "recovery_answer_hash": None,
        "recovery_answers": {},
        "recovery_required": True,
        "recovery_configured_at": None,
    }


def test_authenticated_new_user_must_enroll_recovery_before_session(monkeypatch) -> None:
    users = {"00001": _record("StrongPassword!234")}
    monkeypatch.setattr(css_sign_on, "save_users", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(css_sign_on, "record_auth_audit_event", lambda *_args, **_kwargs: None)

    with pytest.raises(css_sign_on.RecoverySetupRequired) as exc:
        css_sign_on.authenticate_credentials(users, "00001", "StrongPassword!234")
    assert exc.value.user_id == "00001"

    css_sign_on.enroll_all_password_recovery(
        users,
        "00001",
        {
            question: f"Private Recovery Answer {index}"
            for index, question in enumerate(css_sign_on.RECOVERY_QUESTIONS, start=1)
        },
    )
    assert users["00001"]["recovery_required"] is False
    assert len(users["00001"]["recovery_answers"]) == 5
    assert all(
        users["00001"]["recovery_answers"][question] != f"Private Recovery Answer {index}"
        for index, question in enumerate(css_sign_on.RECOVERY_QUESTIONS, start=1)
    )

    ctx = css_sign_on.authenticate_credentials(users, "00001", "StrongPassword!234")
    assert ctx["user_id"] == "00001"


def test_created_user_is_marked_recovery_required(monkeypatch) -> None:
    users: dict[str, dict] = {}
    monkeypatch.setattr(css_sign_on, "available_roles", lambda: ("TRADER",))
    actor = {"user_id": "00000", "role": "SUPER_USER"}
    css_sign_on.create_user(
        users,
        actor,
        "1",
        "New User",
        "TRADER",
        "StrongInitial!234",
    )
    row = users["00001"]
    assert row["recovery_required"] is True
    assert row["recovery_question"] is None
    assert row["recovery_answer_hash"] is None
    assert row["recovery_answers"] == {}


def test_single_recovery_answer_is_not_enough(monkeypatch) -> None:
    users = {"00001": _record("StrongPassword!234")}
    monkeypatch.setattr(css_sign_on, "save_users", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(css_sign_on, "record_auth_audit_event", lambda *_args, **_kwargs: None)

    css_sign_on.enroll_password_recovery(
        users,
        "00001",
        css_sign_on.RECOVERY_QUESTIONS[0],
        "Only One Answer",
        "Only One Answer",
    )
    assert css_sign_on.recovery_is_configured(users["00001"]) is False
    assert users["00001"]["recovery_required"] is True


def test_random_challenge_reset_uses_selected_question(monkeypatch) -> None:
    users = {"00001": _record("StrongPassword!234")}
    monkeypatch.setattr(css_sign_on, "save_users", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(css_sign_on, "record_auth_audit_event", lambda *_args, **_kwargs: None)
    answers = {
        question: f"Answer {index}"
        for index, question in enumerate(css_sign_on.RECOVERY_QUESTIONS, start=1)
    }
    css_sign_on.enroll_all_password_recovery(users, "00001", answers)
    question = css_sign_on.RECOVERY_QUESTIONS[3]
    ctx = css_sign_on.reset_password_with_recovery(
        users,
        "00001",
        answers[question],
        "DifferentStrongPassword!567",
        "DifferentStrongPassword!567",
        recovery_question=question,
    )
    assert ctx["user_id"] == "00001"
    assert users["00001"]["failed_attempts"] == 0
