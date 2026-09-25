from __future__ import annotations

import json

from dashboard.auth import css_sign_on as auth
from tools import css_reset_local_password as reset_tool


def test_reset_uses_current_auth_paths_and_preserves_profile(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    session_file = tmp_path / "session.json"

    monkeypatch.setenv("CSS_BOOTSTRAP_ADMIN_PASSWORD", "StrongBootstrap!9")
    monkeypatch.setattr(auth, "USERS_FILE", users_file)
    monkeypatch.setattr(auth, "SESSION_AUTH_FILE", session_file)

    users = auth.load_users(users_file)
    users["00000"]["recovery_answers"] = {"q": "hashed-answer"}
    users["00000"]["selected_broker"] = "QUESTRADE"
    auth.save_users(users, users_file)
    session_file.write_text(json.dumps({"authenticated": True}), encoding="utf-8")

    reset_tool.reset_local_password("00000", "TemporaryPassword!42")

    reloaded = auth.load_users(users_file)
    record = reloaded["00000"]
    assert auth.verify_password("TemporaryPassword!42", record["password_hash"]) is True
    assert record["must_change_password"] is True
    assert record["recovery_answers"] == {"q": "hashed-answer"}
    assert record["selected_broker"] == "QUESTRADE"
    assert not session_file.exists()
