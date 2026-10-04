"""Owner-UAT defect: Trial & Contract -> Check Status showed nothing.

``checkTrialStatus`` began with ``if (!governingAgreement) return;`` -- it
silently did nothing unless **Load Agreement** had been clicked earlier in the
same page load (a fresh sign-in as the checker never had), and it had no
network/parse error handling. It now reads Agreement ID / Version from the
page fields (the server needs them: enrollments are keyed by agreement),
validates visibly, and renders every outcome. The status API also returns the
enrollment facts (customer, account, trial start/expiry, cancellation) and
turns a malformed request into 422 instead of 500. Status checks are read-only.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess

import pytest

from backend.app.auth.session_dependency import SESSION_COOKIE_NAME
from dashboard.web import web_app
from tests.test_uat_trial_enrollment import (  # noqa: F401  (fixtures)
    UAT_AGREEMENT,
    _approve,
    _bearer,
    _cookie_csrf,
    _enroll_body,
    env,
    runtime_db,
)

NODE = shutil.which("node")


def _status_url(customer="UAT-CUST-E2E", account="UAT-ACCT-E2E", agreement=UAT_AGREEMENT.agreement_id,
                version=UAT_AGREEMENT.agreement_version, assessed_at="2026-10-05T00:00:00Z"):
    return (f"/api/v1/commercial-trial/status?customer_id={customer}&account_reference={account}"
            f"&agreement_id={agreement}&agreement_version={version}&assessed_at={assessed_at}")


def _enroll(client, store):
    maker = _cookie_csrf(store, "10001", "FINCON")
    action = client.post("/api/v1/commercial-trial/enroll", json=_enroll_body(), headers=maker).json()["controlled_action"]
    assert _approve(client, _bearer(store, "10002", "HEAD_FINCON"), action).json()["controlled_action"]["status"] == "EXECUTED"


def _session_cookie(store, user, role):
    return {"Cookie": f"{SESSION_COOKIE_NAME}={store.create_session(user, [role])}"}


def _row_counts(runtime_db_path, commercial_db):  # noqa: F811
    rt = sqlite3.connect(str(runtime_db_path))
    counts = {t: rt.execute(f"select count(*) from {t}").fetchone()[0] for t in (
        "commercial_trial_enrollments", "commercial_trial_cancellations",
        "commercial_receivable_payments", "commercial_payment_collection_authorities")}
    counts["controlled_actions"] = sqlite3.connect(commercial_db).execute(
        "select count(*) from commercial_controlled_actions").fetchone()[0]
    return counts


# ---------------------------------------------------------------------------
# Status API
# ---------------------------------------------------------------------------


def test_existing_active_enrollment_reports_full_status_read_only(env, runtime_db):  # noqa: F811
    client, store, commercial_db = env
    _enroll(client, store)
    before = _row_counts(runtime_db, commercial_db)
    resp = client.get(_status_url(), headers=_session_cookie(store, "10002", "HEAD_FINCON"))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == "TRIAL_ACTIVE"
    assert (body["customer_id"], body["account_reference"]) == ("UAT-CUST-E2E", "UAT-ACCT-E2E")
    assert (body["agreement_id"], body["agreement_version"]) == (UAT_AGREEMENT.agreement_id, UAT_AGREEMENT.agreement_version)
    assert body["trial_start_at"] == "2026-09-29T12:00:00Z"
    assert body["trial_expires_at"] == "2026-10-29T12:00:00Z"
    assert body["cancellation_recorded"] is False and body["canceled_at"] is None
    assert body["payment_execution_allowed"] is False
    assert body["money_movement_allowed"] is False
    assert body["execution_authority"] is False
    assert _row_counts(runtime_db, commercial_db) == before  # nothing written by a status check


def test_cancelled_enrollment_reports_cancellation(env):  # noqa: F811
    client, store, _ = env
    _enroll(client, store)
    maker = _cookie_csrf(store, "10001", "FINCON")
    cancel = client.post("/api/v1/commercial-trial/cancel", headers=maker, json={
        "customer_id": "UAT-CUST-E2E", "account_reference": "UAT-ACCT-E2E", "canceled_at": "2026-10-01T00:00:00Z",
        "cancellation_audit_reference": "uat-cancel-status", "evidence_refs": ["uat:e2e"], "idempotency_key": "status-cancel",
    }).json()["controlled_action"]
    _approve(client, _bearer(store, "10002", "HEAD_FINCON"), cancel)
    body = client.get(_status_url(), headers=_session_cookie(store, "10003", "AUDIT")).json()
    assert body["status"] == "CANCELED"
    assert body["cancellation_recorded"] is True and body["canceled_at"] == "2026-10-01T00:00:00Z"


def test_nonexistent_enrollment_is_an_explicit_404(env):  # noqa: F811
    client, store, _ = env
    resp = client.get(_status_url(customer="NO-SUCH-CUSTOMER"), headers=_session_cookie(store, "10002", "HEAD_FINCON"))
    assert resp.status_code == 404
    assert "enrollment is missing" in resp.json()["detail"]


@pytest.mark.parametrize("url", [
    "/api/v1/commercial-trial/status?customer_id=c&account_reference=a",          # missing fields
    _status_url(assessed_at="not-a-timestamp"),                                     # malformed timestamp
])
def test_missing_or_malformed_fields_are_422_not_500(env, url):  # noqa: F811
    client, store, _ = env
    _enroll(client, store)
    resp = client.get(url, headers=_session_cookie(store, "10002", "HEAD_FINCON"))
    assert resp.status_code == 422
    assert "Traceback" not in resp.content.decode()


def test_status_requires_an_authorized_session(env):  # noqa: F811
    client, store, _ = env
    _enroll(client, store)
    assert client.get(_status_url()).status_code == 401
    assert client.get(_status_url(), headers={"Cookie": f"{SESSION_COOKIE_NAME}=forged"}).status_code == 401
    assert client.get(_status_url(), headers=_session_cookie(store, "10009", "TRADER")).status_code == 403
    for user, role in [("10001", "FINCON"), ("10002", "HEAD_FINCON"), ("10003", "AUDIT"), ("10004", "HEAD_COMPLIANCE")]:
        assert client.get(_status_url(), headers=_session_cookie(store, user, role)).status_code == 200


# ---------------------------------------------------------------------------
# Browser rendering (the page's real script, executed in Node)
# ---------------------------------------------------------------------------


def _run_check_status(fields, fetch_js):
    script = web_app._trial_contract_page().split("<script>")[-1].split("</script>")[0]
    harness = """
const elements = {};
function el(id) { return elements[id] || (elements[id] = {id, value: "", textContent: "", checked: false, style: {},
  addEventListener() {}}); }
globalThis.document = {getElementById: el};
globalThis.window = globalThis;
const FIELDS = %s;
for (const [id, value] of Object.entries(FIELDS)) el(id).value = value;
const calls = [];
globalThis.fetch = %s;
""" % (json.dumps(fields), fetch_js)
    program = harness + script + """
checkTrialStatus().then(() => {
  console.log(JSON.stringify({text: el("trial-result").textContent, calls}));
});
"""
    out = subprocess.run([NODE, "-e", program], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


FIELDS = {"trial-customer-id": "UAT-CUSTOMER-001", "trial-account-reference": "UAT-ACCOUNT-001",
          "trial-agreement-id": "UAT-AGR-001", "trial-agreement-version": "v1"}
OK_BODY = {"status": "TRIAL_ACTIVE", "customer_id": "UAT-CUSTOMER-001", "account_reference": "UAT-ACCOUNT-001",
           "agreement_id": "UAT-AGR-001", "agreement_version": "v1", "trial_start_at": "2026-09-30T01:55:05.283000Z",
           "trial_expires_at": "2026-10-30T01:55:05.283000Z", "cancellation_recorded": False, "canceled_at": None,
           "reason": "trial is active", "payment_execution_allowed": False}


def _fetch_returning(status, body):
    return ("async (url) => { calls.push(url); return {ok: %s, status: %d, json: async () => (%s)}; }"
            % ("true" if 200 <= status < 300 else "false", status, json.dumps(body)))


needs_node = pytest.mark.skipif(NODE is None, reason="node is required to execute the page script")


@needs_node
def test_page_shows_active_status_without_loading_the_agreement_first():
    out = _run_check_status(FIELDS, _fetch_returning(200, OK_BODY))
    assert len(out["calls"]) == 1  # the request is actually sent
    assert "agreement_id=UAT-AGR-001" in out["calls"][0] and "agreement_version=v1" in out["calls"][0]
    text = out["text"]
    for expected in ("Status: TRIAL_ACTIVE", "Customer ID: UAT-CUSTOMER-001", "Account Reference: UAT-ACCOUNT-001",
                     "Agreement: UAT-AGR-001 v1", "Trial start: 2026-09-30T01:55:05.283000Z",
                     "Trial expiry: 2026-10-30T01:55:05.283000Z", "Cancellation recorded: NO",
                     "executes no payment and grants no trading authority"):
        assert expected in text
    assert "No enrollment action taken." not in text


@needs_node
def test_page_shows_not_found_explicitly():
    out = _run_check_status(FIELDS, _fetch_returning(404, {"detail": "accepted trial enrollment is missing"}))
    assert out["text"].startswith("Not found: no enrollment for customer UAT-CUSTOMER-001")


@needs_node
@pytest.mark.parametrize("status,expected", [(401, "session has ended"), (403, "Not permitted"),
                                             (500, "Status unavailable (500)")])
def test_page_shows_errors_explicitly(status, expected):
    out = _run_check_status(FIELDS, _fetch_returning(status, {"detail": "x"}))
    assert expected in out["text"]


@needs_node
def test_page_shows_network_failure_explicitly():
    out = _run_check_status(FIELDS, "async () => { throw new Error('down'); }")
    assert "could not be reached" in out["text"]


@needs_node
def test_page_asks_for_missing_fields_instead_of_doing_nothing():
    out = _run_check_status({**FIELDS, "trial-customer-id": "", "trial-agreement-version": ""},
                            _fetch_returning(200, OK_BODY))
    assert out["calls"] == []
    assert out["text"] == "Check Status needs: Customer ID, Version."


@needs_node
def test_page_renders_server_values_as_text_not_html():
    hostile = {**OK_BODY, "customer_id": "<img src=x onerror=alert(1)>"}
    out = _run_check_status(FIELDS, _fetch_returning(200, hostile))
    assert "Customer ID: <img src=x onerror=alert(1)>" in out["text"]  # assigned via textContent, so inert
    script = web_app._trial_contract_page().split("<script>")[-1]
    body = script.split("async function checkTrialStatus()")[1].split("\ndocument.getElementById")[0]
    assert "innerHTML" not in body


# ---------------------------------------------------------------------------
# Every page script must at least parse (a stray newline inside a JS string
# literal silently kills the whole page script)
# ---------------------------------------------------------------------------


@needs_node
@pytest.mark.parametrize("page", ["_dashboard_page", "_positions_page", "_execution_page", "_risk_governance_page",
                                  "_market_opportunities_page", "_broker_page", "_margin_page", "_billing_page",
                                  "_trial_contract_page", "_commercialization_operations_page", "_approvals_page"])
def test_every_page_script_parses(page, tmp_path):
    html = getattr(web_app, page)()
    scripts = [chunk.split("</script>")[0] for chunk in html.split("<script>")[1:]]
    assert scripts
    for i, js in enumerate(scripts):
        path = tmp_path / f"{page}_{i}.js"
        path.write_text(js, encoding="utf-8")
        result = subprocess.run([NODE, "--check", str(path)], capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
