"""Suite-wide test isolation.

``backend.app.auth.auth_audit`` is on by default and writes to
``data/css_auth_audit.sqlite3`` unless ``CSS_AUTH_AUDIT_DB`` says otherwise, so
any test that logs in, logs out or is denied would otherwise append synthetic
events to the real authentication audit trail of whatever checkout runs the
suite. Point every test at its own throwaway database; tests that inspect the
audit trail still override this with their own fixture.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_auth_audit_db(tmp_path, monkeypatch):
    monkeypatch.setenv("CSS_AUTH_AUDIT_DB", str(tmp_path / "css_auth_audit.sqlite3"))
