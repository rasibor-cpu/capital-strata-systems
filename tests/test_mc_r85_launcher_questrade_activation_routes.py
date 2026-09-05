from fastapi.testclient import TestClient

from launcher import css_mobile_launcher as launcher


def _client(monkeypatch):
    monkeypatch.setenv("CSS_HOST_SECURITY_PROFILE", "open_dev")
    return TestClient(launcher.app)


def test_r85_activate_route_invokes_coordinator_once(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/test/AppData/Local")
    seen = {}
    def activate(*, refresh_token_store_path):
        seen["path"] = refresh_token_store_path
        return {"status": "READY", "execution_allowed": False, "live_trading_blocked": True}
    monkeypatch.setattr(launcher._QUESTRADE_MISSION_CONTROL_ACTIVATION, "activate", activate)
    response = _client(monkeypatch).post("/api/v1/questrade/mission-control/activate")
    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert seen["path"].endswith("CapitalStrataSystems/secrets/questrade_refresh_token.dpapi") or seen["path"].endswith("CapitalStrataSystems\\secrets\\questrade_refresh_token.dpapi")


def test_r85_refresh_route_never_calls_activate(monkeypatch):
    calls = {"refresh": 0}
    monkeypatch.setattr(launcher._QUESTRADE_MISSION_CONTROL_ACTIVATION, "activate", lambda **kwargs: (_ for _ in ()).throw(AssertionError("activate must not run")))
    def refresh():
        calls["refresh"] += 1
        return {"status": "READY", "reason": "refreshed", "execution_allowed": False, "live_trading_blocked": True}
    monkeypatch.setattr(launcher._QUESTRADE_MISSION_CONTROL_ACTIVATION, "refresh", refresh)
    response = _client(monkeypatch).post("/api/v1/questrade/mission-control/refresh")
    assert response.status_code == 200
    assert response.json()["reason"] == "refreshed"
    assert calls["refresh"] == 1


def test_r85_activate_route_fails_closed_without_localappdata(monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    response = _client(monkeypatch).post("/api/v1/questrade/mission-control/activate")
    assert response.status_code == 503
    assert response.json()["detail"] == "QUESTRADE_TOKEN_PATH_UNAVAILABLE"
