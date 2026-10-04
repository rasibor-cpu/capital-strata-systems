"""WebSocket auth for the dashboard-state feed.

Covers: anonymous/invalid/forged handshake rejection (pre-accept, so no
broker/PnL data is ever sent), a valid session succeeding, and -- the gap
this closes -- a session that is revoked or expires *after* the handshake no
longer being able to keep an already-open stream of live broker telemetry.
"""
from __future__ import annotations

import asyncio

import pytest

import backend.app.auth.token_store as token_store_module
import dashboard.runtime.ws_bridge as ws_bridge
from backend.app.auth.session_dependency import SESSION_COOKIE_NAME
from backend.app.auth.token_store import TokenStore
from dashboard.runtime.ws_bridge import create_ws_router


@pytest.fixture
def fresh_token_store(monkeypatch):
    store = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", store)
    return store


class FakeWebSocket:
    def __init__(self, cookies=None, headers=None):
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.sent = []
        self.accepted = False
        self.closed_code = None

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self, code=None):
        self.closed_code = code


def _endpoint():
    router = create_ws_router(interval_seconds=0)
    return router.routes[0].endpoint


def test_anonymous_handshake_is_rejected_before_accept(fresh_token_store):
    ws = FakeWebSocket()
    asyncio.run(_endpoint()(ws))
    assert ws.accepted is False
    assert ws.closed_code == 4401
    assert ws.sent == []


def test_forged_cookie_is_rejected_before_accept(fresh_token_store):
    ws = FakeWebSocket(cookies={SESSION_COOKIE_NAME: "forged-token"})
    asyncio.run(_endpoint()(ws))
    assert ws.accepted is False
    assert ws.closed_code == 4401
    assert ws.sent == []


def test_valid_session_is_accepted_and_streams(fresh_token_store, monkeypatch):
    token = fresh_token_store.create_session("10001", ["FINCON"], minutes=60)
    ws = FakeWebSocket(cookies={SESSION_COOKIE_NAME: token})

    call_count = {"n": 0}

    async def sleep_then_stop(_seconds):
        call_count["n"] += 1
        if call_count["n"] >= 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr(ws_bridge.asyncio, "sleep", sleep_then_stop)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_endpoint()(ws))

    assert ws.accepted is True
    assert len(ws.sent) == 1  # the initial snapshot, before the loop's first sleep


def test_session_revoked_mid_stream_closes_the_connection(fresh_token_store, monkeypatch):
    token = fresh_token_store.create_session("10001", ["FINCON"], minutes=60)
    ws = FakeWebSocket(cookies={SESSION_COOKIE_NAME: token})

    async def sleep_and_revoke(_seconds):
        fresh_token_store.revoke(token)

    monkeypatch.setattr(ws_bridge.asyncio, "sleep", sleep_and_revoke)

    asyncio.run(_endpoint()(ws))

    assert ws.accepted is True
    assert ws.closed_code == 4401


def test_session_expiry_mid_stream_closes_the_connection(fresh_token_store, monkeypatch):
    token = fresh_token_store.create_session("10001", ["FINCON"], minutes=60)
    ws = FakeWebSocket(cookies={SESSION_COOKIE_NAME: token})

    session = fresh_token_store.validate(token)

    async def sleep_and_expire(_seconds):
        # Simulate time passing past expiry without needing a real clock wait.
        object.__setattr__(session, "expires_at_utc", session.issued_at_utc)

    monkeypatch.setattr(ws_bridge.asyncio, "sleep", sleep_and_expire)

    asyncio.run(_endpoint()(ws))

    assert ws.accepted is True
    assert ws.closed_code == 4401


def test_account_disabled_mid_stream_closes_the_connection(fresh_token_store, monkeypatch):
    # Mirrors the real admin-disable flow (COM-013's disable endpoint calls
    # token_store.revoke_all_for_user immediately), rather than a bare
    # revoke, to prove disable-while-connected specifically closes the
    # socket, not just revocation in the abstract.
    token = fresh_token_store.create_session("10001", ["FINCON"], minutes=60)
    ws = FakeWebSocket(cookies={SESSION_COOKIE_NAME: token})

    async def sleep_and_disable(_seconds):
        fresh_token_store.revoke_all_for_user("10001")

    monkeypatch.setattr(ws_bridge.asyncio, "sleep", sleep_and_disable)

    asyncio.run(_endpoint()(ws))

    assert ws.accepted is True
    assert ws.closed_code == 4401


def test_revalidation_happens_on_every_tick_not_just_once(fresh_token_store, monkeypatch):
    # Proves this is bounded-interval revalidation (every loop tick), not a
    # single post-handshake check that then lets an idle connection run
    # forever regardless of later revocation.
    token = fresh_token_store.create_session("10001", ["FINCON"], minutes=60)
    ws = FakeWebSocket(cookies={SESSION_COOKIE_NAME: token})

    tick_count = {"n": 0}

    async def sleep_three_ticks_then_revoke(_seconds):
        tick_count["n"] += 1
        if tick_count["n"] >= 3:
            fresh_token_store.revoke(token)

    monkeypatch.setattr(ws_bridge.asyncio, "sleep", sleep_three_ticks_then_revoke)

    asyncio.run(_endpoint()(ws))

    assert tick_count["n"] == 3  # stayed open across two clean ticks, closed on the third
    assert ws.closed_code == 4401
