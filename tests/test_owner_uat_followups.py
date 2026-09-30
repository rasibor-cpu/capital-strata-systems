"""Owner-UAT follow-ups (2026-09-29 session).

A. Every authenticated web page shows who is signed in (user id + server-side
   role) next to Logout -- owner could not tell which identity was active.
B. A governed web checker UI (/approvals): the maker-checker request an
   operator creates on Trial & Contract had no web page on which the
   independent checker could find and decide it (approval was API-only).
C. Dashboard "Top Ranked"/"Top Composite"/... tiles rendered "[object Object]"
   because the page's get(path) only resolved two path segments.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

import backend.app.auth.token_store as token_store_module
from backend.app.auth.session_dependency import SESSION_COOKIE_NAME
from backend.app.auth.token_store import TokenStore
from dashboard.web import web_app
from dashboard.web.web_app import create_app
from engine.commercial.commercial_audit import CommercialAuditLog
from tests.asgi_test_client import AsgiTestClient as TestClient
from tests.test_uat_trial_enrollment import _enroll_body, _persisted_enrollment, env, runtime_db  # noqa: F401

ROLES = [("10001", "FINCON"), ("10002", "HEAD_FINCON"), ("10003", "AUDIT"), ("10004", "HEAD_COMPLIANCE")]
PAGES = ["/dashboard", "/billing", "/trial-contract", "/commercialization-operations", "/approvals"]


@pytest.fixture
def store(monkeypatch):
    fresh = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", fresh)
    return fresh


def _cookie(token):
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}


# ---------------------------------------------------------------------------
# A. Authenticated identity indicator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("user_id,role", ROLES)
@pytest.mark.parametrize("path", PAGES)
def test_every_page_shows_the_server_side_identity_next_to_logout(store, user_id, role, path):
    token = store.create_session(user_id, [role])
    page = TestClient(create_app()).get(path, headers=_cookie(token)).content.decode()
    assert f"Signed in: {user_id} &middot; {role}</span>" in page
    identity_at = page.index('id="css-session-identity"')
    assert page.index('action="/logout"') > identity_at  # Logout immediately follows
    assert token not in page


def test_identity_ignores_anything_the_client_claims(store):
    token = store.create_session("10001", ["FINCON"])
    page = TestClient(create_app()).get(
        "/dashboard?role=HEAD_FINCON&user_id=10002",
        headers={**_cookie(token), "X-User-Id": "10002", "X-Role": "HEAD_FINCON"},
    ).content.decode()
    assert "Signed in: 10001 &middot; FINCON" in page
    assert "HEAD_FINCON" not in page.split('id="css-session-identity"')[1].split("</span>")[0]


def test_identity_values_are_html_escaped():
    class Fake:
        username = '<img src=x onerror="alert(1)">'
        roles = ["<b>ROLE</b>"]
        csrf_token = "t"

    html_out = web_app._session_controls(Fake())
    assert "<img" not in html_out and "<b>" not in html_out
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in html_out


def test_anonymous_pages_still_redirect(store):
    client = TestClient(create_app())
    for path in PAGES:
        resp = client.get(path)
        assert resp.status_code == 303 and resp.headers["location"] == "/login"


# ---------------------------------------------------------------------------
# B. Governed web checker UI (/approvals)
# ---------------------------------------------------------------------------


def _session(store, user, role):
    token = store.create_session(user, [role])
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}, store.validate(token).csrf_token


def _make_request(client, store):
    cookie, csrf = _session(store, "10001", "FINCON")
    resp = client.post("/api/v1/commercial-trial/enroll", json=_enroll_body(), headers={**cookie, "X-CSRF-Token": csrf})
    assert resp.status_code == 201
    return resp.json()["controlled_action"]


def test_approvals_page_is_linked_and_lists_pending_requests_by_cookie(env):  # noqa: F811
    client, store, _ = env
    action = _make_request(client, store)
    cookie, _ = _session(store, "10002", "HEAD_FINCON")
    page = client.get("/approvals", headers=cookie).content.decode()
    assert 'href="/approvals"' in page and "Maker-Checker Approvals" in page
    listed = client.get("/api/v1/commercial/controlled-actions?status=PENDING", headers=cookie)
    assert listed.status_code == 200
    row = next(a for a in listed.json()["controlled_actions"] if a["action_id"] == action["action_id"])
    assert (row["maker_id"], row["maker_role"], row["status"]) == ("10001", "FINCON", "PENDING")
    assert row["payload"]["customer_id"] == "UAT-CUST-E2E"
    assert listed.json()["safety"]["execution_allowed"] is False


def test_listing_requires_a_commercial_role(env):  # noqa: F811
    client, store, _ = env
    trader, _ = _session(store, "10009", "TRADER")
    assert client.get("/api/v1/commercial/controlled-actions", headers=trader).status_code == 403
    assert client.get("/api/v1/commercial/controlled-actions").status_code == 401


def test_cookie_approval_requires_csrf_and_changes_nothing_without_it(env):  # noqa: F811
    client, store, _ = env
    action = _make_request(client, store)
    cookie, csrf = _session(store, "10002", "HEAD_FINCON")
    url = f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve"
    body = {"expected_payload_hash": action["payload_hash"]}
    for headers in (cookie, {**cookie, "X-CSRF-Token": "forged"}):
        assert client.post(url, json=body, headers=headers).status_code == 403
    assert _persisted_enrollment() is None
    ok = client.post(url, json=body, headers={**cookie, "X-CSRF-Token": csrf})
    assert ok.status_code == 200 and ok.json()["controlled_action"]["status"] == "EXECUTED"
    assert ok.json()["controlled_action"]["checker_id"] == "10002"
    assert _persisted_enrollment() is not None
    assert ok.json()["safety"]["money_movement_allowed"] is False


def test_maker_cannot_approve_own_request_from_the_page(env):  # noqa: F811
    client, store, _ = env
    cookie, csrf = _session(store, "10002", "HEAD_FINCON")
    action = client.post("/api/v1/commercial-trial/enroll", json=_enroll_body(),
                         headers={**cookie, "X-CSRF-Token": csrf}).json()["controlled_action"]
    resp = client.post(f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
                       json={"expected_payload_hash": action["payload_hash"]}, headers={**cookie, "X-CSRF-Token": csrf})
    assert resp.status_code in (403, 409, 422)
    assert _persisted_enrollment() is None


@pytest.mark.parametrize("user,role", [("10001", "FINCON"), ("10003", "AUDIT")])
def test_roles_without_approve_rights_are_refused_and_audited(env, user, role):  # noqa: F811
    client, store, commercial_db = env
    action = _make_request(client, store)
    cookie, csrf = _session(store, user, role)
    resp = client.post(f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
                       json={"expected_payload_hash": action["payload_hash"]}, headers={**cookie, "X-CSRF-Token": csrf})
    assert resp.status_code == 403
    denials = [e for e in CommercialAuditLog(commercial_db).events(object_type="commercial_api") if e.outcome == "DENIED"]
    assert len(denials) == 1 and denials[0].actor_id == user
    assert _persisted_enrollment() is None


def test_reject_from_the_page_is_final_and_attributed(env):  # noqa: F811
    client, store, _ = env
    action = _make_request(client, store)
    cookie, csrf = _session(store, "10004", "HEAD_COMPLIANCE")
    resp = client.post(f"/api/v1/commercial/controlled-actions/{action['action_id']}/reject",
                       json={"expected_payload_hash": action["payload_hash"], "reason": "UAT rejection"},
                       headers={**cookie, "X-CSRF-Token": csrf})
    assert resp.status_code == 200
    done = resp.json()["controlled_action"]
    assert (done["status"], done["checker_id"], done["decision_reason"]) == ("REJECTED", "10004", "UAT rejection")
    assert _persisted_enrollment() is None


def test_bearer_clients_of_the_governance_api_are_unaffected(env):  # noqa: F811
    client, store, _ = env
    action = _make_request(client, store)
    token = store.create_session("10002", ["HEAD_FINCON"])
    resp = client.post(f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
                       json={"expected_payload_hash": action["payload_hash"]}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_approvals_script_never_approves_by_itself():
    script = web_app._approvals_script()
    # Decisions happen only inside the click handler, behind confirm()/prompt().
    assert script.count("/approve") == 0  # the verb is appended from the clicked button
    assert "window.confirm(" in script and "window.prompt(" in script
    assert "addEventListener(\"click\", () => decide(action, verb))" in script
    assert "innerHTML" not in script  # rows are built with textContent only


# ---------------------------------------------------------------------------
# C. Dashboard "[object Object]" tiles
# ---------------------------------------------------------------------------

NODE = shutil.which("node")


def _dashboard_helpers() -> str:
    page = web_app._dashboard_page()
    start = page.index("    function get(path) {")
    end = page.index("    function escapeHtml(value) {")
    return page[start:end]


@pytest.mark.skipif(NODE is None, reason="node is required to execute the page script")
def test_dashboard_scoring_tiles_render_values_not_object_object():
    sections = {"opportunities": {"count": 2, "scoring_overview": {
        "top_ranked_symbols": ["BTC-USD", "CL"], "top_composite_scores": [0.87, 0.5],
        "best_adjusted_edge": 0.12, "average_execution_quality": 0.9,
        "highest_survivability_symbols": ["CL", "BTC-USD"]}}}
    paths = [
        "opportunities.scoring_overview.top_ranked_symbols.0",
        "opportunities.scoring_overview.top_composite_scores.0",
        "opportunities.scoring_overview.best_adjusted_edge",
        "opportunities.scoring_overview.average_execution_quality",
        "opportunities.scoring_overview.highest_survivability_symbols.0",
        "opportunities.count",
        "opportunities.scoring_overview",        # an object: shown as N/A, never "[object Object]"
        "opportunities.missing.deeper.path",
    ]
    program = (
        "function money(v){return String(v);} function pct(v){return String(v);}\n"
        f"const state = {{ sections: {json.dumps(sections)} }};\n"
        + _dashboard_helpers().replace("{{", "{").replace("}}", "}")
        + f"\nconsole.log(JSON.stringify({json.dumps(paths)}.map((p) => formatField(p, get(p)))));"
    )
    out = subprocess.run([NODE, "-e", program], capture_output=True, text=True, timeout=60, check=True).stdout
    assert json.loads(out) == ["BTC-USD", "0.87", "0.12", "0.9", "CL", "2", "N/A", "NONE"]


def test_dashboard_page_no_longer_uses_the_two_segment_lookup():
    helpers = _dashboard_helpers()
    assert 'const [section, key] = path.split(".")' not in helpers
