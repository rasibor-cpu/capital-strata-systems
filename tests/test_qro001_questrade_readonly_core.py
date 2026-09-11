from datetime import datetime, timedelta, timezone

import pytest

from backend.app.brokers.questrade_credential_handler import InMemoryQuestradeCredentialStore
from backend.brokers.questrade_account_provider import QuestradeAccountProvider
from backend.brokers.questrade_client import (
    MalformedResponseError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    QuestradeReadOnlyClient,
    chunk_activity_range,
)
from backend.brokers.questrade_oauth_manager import (
    AuthRequiredError,
    QuestradeOAuthManager,
    QuestradeTokenSession,
    parse_token_response,
)
from dashboard.runtime.mission_control_state import build_mission_control_state


class Response:
    def __init__(self, payload, status_code=200, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, headers, timeout):
        self.calls.append((url, headers, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class TokenTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post_token(self, **kwargs):
        self.calls.append(kwargs)
        return self.payload


NOW = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)


def session(refresh="old"):
    return QuestradeTokenSession("access", refresh, "https://api.example.test", NOW + timedelta(hours=1))


def test_security_contract_exposes_no_execution_methods():
    client = QuestradeReadOnlyClient(session=session(), transport=Transport([Response({})]))
    prohibited = {"place_order", "submit_order", "modify_order", "replace_order", "cancel_order", "withdraw", "transfer", "deposit", "fund", "move_money"}
    assert not prohibited.intersection(dir(client))
    assert False is False


def test_token_parsing_is_utc_and_repr_redacts_secrets():
    parsed = parse_token_response({"access_token": "secret-a", "refresh_token": "secret-r", "expires_in": 60, "api_server": "https://api.example.test"}, now=NOW)
    assert parsed.expires_at_utc == NOW + timedelta(seconds=60)
    assert parsed.expires_at_utc.tzinfo == timezone.utc
    assert "secret-a" not in repr(parsed)
    assert "secret-r" not in repr(parsed)


def test_token_rejects_non_https_and_malformed_payload():
    with pytest.raises(Exception):
        parse_token_response({"access_token": "a", "refresh_token": "r", "expires_in": 60, "api_server": "http://bad"})
    with pytest.raises(AuthRequiredError):
        parse_token_response({"access_token": "a", "api_server": "https://api.example.test"})


def test_refresh_rotates_atomically_and_failed_refresh_preserves_old():
    store = InMemoryQuestradeCredentialStore("old")
    manager = QuestradeOAuthManager(client_id="id", client_secret="secret", credential_store=store, token_transport=TokenTransport({"access_token": "new-a", "refresh_token": "new-r", "expires_in": 300, "api_server": "https://api.example.test"}))
    assert manager.refresh().refresh_token == "new-r"
    assert store.read_refresh_token() == "new-r"
    failing = QuestradeOAuthManager(client_id="id", client_secret="secret", credential_store=store, token_transport=TokenTransport({"access_token": "new-a", "refresh_token": "bad", "expires_in": 300, "api_server": "http://not-https"}))
    with pytest.raises(Exception):
        failing.refresh()
    assert store.read_refresh_token() == "new-r"


def test_client_gets_bearer_and_captures_rate_limit():
    transport = Transport([Response({"accounts": []}, headers={"X-RateLimit-Remaining": "9", "X-RateLimit-Reset": "42"})])
    client = QuestradeReadOnlyClient(session=session(), transport=transport)
    assert client.get_accounts() == {"accounts": []}
    assert transport.calls[0][1]["Authorization"] == "Bearer access"
    assert client.last_rate_limit.remaining == "9"


def test_client_maps_http_errors_and_malformed_json():
    for response, error in [(Response({}, 429), ProviderRateLimitedError), (Response({}, 503), ProviderUnavailableError), (Response({}, 200, {}), MalformedResponseError)]:
        if isinstance(response.payload, dict) and response.status_code == 200:
            response.payload = ValueError("bad json")
        with pytest.raises(error):
            QuestradeReadOnlyClient(session=session(), transport=Transport([response])).get_time()


def test_client_refreshes_once_on_401():
    transport = Transport([Response({}, 401), Response({"time": "ok"})])
    store = InMemoryQuestradeCredentialStore("old")
    oauth = QuestradeOAuthManager(client_id="id", client_secret="secret", credential_store=store, token_transport=TokenTransport({"access_token": "new", "refresh_token": "rotated", "expires_in": 300, "api_server": "https://api.example.test"}))
    client = QuestradeReadOnlyClient(session=session(), transport=transport, oauth=oauth)
    assert client.get_time() == {"time": "ok"}
    assert transport.calls[1][1]["Authorization"] == "Bearer new"


def test_activity_chunking_has_non_overlapping_31_day_windows():
    ranges = chunk_activity_range(NOW, NOW + timedelta(days=62))
    assert len(ranges) == 2
    assert all((end - start).days <= 31 for start, end in ranges)
    assert ranges[0][1] == ranges[1][0]
    with pytest.raises(ValueError):
        chunk_activity_range(NOW, NOW - timedelta(days=1))
    with pytest.raises(ValueError):
        chunk_activity_range(NOW.replace(tzinfo=None), NOW)


def test_read_surfaces_and_provider_mapping_preserve_safety():
    transport = Transport([
        Response({"accounts": [{"number": "A1", "currency": "CAD"}]}),
        Response({"cash": "10", "equity": "12"}),
        Response({"positions": []}),
    ])
    provider = QuestradeAccountProvider(QuestradeReadOnlyClient(session=session(), transport=transport))
    snapshot = provider.snapshot("A1")
    state = build_mission_control_state({"broker_name": "QUESTRADE", "response": snapshot, "capital_provenance": "REAL_BROKER"})
    assert snapshot["provenance"] == "QUESTRADE"
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True
    assert state.broker_execution_armed is False
    assert state.advisory_only is True
