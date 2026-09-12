import json
from io import BytesIO
from datetime import timedelta
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from backend.brokers.questrade_client import ProviderUnavailableError
from backend.brokers.questrade_oauth_manager import AuthRequiredError
from backend.brokers.questrade_oauth_manager import FileQuestradeCredentialStore, TokenEndpointError
from backend.brokers.questrade_provider_config import QuestradeProviderConfig, mask_account_identifier, select_account
from backend.brokers.questrade_readonly_service import provider_failure_status, validate_readonly_provider
from dashboard.runtime.mission_control_state import build_mission_control_state
from tools import questrade_readonly_bootstrap


def test_file_store_rotates_atomically_without_exposing_token(tmp_path):
    path = tmp_path / "state" / "questrade" / "credentials.json"
    store = FileQuestradeCredentialStore(str(path))
    store.replace_refresh_token("first-secret")
    store.replace_refresh_token("second-secret")
    assert store.read_refresh_token() == "second-secret"
    assert "second-secret" in path.read_text(encoding="utf-8")
    assert "second-secret" not in repr(store)


def test_corrupt_or_missing_store_fails_closed(tmp_path):
    store = FileQuestradeCredentialStore(str(tmp_path / "missing.json"))
    assert store.read_refresh_token() is None
    path = tmp_path / "bad.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        FileQuestradeCredentialStore(str(path)).read_refresh_token()


def test_provider_configuration_defaults_disabled_and_selection_is_explicit():
    config = QuestradeProviderConfig()
    assert config.enabled is False
    with pytest.raises(RuntimeError, match="CONFIGURATION_REQUIRED"):
        config.require_enabled()
    with pytest.raises(RuntimeError, match="CONFIGURATION_REQUIRED"):
        select_account([{"number": "A"}, {"number": "B"}])
    assert select_account([{"number": "A"}], None)["number"] == "A"
    assert select_account([{"number": "A"}, {"number": "B"}], "B")["number"] == "B"


def test_account_masking_does_not_expose_full_identifier():
    assert mask_account_identifier("123456789") == "*****6789"
    assert "123456789" not in mask_account_identifier("123456789")


def test_authenticated_read_only_mission_control_remains_fail_closed():
    state = build_mission_control_state({
        "broker_name": "QUESTRADE",
        "account_mode": "LIVE_READ_ONLY",
        "capital_provenance": "REAL_BROKER",
        "status": "AVAILABLE",
        "timestamp": "2099-01-01T00:00:00+00:00",
        "account": {"accountId": "A"},
        "balances": {"cash": "1"},
        "positions": [],
    })
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True
    assert state.broker_execution_armed is False
    assert state.advisory_only is True


def test_bootstrap_uses_hidden_input_and_redacts_status(monkeypatch, tmp_path):
    class FakeTokenTransport:
        def post_token(self, **kwargs):
            assert kwargs == {"refresh_token": "authorization-secret"}
            return {
                "token_type": "Bearer",
                "access_token": "access-secret",
                "refresh_token": "refresh-secret",
                "expires_in": 300,
                "api_server": "https://api.example.test",
            }

    class FakeValidationTransport:
        def get(self, url, *, headers, timeout):
            assert "access-secret" in headers["Authorization"]
            return SimpleNamespace(status_code=200, headers={}, json=lambda: {"time": "ok"})

    monkeypatch.setattr(questrade_readonly_bootstrap, "_TokenTransport", FakeTokenTransport)
    monkeypatch.setattr(questrade_readonly_bootstrap, "_ValidationTransport", FakeValidationTransport)
    monkeypatch.setattr(questrade_readonly_bootstrap.getpass, "getpass", lambda prompt: "authorization-secret")
    result = questrade_readonly_bootstrap.bootstrap(
        store_path=tmp_path / "credentials.json",
    )

    assert result["credential_status"] == "STORED"
    assert "access-secret" not in json.dumps(result)
    assert "refresh-secret" not in json.dumps(result)
    assert FileQuestradeCredentialStore(str(tmp_path / "credentials.json")).read_refresh_token() == "refresh-secret"


def test_manual_bootstrap_does_not_persist_failed_redemption(monkeypatch, tmp_path):
    class FailedTokenTransport:
        def post_token(self, **kwargs):
            assert kwargs == {"refresh_token": "manual-token"}
            raise RuntimeError("mocked provider failure")

    monkeypatch.setattr(questrade_readonly_bootstrap, "_TokenTransport", FailedTokenTransport)
    monkeypatch.setattr(questrade_readonly_bootstrap.getpass, "getpass", lambda prompt: "manual-token")

    with pytest.raises(RuntimeError, match="mocked provider failure"):
        questrade_readonly_bootstrap.bootstrap(store_path=tmp_path / "credentials.json")
    assert not (tmp_path / "credentials.json").exists()


@pytest.mark.parametrize(
    ("status", "category"),
    [(400, "AUTH_REQUIRED"), (401, "AUTH_REQUIRED"), (403, "AUTH_REQUIRED"), (429, "PROVIDER_RATE_LIMITED"), (500, "PROVIDER_UNAVAILABLE")],
)
def test_token_endpoint_http_errors_are_classified_and_redacted(monkeypatch, status, category):
    body = json.dumps({
        "error": "invalid_grant",
        "error_description": "refresh_token=manual-secret access_token=access-secret",
    }).encode("utf-8")
    error = HTTPError("https://login.example.test", status, "provider", {"Content-Type": "application/json"}, BytesIO(body))
    monkeypatch.setattr(questrade_readonly_bootstrap.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(error))

    with pytest.raises(TokenEndpointError) as raised:
        questrade_readonly_bootstrap._TokenTransport().post_token(refresh_token="manual-secret")
    assert raised.value.category == category
    assert raised.value.diagnostics["http_status"] == status
    assert raised.value.diagnostics["safe_error_code"] == "invalid_grant"
    assert "manual-secret" not in json.dumps(raised.value.diagnostics)
    assert "access-secret" not in json.dumps(raised.value.diagnostics)


def test_token_endpoint_success_reports_safe_presence_metadata(monkeypatch):
    class Response:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"access_token": "access-secret", "refresh_token": "refresh-secret", "expires_in": 300, "api_server": "https://api.example.test", "token_type": "Bearer"}).encode("utf-8")

    monkeypatch.setattr(questrade_readonly_bootstrap.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    transport = questrade_readonly_bootstrap._TokenTransport()
    transport.post_token(refresh_token="manual-secret")
    assert transport.last_diagnostics["http_status"] == 200
    assert all(transport.last_diagnostics[key] for key in ("access_token_present", "refresh_token_present", "expires_in_present", "api_server_present", "token_type_present"))
    assert "access-secret" not in json.dumps(transport.last_diagnostics)


def test_token_endpoint_invalid_json_is_malformed(monkeypatch):
    class Response:
        status = 200
        headers = {"Content-Type": "text/plain"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"not-json"

    monkeypatch.setattr(questrade_readonly_bootstrap.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(TokenEndpointError) as raised:
        questrade_readonly_bootstrap._TokenTransport().post_token(refresh_token="manual-secret")
    assert raised.value.category == "MALFORMED_RESPONSE"
    assert raised.value.diagnostics["response_keys"] == []


def test_token_endpoint_success_missing_required_field_is_malformed(monkeypatch):
    class Response:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"access_token": "access-secret", "expires_in": 300, "api_server": "https://api.example.test"}).encode("utf-8")

    monkeypatch.setattr(questrade_readonly_bootstrap.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(TokenEndpointError) as raised:
        questrade_readonly_bootstrap._TokenTransport().post_token(refresh_token="manual-secret")
    assert raised.value.category == "MALFORMED_RESPONSE"
    assert raised.value.diagnostics["access_token_present"] is True
    assert raised.value.diagnostics["refresh_token_present"] is False


def test_token_endpoint_plain_text_error_is_safely_described(monkeypatch):
    class ResponseHeaders:
        def get(self, key):
            return "text/plain; charset=UTF-8"

    body = b"Forbidden refresh_token=manual-secret access_token=access-secret"
    error = HTTPError("https://login.example.test", 403, "provider", ResponseHeaders(), BytesIO(body))
    monkeypatch.setattr(questrade_readonly_bootstrap.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(error))

    with pytest.raises(TokenEndpointError) as raised:
        questrade_readonly_bootstrap._TokenTransport().post_token(refresh_token="manual-secret")
    diagnostics = raised.value.diagnostics
    assert diagnostics["http_status"] == 403
    assert diagnostics["content_type"] == "text/plain; charset=UTF-8"
    assert diagnostics["response_keys"] == []
    assert diagnostics["safe_error_description"] == "Forbidden refresh_token=<redacted> access_token=<redacted>"
    assert "manual-secret" not in json.dumps(diagnostics)
    assert "access-secret" not in json.dumps(diagnostics)


def test_readonly_validation_is_redacted_and_failures_are_classified():
    client = SimpleNamespace(
        last_rate_limit=SimpleNamespace(remaining="7", reset="42"),
        get_accounts=lambda: {"accounts": [{"number": "123456789", "currency": "CAD"}]},
        get_balances=lambda account_id: {"cash": "12.00"},
        get_positions=lambda account_id: {"positions": [{"symbol": "ABC"}]},
    )
    result = validate_readonly_provider(client, QuestradeProviderConfig(enabled=True), now=None)

    assert result["masked_account_id"] == "*****6789"
    assert "123456789" not in json.dumps(result)
    assert result["execution_allowed"] is False
    assert provider_failure_status(AuthRequiredError("redacted")) == "AUTH_REQUIRED"
    assert provider_failure_status(ProviderUnavailableError("unavailable")) == "PROVIDER_UNAVAILABLE"
