"""GET /api/audit/replay: `_safe_int` was undefined, so every authorized request raised NameError (HTTP 500)."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from dashboard.mobile import mobile_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(mobile_app, "_SESSIONS", {})
    monkeypatch.setattr(mobile_app, "_SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    calls: list[int] = []
    real = mobile_app.replay_mobile_trade_event_file

    def recording(path, *, session_id, limit):
        calls.append(limit)
        return real(path, session_id=session_id, limit=limit)

    monkeypatch.setattr(mobile_app, "replay_mobile_trade_event_file", recording)
    c = TestClient(mobile_app.app)
    c.calls = calls
    return c


def _login(client, role):
    token = f"tok-{role}"
    now = time.time()
    mobile_app._SESSIONS[token] = {"created": now, "last_activity": now,
                                   "user_ctx": {"user_id": f"synthetic-{role.lower()}", "role": role}}
    client.cookies.set(mobile_app.SESSION_COOKIE, token)


@pytest.mark.parametrize("query,expected", [("", 100), ("?limit=5", 5), ("?limit=abc", 100), ("?limit=0", 1),
                                            ("?limit=9999", 250), ("?limit=-3", 1), ("?limit=2.5", 100)])
def test_replay_limit_is_parsed_and_clamped(client, query, expected):
    _login(client, "SUPER_USER")
    r = client.get("/api/audit/replay" + query)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert client.calls == [expected]


def test_replay_still_requires_authentication_and_audit_permission(client):
    assert client.get("/api/audit/replay").status_code == 401
    _login(client, "VIEWER")
    assert client.get("/api/audit/replay").status_code == 403
    assert client.calls == []


@pytest.mark.parametrize("value,default,expected", [("7", 1, 7), (" 8 ", 1, 8), (None, 3, 3), ("x", 3, 3), (True, 3, 3),
                                                    ("1e3", 3, 3)])
def test_safe_int(value, default, expected):
    assert mobile_app._safe_int(value, default) == expected
