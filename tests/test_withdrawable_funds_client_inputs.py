"""Register item #6: client-supplied withdrawable-funds figures never become financial authority.

``GET /api/v1/withdrawable-funds-summary`` computes an advisory estimate from
amounts supplied in the query string. These tests prove a caller manipulating
those amounts cannot create withdrawable funds anywhere authoritative, write
to any ledger/store, reach any external provider, or obtain money-movement,
withdrawal or execution authority -- and that malformed amounts are a clean
422, not an unhandled 500.
"""
from __future__ import annotations

import socket
import sqlite3

import pytest
from fastapi import FastAPI

import backend.app.auth.token_store as token_store_module
from backend.app.auth.token_store import TokenStore
from dashboard.runtime.client_earnings_router import create_client_earnings_router
from tests.asgi_test_client import AsgiTestClient as TestClient

BASE = "/api/v1/withdrawable-funds-summary?account_reference=ACCT-1&account_currency=USD&as_of=2026-09-29T00:00:00Z"
INFLATED = (
    BASE
    + "&total_cash=999999999999&settled_cash=999999999999&reserved_for_open_orders=0"
    "&reserved_for_margin_or_positions=0&pending_css_charge=0&other_restricted_amount=0"
    "&data_freshness=CURRENT&is_complete=true"
)


@pytest.fixture
def client_and_token(monkeypatch):
    store = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", store)
    app = FastAPI()
    app.router.routes.extend(create_client_earnings_router().routes)
    return TestClient(app), store.create_session("10001", ["FINCON"])


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_inflated_client_figures_are_labelled_non_authoritative_and_grant_nothing(client_and_token):
    client, token = client_and_token
    resp = client.get(INFLATED, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    # The arithmetic is echoed back as an estimate...
    assert body["available_to_withdraw"] == "999999999999"
    # ...but never as authority.
    assert body["input_provenance"] == "CLIENT_SUPPLIED"
    assert body["authoritative"] is False
    assert body["money_movement_allowed"] is False
    assert body["broker_withdrawal_allowed"] is False
    assert body["execution_authority"] is False
    assert "not from authoritative broker or ledger state" in body["advisory_note"]


def test_the_route_performs_no_persistence_and_no_network_io(client_and_token, monkeypatch):
    client, token = client_and_token

    def _forbidden(*_a, **_k):
        raise AssertionError("withdrawable-funds summary must not touch storage or the network")

    real_connect = socket.socket.connect

    def _loopback_only(sock, address):
        # asyncio's Windows event loop builds its self-pipe with a loopback
        # socketpair; anything else would be an outbound connection.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return real_connect(sock, address)
        _forbidden()

    monkeypatch.setattr(sqlite3, "connect", _forbidden)
    monkeypatch.setattr(socket.socket, "connect", _loopback_only)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", _forbidden)
    resp = client.get(INFLATED, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["authoritative"] is False


def test_repeated_manipulation_leaves_no_state_behind(client_and_token):
    client, token = client_and_token
    first = client.get(INFLATED, headers=_auth(token)).json()
    plain = client.get(BASE + "&settled_cash=10", headers=_auth(token)).json()
    # Nothing from the inflated call persisted into a later, unrelated call.
    assert first["available_to_withdraw"] == "999999999999"
    assert plain["available_to_withdraw"] == "10"
    assert plain["is_complete"] is False and "INCOMPLETE_BROKER_DATA" in plain["restriction_reasons"]


@pytest.mark.parametrize("bad", ["abc", "NaN", "Infinity", "-5", "", "1,000"])
def test_malformed_or_negative_amounts_are_422_not_500(client_and_token, bad):
    client, token = client_and_token
    resp = client.get(BASE + f"&settled_cash={bad}", headers=_auth(token))
    assert resp.status_code == 422
    text = resp.content.decode()
    assert "Traceback" not in text and ".py" not in text


def test_non_canonical_currency_is_422_not_500(client_and_token):
    client, token = client_and_token
    resp = client.get(BASE.replace("account_currency=USD", "account_currency=usd"), headers=_auth(token))
    assert resp.status_code == 422


def test_still_requires_commercial_view_rights(client_and_token):
    client, _token = client_and_token
    assert client.get(INFLATED).status_code == 401
    trader = token_store_module.token_store.create_session("10009", ["TRADER"])
    assert client.get(INFLATED, headers=_auth(trader)).status_code == 403
