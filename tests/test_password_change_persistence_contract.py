from __future__ import annotations

from dashboard.auth import css_sign_on as auth
from dashboard.enterprise_shell import operator_configuration as operator_config


def test_password_change_preserves_broker_selection_and_recovery(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    broker_file = tmp_path / "css_operator_broker_selection.json"

    monkeypatch.setenv("CSS_BOOTSTRAP_ADMIN_PASSWORD", "StrongBootstrap!9")
    monkeypatch.setattr(auth, "USERS_FILE", users_file)
    monkeypatch.setattr(operator_config, "BROKER_SELECTION_FILE", broker_file)

    users = auth.load_users(users_file)
    recovery_answers = {
        question: f"answer-{index}"
        for index, question in enumerate(auth.RECOVERY_QUESTIONS, start=1)
    }
    auth.enroll_all_password_recovery(users, "00000", recovery_answers)

    selection = operator_config.save_broker_selection(
        broker="OANDA",
        broker_mode="LIVE_READ_ONLY",
        actor_user_id="00000",
        confirmed=True,
    )
    assert selection["execution_allowed"] is False
    assert selection["live_trading_blocked"] is True
    assert selection["broker_execution_armed"] is False
    assert selection["advisory_only"] is True

    recovery_before = dict(users["00000"]["recovery_answers"])
    auth.change_password(
        users,
        "00000",
        "ChangedPassword!42",
        "ChangedPassword!42",
    )
    auth.save_users(users)

    reloaded_users = auth.load_users(users_file)
    reloaded_selection = operator_config.load_broker_selection("00000")

    assert auth.verify_password(
        "ChangedPassword!42",
        reloaded_users["00000"]["password_hash"],
    ) is True
    assert reloaded_users["00000"]["recovery_answers"] == recovery_before
    assert reloaded_selection["selected_broker"] == "OANDA"
    assert reloaded_selection["broker_mode"] == "LIVE_READ_ONLY"
    assert reloaded_selection["confirmed"] is True
    assert reloaded_selection["execution_allowed"] is False
    assert reloaded_selection["live_trading_blocked"] is True
    assert reloaded_selection["broker_execution_armed"] is False
    assert reloaded_selection["advisory_only"] is True
