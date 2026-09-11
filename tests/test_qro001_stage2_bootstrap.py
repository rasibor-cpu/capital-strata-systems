import json
from datetime import timedelta

import pytest

from backend.brokers.questrade_oauth_manager import FileQuestradeCredentialStore
from backend.brokers.questrade_provider_config import QuestradeProviderConfig, mask_account_identifier, select_account
from dashboard.runtime.mission_control_state import build_mission_control_state


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
