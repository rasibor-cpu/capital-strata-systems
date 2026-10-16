"""HTTP API for trading profiles: authentication, own-account only, no trading capability."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.trading_profiles.api import PREFIX, create_trading_profiles_router
from backend.trading_profiles.disclosures import DISCLOSURE_VERSION
from backend.trading_profiles.service import TradingProfileService

KEY = b"synthetic-test-mandate-key-0123456789abcdef"


def _client(tmp_path, key=KEY) -> TestClient:
    def resolver(request):
        user = request.headers.get("x-test-user")
        return {"user_id": user, "session_id": "sess-" + user} if user else None

    app = FastAPI()
    app.include_router(create_trading_profiles_router(
        user_resolver=resolver,
        service_factory=lambda: TradingProfileService(tmp_path, key_provider=(lambda: key) if key else None),
    ))
    return TestClient(app)


def test_requires_authentication(tmp_path):
    client = _client(tmp_path)
    for path in ("/catalog", "/me", "/statement"):
        assert client.get(PREFIX + path).status_code == 401
    assert client.post(PREFIX + "/mode", json={"mode": "Simulated Trading"}).status_code == 401


def test_catalog_lists_exact_choices_and_no_live_permission(tmp_path):
    body = _client(tmp_path).get(PREFIX + "/catalog", headers={"x-test-user": "u1"}).json()
    assert [m["mode"] for m in body["operating_modes"]] == ["Simulated Trading", "Copy a CSS Trader", "CSS Autonomous Trading"]
    assert all(m["live_broker_orders_permitted"] is False for m in body["operating_modes"])
    assert [p["personality"] for p in body["risk_personalities"]] == [
        "Safe", "Conservative", "Balanced", "Aggressive", "Ultra Aggressive"]
    assert all(p["overrides_safety_gates"] is False and p["live_trading_permission"] is False for p in body["risk_personalities"])
    assert body["disclosure"]["version"] == DISCLOSURE_VERSION


def test_full_copy_setup_flow_and_startup_state(tmp_path):
    client = _client(tmp_path)
    h = {"x-test-user": "u1"}
    assert client.get(PREFIX + "/me", headers=h).json()["needs_selection"] == ["operating_mode"]
    assert client.post(PREFIX + "/mode", json={"mode": "Copy a CSS Trader"}, headers=h).json()["ok"]
    assert client.post(PREFIX + "/personality", json={"personality": "Aggressive"}, headers=h).json()["ok"]
    assert client.post(PREFIX + "/disclosure/acknowledge", json={"version": DISCLOSURE_VERSION}, headers=h).json()["ok"]
    me = client.get(PREFIX + "/me", headers=h).json()
    assert me["needs_selection"] == ["trader_mandate"] and me["can_open_new_trades"] is False
    created = client.post(PREFIX + "/mandates", headers=h, json={
        "trader_id": "trader-alpha", "asset_classes": ["FX", "CRYPTO"], "max_allocation": 2000, "currency": "CAD",
        "valid_days": 30, "reauthorization_policy": "INTERVAL", "reauthorization_interval_hours": 24}).json()
    assert created["ok"] and created["mandate_id"].startswith("mdt-")
    me = client.get(PREFIX + "/me", headers=h).json()
    assert me["can_open_new_trades"] is True and me["live_trading_permitted"] is False
    assert me["mandate"]["personality"] == "Aggressive" and me["mandate"]["status"] == "mandate_valid"
    # Another user cannot revoke u1's mandate: identity comes from the session only.
    other = client.post(PREFIX + f"/mandates/{created['mandate_id']}/revoke", headers={"x-test-user": "u2"}, json={})
    assert other.status_code == 400 and other.json()["reason"] == "mandate_not_found"
    assert client.post(PREFIX + f"/mandates/{created['mandate_id']}/revoke", headers=h, json={}).json()["ok"]
    assert "trader_mandate" in client.get(PREFIX + "/me", headers=h).json()["needs_selection"]


def test_invalid_choices_and_missing_signing_key(tmp_path):
    client = _client(tmp_path, key=None)
    h = {"x-test-user": "u1"}
    assert client.post(PREFIX + "/mode", json={"mode": "Live Trading"}, headers=h).status_code == 400
    assert client.post(PREFIX + "/personality", json={"personality": "EXPANSION"}, headers=h).status_code == 400
    client.post(PREFIX + "/mode", json={"mode": "Copy a CSS Trader"}, headers=h)
    client.post(PREFIX + "/personality", json={"personality": "Safe"}, headers=h)
    client.post(PREFIX + "/disclosure/acknowledge", json={"version": DISCLOSURE_VERSION}, headers=h)
    response = client.post(PREFIX + "/mandates", headers=h, json={
        "trader_id": "t", "asset_classes": ["FX"], "max_allocation": 100, "valid_days": 1,
        "reauthorization_policy": "EACH_SIGN_ON"})
    assert response.status_code == 503 and response.json()["reason"] == "mandate_signing_key_unavailable"


def test_router_is_mounted_on_mobile_app_and_requires_session():
    from dashboard.mobile import mobile_app

    client = TestClient(mobile_app.app)
    # 401 (not 404) proves the route is mounted and guarded by the mobile session.
    assert client.get(PREFIX + "/me").status_code == 401
    assert client.post(PREFIX + "/mandates", json={}).status_code == 401
    assert client.get(PREFIX + "/does-not-exist").status_code == 404
