"""Release blocker: the bootstrap SUPER_USER 00000 first-claim race.

Previously a fresh (or unclaimed) ``css_sign_on`` store created 00000 with the
published password ``123456`` and a forced change, so whoever reached the
operator API change-password or the LAN-exposed mobile login first could set
its password and hold SUPER_USER. Now 00000 starts with no usable password and
only the local one-time ``scripts/bootstrap_css_admin.py`` can initialize it.
"""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime

import pytest

from dashboard.auth import css_sign_on
from dashboard.auth.css_sign_on import (
    BOOTSTRAP_INITIALIZED,
    BOOTSTRAP_REQUIRED,
    INITIAL_ADMIN_ID,
    INITIAL_ADMIN_PASSWORD,
)
from dashboard.mobile import mobile_app
from engine.commercial.commercial_audit import CommercialAuditLog
from scripts import bootstrap_css_admin
from tests.asgi_test_client import AsgiTestClient as TestClient
from tests.test_operator_authentication import operator_env  # noqa: F401  (fixture)

ADMIN_PW = "Admin-Bootstrap-Pass-42!"


@pytest.fixture
def store(tmp_path):
    return tmp_path / "users.json"


def _bootstrap(store, password=ADMIN_PW, confirm=None, monkeypatch=None):
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{password}\n{confirm or password}\n"))
    return bootstrap_css_admin.main(["--users-file", str(store), "--stdin"])


# ---------------------------------------------------------------------------
# Fresh store: nothing can claim or use 00000 remotely
# ---------------------------------------------------------------------------


def test_fresh_store_admin_has_no_usable_password(store):
    users = css_sign_on.load_users(store)
    admin = users[INITIAL_ADMIN_ID]
    assert admin["bootstrap_state"] == BOOTSTRAP_REQUIRED
    assert admin["password_hash"] == ""
    for guess in (INITIAL_ADMIN_PASSWORD, "", "admin", "password"):
        assert not css_sign_on.verify_password(guess, admin["password_hash"])


@pytest.mark.parametrize("password", [INITIAL_ADMIN_PASSWORD, "", "anything"])
def test_fresh_store_admin_cannot_sign_in(store, password):
    users = css_sign_on.load_users(store)
    with pytest.raises(css_sign_on.AuthFailure) as exc:
        css_sign_on.authenticate_credentials(users, INITIAL_ADMIN_ID, password)
    assert exc.value.code == "ACCOUNT_NOT_INITIALIZED"


def test_operator_api_cannot_claim_the_admin_with_the_old_default(operator_env):  # noqa: F811
    # operator_env's store was created fresh, so it holds an uninitialized 00000.
    resp = operator_env.post("/auth/operator/change-password", json={
        "user_id": INITIAL_ADMIN_ID, "current_password": INITIAL_ADMIN_PASSWORD,
        "new_password": "Attacker-Chosen-Pass-1!", "confirm_password": "Attacker-Chosen-Pass-1!",
    })
    assert resp.status_code == 401
    login = operator_env.post("/auth/operator/login", json={"user_id": INITIAL_ADMIN_ID, "password": INITIAL_ADMIN_PASSWORD})
    assert login.status_code == 401
    assert css_sign_on.load_users()[INITIAL_ADMIN_ID]["bootstrap_state"] == BOOTSTRAP_REQUIRED


def test_mobile_login_cannot_claim_the_admin_with_the_old_default(store, monkeypatch):
    real_load, real_save = css_sign_on.load_users, css_sign_on.save_users
    monkeypatch.setattr(mobile_app, "load_users", lambda *_a, **_k: real_load(store))
    monkeypatch.setattr(mobile_app, "save_users", lambda users, *_a, **_k: real_save(users, store))
    client = TestClient(mobile_app.app)
    resp = client.post("/login", data={"user_id": INITIAL_ADMIN_ID, "password": INITIAL_ADMIN_PASSWORD})
    assert resp.status_code != 303  # no session, no password-change page
    assert "css_mobile_session" not in resp.headers.get("set-cookie", "")
    assert "css_mobile_password_change" not in resp.headers.get("set-cookie", "")


def test_change_password_primitive_refuses_an_uninitialized_admin(store):
    users = css_sign_on.load_users(store)
    with pytest.raises(css_sign_on.PasswordValidationError):
        css_sign_on.change_password(users, INITIAL_ADMIN_ID, "Some-New-Pass-9!", "Some-New-Pass-9!")
    assert users[INITIAL_ADMIN_ID]["password_hash"] == ""


def test_no_network_route_can_reach_the_bootstrap():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    callers = []
    for top in ("backend", "dashboard", "engine"):
        for path in (root / top).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if "bootstrap_initial_admin(" in text:
                callers.append(path.relative_to(root).as_posix())
    assert callers == ["dashboard/auth/css_sign_on.py"]  # its definition only


# ---------------------------------------------------------------------------
# Local one-time bootstrap
# ---------------------------------------------------------------------------


def test_local_bootstrap_initializes_and_admin_signs_in_normally(store, monkeypatch, capsys):
    assert _bootstrap(store, monkeypatch=monkeypatch) == 0
    out = capsys.readouterr().out
    assert ADMIN_PW not in out
    users = css_sign_on.load_users(store)
    assert users[INITIAL_ADMIN_ID]["bootstrap_state"] == BOOTSTRAP_INITIALIZED
    ctx = css_sign_on.authenticate_credentials(users, INITIAL_ADMIN_ID, ADMIN_PW)
    assert ctx["role"] == "SUPER_USER"


def test_bootstrap_cannot_be_replayed(store, monkeypatch, capsys):
    assert _bootstrap(store, monkeypatch=monkeypatch) == 0
    before = json.loads(store.read_text())[INITIAL_ADMIN_ID]["password_hash"]
    assert _bootstrap(store, password="Replay-Takeover-Pass-1!", monkeypatch=monkeypatch) == 2
    assert "already initialized" in capsys.readouterr().out
    assert json.loads(store.read_text())[INITIAL_ADMIN_ID]["password_hash"] == before
    users = css_sign_on.load_users(store)
    with pytest.raises(css_sign_on.AuthFailure) as exc:
        css_sign_on.bootstrap_initial_admin(users, "Replay-Takeover-Pass-1!", "Replay-Takeover-Pass-1!")
    assert exc.value.code == "BOOTSTRAP_ALREADY_COMPLETE"


@pytest.mark.parametrize("password,confirm", [
    (INITIAL_ADMIN_PASSWORD, INITIAL_ADMIN_PASSWORD),   # the published default is deny-listed
    ("short", "short"),
    ("Admin-Bootstrap-Pass-42!", "mismatch"),
])
def test_bootstrap_enforces_password_policy_and_stays_uninitialized(store, monkeypatch, password, confirm):
    assert _bootstrap(store, password=password, confirm=confirm, monkeypatch=monkeypatch) == 1
    assert css_sign_on.load_users(store)[INITIAL_ADMIN_ID]["bootstrap_state"] == BOOTSTRAP_REQUIRED


def test_bootstrap_secret_is_never_logged_or_stored_in_clear(store, monkeypatch, tmp_path, capsys):
    db = str(tmp_path / "auth.sqlite3")
    monkeypatch.setenv("CSS_AUTH_AUDIT_DB", db)
    assert _bootstrap(store, monkeypatch=monkeypatch) == 0
    events = CommercialAuditLog(db).events(object_type="operator_auth")
    assert [(e.action, e.outcome) for e in events] == [("ADMIN_BOOTSTRAP", "SUCCEEDED")]
    assert ADMIN_PW not in repr(events)
    assert ADMIN_PW not in store.read_text()
    assert ADMIN_PW not in capsys.readouterr().out


def test_bootstrap_command_takes_no_password_argument():
    with pytest.raises(SystemExit):
        bootstrap_css_admin.main(["--password", "x"])


def test_no_default_credential_is_committed_as_a_usable_hash():
    import pathlib

    source = (pathlib.Path(css_sign_on.__file__)).read_text(encoding="utf-8")
    assert "hash_password(INITIAL_ADMIN_PASSWORD)" not in source


# ---------------------------------------------------------------------------
# Initialized admin: normal rules still apply
# ---------------------------------------------------------------------------


def test_initialized_admin_is_subject_to_lockout_and_disable(store, monkeypatch):
    assert _bootstrap(store, monkeypatch=monkeypatch) == 0
    users = css_sign_on.load_users(store)
    for _ in range(3):
        with pytest.raises(css_sign_on.AuthFailure):
            css_sign_on.authenticate_credentials(users, INITIAL_ADMIN_ID, "wrong-guess")
    with pytest.raises(css_sign_on.AuthFailure) as exc:
        css_sign_on.authenticate_credentials(users, INITIAL_ADMIN_ID, ADMIN_PW)
    assert exc.value.code == "AUTH_LOCKOUT"

    css_sign_on.clear_lockout_state(users[INITIAL_ADMIN_ID], preserve_failed_attempts=False)
    users[INITIAL_ADMIN_ID]["disabled"] = True
    with pytest.raises(css_sign_on.AuthFailure) as exc:
        css_sign_on.authenticate_credentials(users, INITIAL_ADMIN_ID, ADMIN_PW)
    assert exc.value.code == "ACCOUNT_DISABLED"


# ---------------------------------------------------------------------------
# Existing installations
# ---------------------------------------------------------------------------


def _legacy_admin(password_hash, **extra):
    record = {
        "user_id": INITIAL_ADMIN_ID, "display_name": "CSS Administrator", "role": "SUPER_USER",
        "unit_code": "CORE", "home_branch": "HQ", "password_hash": password_hash,
        "must_change_password": True, "last_password_change": None, "password_history": [],
        "failed_attempts": 0, "locked": False, "locked_at": None, "lockout_until": None,
        "lockout_seconds": 0, "lockout_started_at": None,
    }
    record.update(extra)
    return record


@pytest.mark.parametrize("legacy_hash", [
    css_sign_on.hash_password(INITIAL_ADMIN_PASSWORD),                       # salted default
    hashlib.sha256(INITIAL_ADMIN_PASSWORD.encode("utf-8")).hexdigest(),      # pre-COM-011 unsalted default
])
def test_unclaimed_legacy_admin_is_neutralized_on_load(store, legacy_hash):
    store.write_text(json.dumps({INITIAL_ADMIN_ID: _legacy_admin(legacy_hash)}), encoding="utf-8")
    users = css_sign_on.load_users(store)
    admin = users[INITIAL_ADMIN_ID]
    assert admin["bootstrap_state"] == BOOTSTRAP_REQUIRED and admin["password_hash"] == ""
    with pytest.raises(css_sign_on.AuthFailure):
        css_sign_on.authenticate_credentials(users, INITIAL_ADMIN_ID, INITIAL_ADMIN_PASSWORD)
    # Persisted, so the neutralization is not re-derived (or undone) later.
    assert json.loads(store.read_text())[INITIAL_ADMIN_ID]["bootstrap_state"] == BOOTSTRAP_REQUIRED


def test_already_claimed_legacy_admin_keeps_working_unchanged(store):
    real_hash = css_sign_on.hash_password("Previously-Claimed-Pass-3!")
    store.write_text(json.dumps({INITIAL_ADMIN_ID: _legacy_admin(
        real_hash, must_change_password=False,
        last_password_change=datetime.now().isoformat(timespec="seconds"))}), encoding="utf-8")
    users = css_sign_on.load_users(store)
    assert users[INITIAL_ADMIN_ID]["bootstrap_state"] == BOOTSTRAP_INITIALIZED
    assert users[INITIAL_ADMIN_ID]["password_hash"] == real_hash
    assert css_sign_on.authenticate_credentials(users, INITIAL_ADMIN_ID, "Previously-Claimed-Pass-3!")["role"] == "SUPER_USER"


def test_other_operators_are_untouched_by_the_migration(store):
    users = css_sign_on.load_users(store)
    css_sign_on.create_user(users, {"user_id": INITIAL_ADMIN_ID, "role": "SUPER_USER"}, "10001", "Op",
                            "FINCON", "fincon-pass-1", must_change_password=False)
    users["10001"]["last_password_change"] = datetime.now().isoformat(timespec="seconds")
    css_sign_on.save_users(users, store)
    reloaded = css_sign_on.load_users(store)
    assert "bootstrap_state" not in reloaded["10001"]
    assert css_sign_on.authenticate_credentials(reloaded, "10001", "fincon-pass-1")["role"] == "FINCON"
