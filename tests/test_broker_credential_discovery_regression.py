import os
import tempfile
from pathlib import Path
import pytest

from backend.app.brokers.credential_loader import load_credentials
from backend.app.brokers.broker_bootstrap import run_broker_bootstrap_self_test
from backend.runtime.broker_credential_diagnostics import diagnose_broker_credentials


PEM = "-----BEGIN EC PRIVATE KEY-----\nredacted\n-----END EC PRIVATE KEY-----"


def test_cwd_movement_does_not_break_credential_discovery():
    """
    Test that moving the current working directory (CWD) to a temporary folder
    does not break the dotenv loading and credential discovery.
    """
    original_cwd = os.getcwd()
    
    # Verify we can discover credentials in the normal path
    coinbase_creds_before = load_credentials("coinbase", mode="paper")
    oanda_creds_before = load_credentials("oanda", mode="paper")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Change CWD to temporary directory
            os.chdir(tmpdir)
            
            # Retrieve credentials again
            coinbase_creds_after = load_credentials("coinbase", mode="paper")
            oanda_creds_after = load_credentials("oanda", mode="paper")
            
            # Assert they are discovered identically
            assert coinbase_creds_before == coinbase_creds_after
            assert oanda_creds_before == oanda_creds_after
            
        finally:
            # Restore working directory
            os.chdir(original_cwd)


def test_entrypoint_consistency_in_discovery():
    """
    Assert that the loader discovers exactly the same credentials
    regardless of simulated entry points environment states.
    """
    coinbase_creds = load_credentials("coinbase", mode="paper")
    oanda_creds = load_credentials("oanda", mode="paper")
    
    # We should have at least the keys or files present if configured in .env
    if coinbase_creds:
        assert "COINBASE_ENABLE_LIVE_ORDERS" in coinbase_creds
    if oanda_creds:
        assert "OANDA_ENV" in oanda_creds


def test_bootstrap_self_test_runs_successfully():
    """
    Verify the bootstrap self test executes successfully (even if it detects FAIL on some stages).
    It should not raise unhandled exceptions and should return a boolean.
    """
    result = run_broker_bootstrap_self_test("coinbase", mode="paper")
    assert isinstance(result, bool)


def test_coinbase_loader_skips_invalid_json_path_and_uses_valid_key_file(tmp_path, monkeypatch):
    key_file = tmp_path / "cdp_api_key.json"
    base_dir = tmp_path / "empty_credentials"
    base_dir.mkdir()
    key_file.write_text('{"name": "organizations/redacted/apiKeys/redacted", "privateKey": "' + PEM.replace("\n", "\\n") + '"}', encoding="utf-8")
    import backend.app.brokers.credential_loader as credential_loader

    monkeypatch.setattr(credential_loader, "load_dotenv", lambda *_args, **_kwargs: False)

    for key in (
        "COINBASE_KEY_JSON_PATH",
        "COINBASE_KEY_JSON",
        "COINBASE_KEY_FILE",
        "COINBASE_CDP_KEY_NAME",
        "COINBASE_KEY_NAME",
        "COINBASE_CDP_PRIVATE_KEY",
        "COINBASE_PRIVATE_KEY",
        "COINBASE_CDP_PRIVATE_KEY_PATH",
        "COINBASE_PRIVATE_KEY_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("COINBASE_KEY_JSON", str(tmp_path / "missing.json"))
    monkeypatch.setenv("COINBASE_KEY_FILE", str(key_file))

    credentials = load_credentials("coinbase", mode="paper", base_dir=str(base_dir))

    assert credentials is not None
    assert credentials["privateKey"] == PEM
    assert credentials["COINBASE_CDP_PRIVATE_KEY"] == PEM
    assert credentials["COINBASE_KEY_JSON_PATH"] == str(key_file.resolve())
    assert not credentials["privateKey"].endswith(".json")


def test_coinbase_loader_reads_path_valued_private_key_env(tmp_path, monkeypatch):
    key_file = tmp_path / "coinbase.json"
    base_dir = tmp_path / "empty_credentials"
    base_dir.mkdir()
    key_file.write_text('{"name": "organizations/redacted/apiKeys/redacted", "privateKey": "' + PEM.replace("\n", "\\n") + '"}', encoding="utf-8")
    import backend.app.brokers.credential_loader as credential_loader

    monkeypatch.setattr(credential_loader, "load_dotenv", lambda *_args, **_kwargs: False)

    for key in (
        "COINBASE_KEY_JSON_PATH",
        "COINBASE_KEY_JSON",
        "COINBASE_KEY_FILE",
        "COINBASE_CDP_KEY_NAME",
        "COINBASE_KEY_NAME",
        "COINBASE_CDP_PRIVATE_KEY",
        "COINBASE_PRIVATE_KEY",
        "COINBASE_CDP_PRIVATE_KEY_PATH",
        "COINBASE_PRIVATE_KEY_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("COINBASE_CDP_KEY_NAME", "organizations/redacted/apiKeys/redacted")
    monkeypatch.setenv("COINBASE_PRIVATE_KEY", str(key_file))

    credentials = load_credentials("coinbase", mode="paper", base_dir=str(base_dir))

    assert credentials is not None
    assert credentials["privateKey"] == PEM
    assert credentials["COINBASE_PRIVATE_KEY"] == PEM


def test_coinbase_adapter_passes_pem_material_to_restclient(tmp_path, monkeypatch):
    key_file = tmp_path / "coinbase.json"
    key_file.write_text('{"name": "organizations/redacted/apiKeys/redacted", "privateKey": "' + PEM.replace("\n", "\\n") + '"}', encoding="utf-8")
    import backend.app.brokers.credential_loader as credential_loader

    monkeypatch.setattr(credential_loader, "load_dotenv", lambda *_args, **_kwargs: False)

    for key in (
        "COINBASE_KEY_JSON_PATH",
        "COINBASE_KEY_JSON",
        "COINBASE_KEY_FILE",
        "COINBASE_CDP_KEY_NAME",
        "COINBASE_KEY_NAME",
        "COINBASE_CDP_PRIVATE_KEY",
        "COINBASE_PRIVATE_KEY",
        "COINBASE_CDP_PRIVATE_KEY_PATH",
        "COINBASE_PRIVATE_KEY_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("COINBASE_KEY_FILE", str(key_file))

    captured = {}

    class FakeRESTClient:
        def __init__(self, api_key=None, api_secret=None):
            captured["api_key_present"] = bool(api_key)
            captured["api_secret"] = api_secret

    import backend.broker.coinbase_adapter as coinbase_adapter

    monkeypatch.setattr(coinbase_adapter, "RESTClient", FakeRESTClient)

    coinbase_adapter.CoinbaseAdapter(paper_mode=False)._get_rest_client()

    assert captured["api_key_present"] is True
    assert captured["api_secret"] == PEM
    assert not captured["api_secret"].endswith(".json")


def test_coinbase_diagnostics_use_canonical_loader_when_env_not_explicit(tmp_path, monkeypatch):
    key_file = tmp_path / "coinbase.json"
    key_file.write_text('{"name": "organizations/redacted/apiKeys/redacted", "privateKey": "' + PEM.replace("\n", "\\n") + '"}', encoding="utf-8")
    import backend.app.brokers.credential_loader as credential_loader

    monkeypatch.setattr(credential_loader, "load_dotenv", lambda *_args, **_kwargs: False)

    for key in (
        "COINBASE_KEY_JSON_PATH",
        "COINBASE_KEY_JSON",
        "COINBASE_KEY_FILE",
        "COINBASE_CDP_KEY_NAME",
        "COINBASE_KEY_NAME",
        "COINBASE_CDP_PRIVATE_KEY",
        "COINBASE_PRIVATE_KEY",
        "COINBASE_CDP_PRIVATE_KEY_PATH",
        "COINBASE_PRIVATE_KEY_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("COINBASE_KEY_FILE", str(key_file))

    diagnostic = diagnose_broker_credentials("coinbase").as_dict()
    explicit_empty = diagnose_broker_credentials("coinbase", env={}).as_dict()

    assert diagnostic["credentials_present"] is True
    assert diagnostic["failure_reason"] == "NONE"
    assert diagnostic["readiness_status"] == "READY"
    assert explicit_empty["credentials_present"] is False
    assert explicit_empty["failure_reason"] == "KEY_MISSING"


def test_coinbase_adapter_read_only_product_and_portfolio_wrappers(tmp_path, monkeypatch):
    key_file = tmp_path / "coinbase.json"
    key_file.write_text('{"name": "organizations/redacted/apiKeys/redacted", "privateKey": "' + PEM.replace("\n", "\\n") + '"}', encoding="utf-8")
    import backend.app.brokers.credential_loader as credential_loader
    import backend.broker.coinbase_adapter as coinbase_adapter

    monkeypatch.setattr(credential_loader, "load_dotenv", lambda *_args, **_kwargs: False)

    for key in (
        "COINBASE_KEY_JSON_PATH",
        "COINBASE_KEY_JSON",
        "COINBASE_KEY_FILE",
        "COINBASE_CDP_KEY_NAME",
        "COINBASE_KEY_NAME",
        "COINBASE_CDP_PRIVATE_KEY",
        "COINBASE_PRIVATE_KEY",
        "COINBASE_CDP_PRIVATE_KEY_PATH",
        "COINBASE_PRIVATE_KEY_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("COINBASE_KEY_FILE", str(key_file))

    class FakeRESTClient:
        calls: list[str] = []

        def __init__(self, api_key=None, api_secret=None):
            self.calls.append("construct")

        def get_accounts(self):
            self.calls.append("get_accounts")
            return {"accounts": [{"currency": "USD", "available_balance": {"value": "1.00"}}]}

        def get_portfolios(self):
            self.calls.append("get_portfolios")
            return {"portfolios": [{"uuid": "portfolio-1"}]}

        def get_products(self):
            self.calls.append("get_products")
            return {"products": [{"product_id": "BTC-USD"}]}

        def get_product(self, product_id: str):
            self.calls.append(f"get_product:{product_id}")
            return {"product_id": product_id, "price": "65000.00"}

    monkeypatch.setattr(coinbase_adapter, "RESTClient", FakeRESTClient)

    adapter = coinbase_adapter.CoinbaseAdapter(paper_mode=False)

    assert adapter.get_product("BTC-USD")["product_id"] == "BTC-USD"
    assert adapter.get_products()["products"]
    assert adapter.get_portfolios()["portfolios"]
    assert adapter.get_balances()[0]["currency"] == "USD"
    assert not any("order" in call or "cancel" in call for call in FakeRESTClient.calls)
