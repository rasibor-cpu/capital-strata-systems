"""HTTP API: authentication, session isolation, direct-API bypass attempts, downloads, emergency actions."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from css118_support import KEY, approve_trader, mandate_request
from backend.trading_profiles.api import ONBOARDING_PATH, PREFIX, create_trading_profiles_router
from backend.trading_profiles.manual import ACKNOWLEDGEMENT_SHA256, ACKNOWLEDGEMENT_TEXT, current_manual
from backend.trading_profiles.service import TradingProfileService
from backend.trading_profiles.trader_registry import TraderRegistry


def _client(tmp_path, key=KEY) -> TestClient:
    def resolver(request):
        user = request.headers.get("x-test-user")
        session = request.headers.get("x-test-session") or ("sess-" + str(user))
        return {"user_id": user, "session_id": session} if user else None

    approve_trader(TraderRegistry(tmp_path))  # synthetic dual-control approval of trader-alpha
    app = FastAPI()
    app.include_router(create_trading_profiles_router(
        user_resolver=resolver,
        service_factory=lambda: TradingProfileService(tmp_path, key_provider=(lambda: key) if key else None),
    ))
    return TestClient(app)


def _h(user="u1", session=None):
    headers = {"x-test-user": user}
    if session:
        headers["x-test-session"] = session
    return headers


def _review_all(client, review, headers):
    for page in review["pages"]:
        body = client.get(f"{PREFIX}/consent/reviews/{review['review_id']}/pages/{page['page_id']}", headers=headers).json()
        assert body["ok"] and "<script" not in body["html"]
        r = client.post(f"{PREFIX}/consent/reviews/{review['review_id']}/pages/{page['page_id']}/reviewed",
                        headers=headers, json={"method": "scroll_bottom", "page_sha256": body["sha256"]})
        assert r.json()["ok"], r.json()


def _accept_payload(change, review, **overrides):
    payload = {"acknowledgement_checked": True, "acknowledgement_sha256": ACKNOWLEDGEMENT_SHA256,
               "manual_version": review["manual_version"], "manual_sha256": review["manual_sha256"],
               "policy_hash": change["policy_hash"]}
    payload.update(overrides)
    return payload


def _start(client, headers, payload):
    change = client.post(PREFIX + "/changes", headers=headers, json=payload).json()["change"]
    review = client.post(PREFIX + "/consent/reviews", headers=headers, json={"change_id": change["change_id"]}).json()
    return change, review


def test_every_endpoint_requires_authentication(tmp_path):
    client = _client(tmp_path)
    for path in ("/catalog", "/me", "/manual", "/manual/download", "/manual/pages/about", "/consent/receipts", "/statement"):
        assert client.get(PREFIX + path).status_code == 401, path
    for path in ("/changes", "/consent/reviews", "/consent/reviews/x/accept", "/emergency/pause", "/resume"):
        assert client.post(PREFIX + path, json={}).status_code == 401, path
    assert client.get(ONBOARDING_PATH).status_code == 401


def test_catalog_lists_four_modes_five_personalities_manual_and_precedence(tmp_path):
    body = _client(tmp_path).get(PREFIX + "/catalog", headers=_h()).json()
    assert [m["mode"] for m in body["operating_modes"]] == [
        "Simulated Trading", "CSS-Assisted Trading", "Copy a CSS Trader", "CSS Autonomous Trading"]
    assert all(m["live_broker_orders_permitted"] is False for m in body["operating_modes"])
    assert [p["personality"] for p in body["risk_personalities"]] == [
        "Safe", "Conservative", "Balanced", "Aggressive", "Ultra Aggressive"]
    assert body["manual"]["acknowledgement_text"] == ACKNOWLEDGEMENT_TEXT
    assert body["precedence"][-2] == "user-configured limits (tighten only)"


def test_full_onboarding_flow_receipt_and_history(tmp_path):
    client = _client(tmp_path)
    h = _h()
    me = client.get(PREFIX + "/me", headers=h).json()
    assert me["needs"] == ["onboarding_acceptance"] and me["can_open_new_trades"] is False
    change, review = _start(client, h, {"operating_mode": "Copy a CSS Trader", "risk_personality": "Aggressive",
                                        "limits": {"max_position_pct_of_equity": 5}, "mandate": mandate_request()})
    assert change["kind"] == "INITIAL_ACTIVATION" and change["implications"]
    assert client.get(PREFIX + "/me", headers=h).json()["active"] is None  # proposing is not activating
    _review_all(client, review, h)
    receipt = client.post(f"{PREFIX}/consent/reviews/{review['review_id']}/accept", headers=h,
                          json=_accept_payload(change, review)).json()["receipt"]
    assert receipt["document"]["version"] == current_manual().version and receipt["live_trading_authorized"] is False
    me = client.get(PREFIX + "/me", headers=h).json()
    assert me["can_open_new_trades"] is True and me["consent"]["valid"] is True and me["live_trading_permitted"] is False
    history = client.get(PREFIX + "/consent/receipts", headers=h).json()
    assert [r["receipt_id"] for r in history["receipts"]] == [receipt["receipt_id"]] and history["document_history"]
    download = client.get(f"{PREFIX}/consent/receipts/{receipt['receipt_id']}/download", headers=h)
    assert download.status_code == 200 and "attachment" in download.headers["content-disposition"]
    assert client.get(f"{PREFIX}/consent/receipts/{receipt['receipt_id']}/download", headers=_h("u2")).status_code == 404


def test_direct_api_bypass_attempts_are_rejected(tmp_path):
    client = _client(tmp_path)
    h = _h()
    change, review = _start(client, h, {"operating_mode": "CSS Autonomous Trading", "risk_personality": "Balanced"})
    accept = f"{PREFIX}/consent/reviews/{review['review_id']}/accept"
    r = client.post(accept, headers=h, json=_accept_payload(change, review))
    assert r.status_code == 400 and r.json()["reason"].startswith("pages_not_reviewed")
    # Marking a page reviewed without the server having presented it.
    r = client.post(f"{PREFIX}/consent/reviews/{review['review_id']}/pages/about/reviewed", headers=h,
                    json={"method": "scroll_bottom", "page_sha256": "0" * 64})
    assert r.json()["reason"] == "page_not_presented"
    _review_all(client, review, h)
    for bad in ({"acknowledgement_checked": False}, {"acknowledgement_checked": "true"}, {"acknowledgement_sha256": "x"},
                {"manual_version": "0.0.1"}, {"policy_hash": "0" * 64}):
        r = client.post(accept, headers=h, json=_accept_payload(change, review, **bad))
        assert r.status_code == 400, bad
    assert client.get(PREFIX + "/me", headers=h).json()["active"] is None
    assert client.post(accept, headers=h, json=_accept_payload(change, review)).json()["ok"]
    assert client.post(accept, headers=h, json=_accept_payload(change, review)).json()["reason"] == "review_closed"


def test_session_and_user_isolation_including_deep_links(tmp_path):
    client = _client(tmp_path)
    change, review = _start(client, _h(), {"operating_mode": "Simulated Trading"})
    page = f"{PREFIX}/consent/reviews/{review['review_id']}/pages/about"
    assert client.get(page, headers=_h("u2")).status_code == 404
    assert client.get(page, headers=_h("u1", session="stolen-elsewhere")).status_code == 404
    assert client.get(f"{PREFIX}/changes/{change['change_id']}", headers=_h("u2")).status_code == 404
    assert client.post(PREFIX + "/consent/reviews", headers=_h("u2"), json={"change_id": change["change_id"]}).status_code == 404


def test_emergency_actions_need_no_consent_but_resume_does(tmp_path):
    client = _client(tmp_path)
    assert client.post(PREFIX + "/emergency/pause", headers=_h()).json()["paused"] is True
    r = client.post(PREFIX + "/resume", headers=_h())
    assert r.status_code == 400 and r.json()["reason"] == "consent_missing"
    assert client.post(PREFIX + "/mandates/mdt-unknown/revoke", headers=_h(), json={}).status_code == 404


def test_manual_reference_and_downloads(tmp_path):
    client = _client(tmp_path)
    manual = client.get(PREFIX + "/manual", headers=_h()).json()
    assert manual["version"] == current_manual().version and len(manual["pages"]) == 12
    md = client.get(PREFIX + "/manual/download?format=md", headers=_h())
    txt = client.get(PREFIX + "/manual/download?format=txt", headers=_h())
    assert md.headers["x-css-document-sha256"] == current_manual().sha256
    assert txt.headers["content-type"].startswith("text/plain") and "attachment" in txt.headers["content-disposition"]
    assert client.get(PREFIX + "/manual/pages/gates", headers=_h()).json()["title"].startswith("4.")
    assert client.get(PREFIX + "/manual/pages/nope", headers=_h()).status_code == 404


def test_copy_activation_without_signing_key_fails_closed(tmp_path):
    client = _client(tmp_path, key=None)
    h = _h()
    change, review = _start(client, h, {"operating_mode": "Copy a CSS Trader", "risk_personality": "Balanced",
                                        "mandate": mandate_request(asset_classes=["FX"])})
    _review_all(client, review, h)
    r = client.post(f"{PREFIX}/consent/reviews/{review['review_id']}/accept", headers=h, json=_accept_payload(change, review))
    assert r.status_code == 503 and "signing_key_unavailable" in r.json()["reason"]
    assert client.get(PREFIX + "/me", headers=h).json()["active"] is None


def test_onboarding_page_is_served_with_unchecked_acknowledgement(tmp_path):
    page = _client(tmp_path).get(ONBOARDING_PATH, headers=_h())
    assert page.status_code == 200
    html = page.text
    assert 'id="ack-checkbox" disabled' in html and "checked" not in html.split('id="ack-checkbox"')[1].split(">")[0]
    assert 'id="accept-btn" disabled' in html
    assert "Pause new trading now" in html


def test_router_is_mounted_on_mobile_app_and_requires_session():
    from dashboard.mobile import mobile_app

    client = TestClient(mobile_app.app)
    assert client.get(PREFIX + "/me").status_code == 401
    assert client.post(PREFIX + "/changes", json={}).status_code == 401
    assert client.get(ONBOARDING_PATH).status_code == 401
    assert client.get(PREFIX + "/does-not-exist").status_code == 404
