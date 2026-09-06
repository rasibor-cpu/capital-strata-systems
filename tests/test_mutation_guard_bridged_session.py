from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.security import mutation_guard


def _request(*, headers=None, method="POST"):
    raw_headers = [
        (str(k).lower().encode("latin-1"), str(v).encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": "/api/v1/questrade/mission-control/activate",
            "raw_path": b"/api/v1/questrade/mission-control/activate",
            "query_string": b"",
            "headers": raw_headers,
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8765),
        }
    )


def test_valid_canonical_bridged_session_authorizes_mutation_with_csrf(monkeypatch):
    monkeypatch.setenv("CSS_HOST_SECURITY_PROFILE", "fail_closed")
    monkeypatch.delenv("CSS_AUTH_TEST_PROFILE", raising=False)

    from dashboard.auth import session_bridge

    monkeypatch.setattr(
        session_bridge,
        "load_bridged_session_context",
        lambda **kwargs: SimpleNamespace(
            authenticated=True,
            active=True,
            user_id="00000",
            role="SUPER_USER",
            session_id="session-test",
        ),
    )

    result = mutation_guard.require_mutation_auth(
        _request(headers={"X-Requested-With": "XMLHttpRequest"})
    )

    assert result["user_id"] == "00000"
    assert result["role"] == "SUPER_USER"
    assert result["source"] == "bridged_session"


def test_bridged_session_still_requires_csrf(monkeypatch):
    monkeypatch.setenv("CSS_HOST_SECURITY_PROFILE", "fail_closed")

    from dashboard.auth import session_bridge

    monkeypatch.setattr(
        session_bridge,
        "load_bridged_session_context",
        lambda **kwargs: SimpleNamespace(
            authenticated=True,
            active=True,
            user_id="00000",
            role="SUPER_USER",
            session_id="session-test",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        mutation_guard.require_mutation_auth(_request())

    assert exc.value.status_code == 403
    assert exc.value.detail == "CSRF_TOKEN_REQUIRED"


def test_invalid_bridged_session_fails_closed(monkeypatch):
    monkeypatch.setenv("CSS_HOST_SECURITY_PROFILE", "fail_closed")

    from dashboard.auth import session_bridge

    monkeypatch.setattr(
        session_bridge,
        "load_bridged_session_context",
        lambda **kwargs: SimpleNamespace(
            authenticated=False,
            active=False,
            user_id="",
            role="",
            session_id="",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        mutation_guard.require_mutation_auth(
            _request(headers={"X-Requested-With": "XMLHttpRequest"})
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "MUTATION_AUTH_REQUIRED"


def test_untrusted_identity_headers_cannot_fall_through_to_bridge(monkeypatch):
    monkeypatch.setenv("CSS_HOST_SECURITY_PROFILE", "fail_closed")
    monkeypatch.delenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", raising=False)

    from dashboard.auth import session_bridge

    monkeypatch.setattr(
        session_bridge,
        "load_bridged_session_context",
        lambda **kwargs: SimpleNamespace(
            authenticated=True,
            active=True,
            user_id="00000",
            role="SUPER_USER",
            session_id="session-test",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        mutation_guard.require_mutation_auth(
            _request(
                headers={
                    "X-CSS-User-Id": "forged",
                    "X-CSS-Role": "SUPER_USER",
                    "X-Requested-With": "XMLHttpRequest",
                }
            )
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "MUTATION_AUTH_REQUIRED"
