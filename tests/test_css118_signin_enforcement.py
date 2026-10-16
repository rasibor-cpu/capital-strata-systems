"""Issue #118 P1: automatic onboarding enforcement at sign-in and on every new risk-taking route.

Drives the real mobile FastAPI app (login, /trade, /controls, live-micro-pilot) with a
temporary trading-profile store, temporary session/controls files and a synthetic user
directory. The live-pilot governor and the ticket executor are replaced by recorders so
no test can touch a broker path or a repository artifact.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from css118_support import KEY, activate
from backend.trading_profiles.gatekeeper import ONBOARDING_PATH, controls_change_increases_risk, risk_taking_status
from backend.trading_profiles.service import TradingProfileService
from dashboard.mobile import mobile_app

PASSWORD = "synthetic-password"


class _GovernorRecorder:
    calls: list[str] = []

    def write_config(self, **kw):
        self.calls.append("configure")
        return {"stub": True}

    def arm(self, **kw):
        self.calls.append("arm")
        return {"stub": True}

    def disarm(self, **kw):
        self.calls.append("disarm")
        return {"armed": False}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    root = tmp_path / "tp"
    monkeypatch.setattr(mobile_app, "_trading_profiles_service", lambda: TradingProfileService(root, key_provider=lambda: KEY))
    monkeypatch.setattr(mobile_app, "_SESSIONS", {})
    monkeypatch.setattr(mobile_app, "_SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    monkeypatch.setattr(mobile_app, "load_users", lambda: {})
    monkeypatch.setattr(mobile_app, "save_users", lambda users: None)

    def authenticate(users, user_id, password):
        if password != PASSWORD:
            # the class the app catches (other tests may reload css_sign_on)
            raise mobile_app.AuthFailure("INVALID_CREDENTIALS", "Invalid credentials.")
        return {"user_id": user_id, "role": "SUPER_USER", "display_name": user_id}

    monkeypatch.setattr(mobile_app, "authenticate_credentials", authenticate)
    _GovernorRecorder.calls = []
    monkeypatch.setattr(mobile_app, "LiveMicroPilotGovernor", _GovernorRecorder)
    tickets: list[dict] = []
    monkeypatch.setattr(mobile_app, "execute_mobile_trade_ticket",
                        lambda user_ctx, form: tickets.append(dict(form)) or {"ok": False, "status": "STUB"})
    client = TestClient(mobile_app.app, follow_redirects=False)
    return {"client": client, "service": TradingProfileService(root, key_provider=lambda: KEY), "tickets": tickets,
            "controls": tmp_path / "controls.json"}


def _login(client, user):
    return client.post("/login", data={"user_id": user, "password": PASSWORD})


def _accept(service, user):
    activate(service.consent, user, "CSS Autonomous Trading", "Balanced")


# ------------------------------------------------------------------ sign-in
def test_sign_in_without_acceptance_lands_on_onboarding(env):
    r = _login(env["client"], "new-user")
    assert r.status_code == 303 and r.headers["location"] == ONBOARDING_PATH


def test_sign_in_with_valid_acceptance_lands_on_dashboard(env):
    _accept(env["service"], "accepted-user")
    r = _login(env["client"], "accepted-user")
    assert r.status_code == 303 and r.headers["location"] == "/dashboard"


def test_sign_in_while_paused_lands_on_onboarding(env):
    _accept(env["service"], "paused-user")
    env["service"].pause("paused-user")
    assert _login(env["client"], "paused-user").headers["location"] == ONBOARDING_PATH
    assert risk_taking_status(env["service"], "paused-user").reason == "trading_paused_by_user"


def test_unreadable_acceptance_store_fails_closed(env):
    _accept(env["service"], "tamper-user")
    env["service"].preferences.path.write_text("{not json", encoding="utf-8")
    assert _login(env["client"], "tamper-user").headers["location"] == ONBOARDING_PATH
    status = risk_taking_status(env["service"], "tamper-user")
    assert status.allowed is False and status.reason.startswith("acceptance_unverifiable")


def test_bad_password_still_rejected_before_acceptance_check(env):
    assert env["client"].post("/login", data={"user_id": "x", "password": "wrong"}).status_code == 401


# ------------------------------------------------------------------ /trade
def test_trade_ticket_blocked_without_acceptance(env):
    client = env["client"]
    _login(client, "new-user")
    r = client.post("/trade", data={"symbol": "EUR/USD", "side": "BUY", "quantity": "1"})
    assert r.status_code == 403
    assert "accept the CSS User Operating Manual" in r.text and ONBOARDING_PATH in r.text
    assert env["tickets"] == []  # never reached the ticket executor


def test_trade_ticket_reaches_executor_only_with_acceptance(env):
    client = env["client"]
    _accept(env["service"], "accepted-user")
    _login(client, "accepted-user")
    client.post("/trade", data={"symbol": "EUR/USD", "side": "BUY", "quantity": "1"})
    assert len(env["tickets"]) == 1  # the existing ticket gates then decide (stubbed here)


# ------------------------------------------------------------------ /controls
def test_risk_increasing_controls_blocked_without_acceptance(env):
    client = env["client"]
    _login(client, "new-user")
    r = client.post("/controls", data={"mobile_trading_mode": "MOBILE_PAPER_TRADING", "engine_mode": "SAFE"})
    assert r.status_code == 403
    assert not env["controls"].exists()  # nothing saved


def test_engine_mode_escalation_blocked_without_acceptance(env):
    client = env["client"]
    _login(client, "new-user")
    r = client.post("/controls", data={"mobile_trading_mode": "MOBILE_READ_ONLY", "engine_mode": "EXPANSION"})
    assert r.status_code == 403 and not env["controls"].exists()


def test_kill_switch_engagement_always_allowed(env):
    client = env["client"]
    _login(client, "new-user")
    r = client.post("/controls", data={"mobile_trading_mode": "MOBILE_READ_ONLY", "engine_mode": "SAFE",
                                       "live_order_kill_switch": "on"})
    assert r.status_code == 200
    assert json.loads(env["controls"].read_text())["live_order_kill_switch"] is True


def test_risk_reduction_from_existing_paper_mode_allowed(env):
    env["controls"].write_text(json.dumps({"mobile_trading_mode": "MOBILE_PAPER_TRADING", "engine_mode": "BALANCED"}))
    client = env["client"]
    _login(client, "new-user")
    r = client.post("/controls", data={"mobile_trading_mode": "MOBILE_READ_ONLY", "engine_mode": "SAFE"})
    assert r.status_code == 200
    assert json.loads(env["controls"].read_text())["mobile_trading_mode"] == "MOBILE_READ_ONLY"


def test_controls_escalation_allowed_after_acceptance(env):
    client = env["client"]
    _accept(env["service"], "accepted-user")
    _login(client, "accepted-user")
    r = client.post("/controls", data={"mobile_trading_mode": "MOBILE_PAPER_TRADING", "engine_mode": "SAFE"})
    assert r.status_code == 200


# ------------------------------------------------------------------ live micro-pilot
@pytest.mark.parametrize("route", ["configure", "arm"])
def test_live_pilot_configure_and_arm_blocked_without_acceptance(env, route):
    client = env["client"]
    _login(client, "new-user")
    r = client.post(f"/api/live-micro-pilot/{route}", data={"confirmation_word": "ARM"})
    body = r.json()
    assert r.status_code == 403 and body["status"] == "MANUAL_ACCEPTANCE_REQUIRED"
    assert body["onboarding_path"] == ONBOARDING_PATH and _GovernorRecorder.calls == []


def test_live_pilot_disarm_never_requires_acceptance(env):
    client = env["client"]
    _login(client, "new-user")
    r = client.post("/api/live-micro-pilot/disarm", data={"confirmation_word": "DISARM"})
    assert r.status_code == 200 and _GovernorRecorder.calls == ["disarm"]


def test_live_pilot_arm_with_acceptance_reaches_its_own_governor_checks(env):
    client = env["client"]
    _accept(env["service"], "accepted-user")
    _login(client, "accepted-user")
    client.post("/api/live-micro-pilot/arm", data={"confirmation_word": "ARM"})
    assert _GovernorRecorder.calls == ["arm"]  # acceptance is necessary, never sufficient


# ------------------------------------------------------------------ classifier
@pytest.mark.parametrize("current,requested,increases", [
    ({"mobile_trading_mode": "MOBILE_READ_ONLY"}, {"mobile_trading_mode": "MOBILE_PAPER_TRADING"}, True),
    ({"mobile_trading_mode": "MOBILE_PAPER_TRADING"}, {"mobile_trading_mode": "MOBILE_READ_ONLY"}, False),
    ({"engine_mode": "SAFE"}, {"engine_mode": "BALANCED"}, True),
    ({"engine_mode": "AGGRESSIVE"}, {"engine_mode": "SAFE"}, False),
    ({"live_order_kill_switch": True}, {"live_order_kill_switch": False}, True),
    ({"live_order_kill_switch": False}, {"live_order_kill_switch": True}, False),
    ({"engine_mode": "SAFE"}, {"engine_mode": "TURBO"}, True),  # unknown value counts as an increase
])
def test_controls_change_classifier(current, requested, increases):
    base = {"mobile_trading_mode": "MOBILE_READ_ONLY", "engine_mode": "SAFE", "live_order_kill_switch": False}
    assert controls_change_increases_risk({**base, **current}, {**base, **requested}) is increases
