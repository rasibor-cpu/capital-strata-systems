from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_coinbase_readonly_setup_never_persists_private_key_material():
    text = (ROOT / "scripts" / "configure_css_coinbase_readonly.ps1").read_text(
        encoding="utf-8"
    )
    assert 'SetEnvironmentVariable("COINBASE_CDP_KEY_NAME"' in text
    assert 'SetEnvironmentVariable("COINBASE_KEY_JSON_PATH"' in text
    assert 'SetEnvironmentVariable("COINBASE_ENABLE_LIVE_ORDERS", "false"' in text
    assert 'SetEnvironmentVariable("COINBASE_ENABLE_LIVE_TRADING", "false"' in text
    assert 'SetEnvironmentVariable("COINBASE_CDP_PRIVATE_KEY"' not in text
    assert 'SetEnvironmentVariable("COINBASE_PRIVATE_KEY"' not in text
    assert "private-key material was printed" in text


def test_canonical_startup_imports_only_safe_coinbase_references():
    text = (ROOT / "scripts" / "start_css_canonical.ps1").read_text(
        encoding="utf-8"
    )
    assert '"COINBASE_CDP_KEY_NAME"' in text
    assert '"COINBASE_KEY_JSON_PATH"' in text
    assert 'GetEnvironmentVariable($name, "User")' in text
    assert '$env:COINBASE_ENABLE_LIVE_ORDERS = "false"' in text
    assert '$env:COINBASE_ENABLE_LIVE_TRADING = "false"' in text
    assert 'GetEnvironmentVariable("COINBASE_CDP_PRIVATE_KEY"' not in text
    assert 'GetEnvironmentVariable("COINBASE_PRIVATE_KEY"' not in text
