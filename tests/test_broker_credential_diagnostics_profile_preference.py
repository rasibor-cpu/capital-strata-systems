from __future__ import annotations

import backend.runtime.broker_credential_diagnostics as diag


def _write_test_pem(tmp_path):
    pem = tmp_path / "coinbase_private_key.pem"
    pem.write_text(
        "-----BEGIN EC PRIVATE KEY-----\n"
        "TEST_ONLY_NOT_A_REAL_KEY\n"
        "-----END EC PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    return pem


def test_diagnostics_prefers_live_read_only_profile(monkeypatch, tmp_path):
    calls: list[str] = []
    pem = _write_test_pem(tmp_path)

    def fake_load_credentials(broker_name: str, mode: str = "paper", base_dir: str = "."):
        calls.append(mode)
        if mode == "live_read_only":
            return {
                "COINBASE_CDP_KEY_NAME": "organizations/example/apiKeys/example",
                "COINBASE_CDP_PRIVATE_KEY_PATH": str(pem),
            }
        return {}

    import backend.app.brokers.credential_loader as loader
    monkeypatch.setattr(loader, "load_credentials", fake_load_credentials)
    diag._cached_diagnostic_source_from_canonical_loader.cache_clear()

    result = diag.diagnose_broker_credentials("coinbase")

    assert calls[0] == "live_read_only"
    assert result.key_present is True
    assert result.private_key_present is True
    assert result.pem_valid is True
    assert result.credentials_present is True
    assert result.execution_allowed is False
    assert result.live_trading_blocked is True


def test_diagnostics_falls_back_to_paper_when_read_only_profile_empty(monkeypatch, tmp_path):
    calls: list[str] = []
    pem = _write_test_pem(tmp_path)

    def fake_load_credentials(broker_name: str, mode: str = "paper", base_dir: str = "."):
        calls.append(mode)
        if mode == "paper":
            return {
                "COINBASE_CDP_KEY_NAME": "organizations/example/apiKeys/example",
                "COINBASE_CDP_PRIVATE_KEY_PATH": str(pem),
            }
        return {}

    import backend.app.brokers.credential_loader as loader
    monkeypatch.setattr(loader, "load_credentials", fake_load_credentials)
    diag._cached_diagnostic_source_from_canonical_loader.cache_clear()

    result = diag.diagnose_broker_credentials("coinbase")

    assert calls[:2] == ["live_read_only", "paper"]
    assert result.key_present is True
    assert result.private_key_present is True
    assert result.pem_valid is True
    assert result.credentials_present is True
