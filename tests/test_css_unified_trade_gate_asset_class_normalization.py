import time

from backend.governance.css_unified_trade_gate import (
    CSSUnifiedTradeGate,
    normalize_asset_class,
)


def _candidate(asset_class):
    return {
        "asset_class": asset_class,
        "expected_value": 10.0,
        "cost": 1.0,
        "probability": 0.80,
    }


def _session():
    return {
        "role": "TRADER",
        "created": time.time(),
    }


def _approve(asset_class, portfolio_state):
    gate = CSSUnifiedTradeGate()
    return gate.approve_trade(
        candidate=_candidate(asset_class),
        session=_session(),
        portfolio_state=portfolio_state,
        engine_mode="SAFE",
    )


def test_normalize_asset_class_lowercase_canonical_forms():
    assert normalize_asset_class("CRYPTO") == "crypto"
    assert normalize_asset_class("FX") == "fx"
    assert normalize_asset_class("FUTURES") == "futures"
    assert normalize_asset_class("OPTIONS") == "options"


def test_uppercase_crypto_enforces_same_cap_as_lowercase_crypto():
    upper = _approve("CRYPTO", {"CRYPTO": 3})
    lower = _approve("crypto", {"crypto": 3})

    assert upper.approved is False
    assert lower.approved is False


def test_uppercase_fx_enforces_same_cap_as_lowercase_fx():
    upper = _approve("FX", {"FX": 3})
    lower = _approve("fx", {"fx": 3})

    assert upper.approved is False
    assert lower.approved is False


def test_unknown_asset_class_fails_closed():
    decision = _approve("EQUITIES", {"EQUITIES": 0})

    assert decision.approved is False
    assert "unrecognized asset class" in decision.reason


def test_lowercase_crypto_behavior_remains_unchanged():
    decision = _approve("crypto", {"crypto": 0})

    assert decision.approved is True
    assert decision.details["asset_class"] == "crypto"