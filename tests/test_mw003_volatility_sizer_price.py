"""MW-003 / RR-003 — canonical price propagation for VolatilityPositionSizer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from engine.execution.execution_gate import ExecutionGate
from engine.risk.canonical_volatility_price import (
    REASON_INSTRUMENT_MISMATCH,
    REASON_INVALID,
    REASON_MISSING,
    REASON_STALE,
    validate_canonical_price_for_volatility,
)
from engine.risk.margin_snapshot import MarginSnapshot, MarginState
from engine.risk.volatility_position_sizer import (
    VolatilityPositionSizer,
    VolatilityPriceError,
    VolatilitySizingPolicy,
)
from dashboard.mobile.mobile_app import _resolve_mobile_canonical_gate_price


def _margin() -> MarginSnapshot:
    return MarginSnapshot(
        broker="TEST",
        account_id="123",
        timestamp="2026-06-17T00:00:00Z",
        equity=10000.0,
        cash=10000.0,
        buying_power=5000.0,
        maintenance_margin=2500.0,
        initial_margin=5000.0,
        margin_used=0.0,
        margin_available=10000.0,
        margin_ratio=0.0,
        margin_state=MarginState.NORMAL,
    )


def _gate(tmp_path: Path) -> ExecutionGate:
    return ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "anti_bleed_state.json"),
        )
    )


def _gate_kwargs(**overrides):
    base = {
        "instrument": "EUR_USD",
        "side": "BUY",
        "notional": 100.0,
        "stop_distance_pct": 0.02,
        "equity": 10000.0,
        "equity_peak": 10000.0,
        "regime_persistence": 1.0,
        "expected_move_bps": 80.0,
        "fee_bps": 1.0,
        "spread_bps": 1.0,
        "slippage_bps": 1.0,
        "price": 1.10,
        "price_instrument": "EUR_USD",
        "margin_snapshot": _margin(),
        "broker_mode": "PAPER",
    }
    base.update(overrides)
    return base


def test_valid_price_reaches_sizer_and_allows(tmp_path) -> None:
    result = _gate(tmp_path).evaluate_trade(**_gate_kwargs())
    assert result["decision"]["final"] == "ALLOW"
    assert result["reason"] == "approved"
    assert result["debug"]["canonical_price"] == 1.10
    assert result["debug"]["canonical_price_source"] == "price"
    assert result["debug"]["base_notional"] == 100.0
    assert result["debug"]["vol_scaled_notional"] == 100.0  # warmup mult 1.0
    assert "vol_size_error" not in result["debug"]


def test_high_volatility_history_compresses_notional(tmp_path) -> None:
    gate = _gate(tmp_path)
    for p in [1.10, 1.20, 1.05, 1.25, 1.00, 1.30, 0.95, 1.35, 0.90, 1.40, 0.85]:
        gate.vol_sizer.size(100.0, p)
    result = gate.evaluate_trade(**_gate_kwargs(price=1.10))
    assert result["decision"]["final"] == "ALLOW"
    assert result["debug"]["vol_scaled_notional"] == 50.0
    assert result["debug"]["vol_mult"] == 0.5
    assert result["debug"]["scaled_notional"] == 50.0


def test_warmup_valid_price_is_deterministic() -> None:
    sizer = VolatilityPositionSizer(VolatilitySizingPolicy(warmup_min_obs=10))
    dbg: dict = {}
    out = sizer.size(100.0, 1.10, debug=dbg)
    assert out == 100.0
    assert dbg["vol_mult"] == 1.0


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"price": None}, REASON_MISSING),
        ({"price": 0.0}, REASON_INVALID),
        ({"price": -1.0}, REASON_INVALID),
        ({"price": float("nan")}, REASON_INVALID),
        ({"price": float("inf")}, REASON_INVALID),
        ({"price": float("-inf")}, REASON_INVALID),
        ({"price": "not-a-price"}, REASON_INVALID),
    ],
)
def test_invalid_or_missing_price_cannot_allow(tmp_path, overrides, reason) -> None:
    kwargs = _gate_kwargs()
    kwargs.update(overrides)
    if "price" in overrides and overrides["price"] is None:
        kwargs.pop("price", None)
    result = _gate(tmp_path).evaluate_trade(**kwargs)
    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"] == reason
    assert "vol_size_error" not in result["debug"]


def test_stale_price_blocked_when_freshness_enforced(tmp_path) -> None:
    stale = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    result = _gate(tmp_path).evaluate_trade(
        **_gate_kwargs(
            price=1.10,
            price_as_of=stale,
            price_max_age_seconds=30,
        )
    )
    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"] == REASON_STALE


def test_stale_validator_unit() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    price, source, reason = validate_canonical_price_for_volatility(
        instrument="EUR_USD",
        price=1.10,
        price_as_of=(now - timedelta(seconds=120)).isoformat(),
        price_max_age_seconds=30,
        now=now,
    )
    assert price is None
    assert reason == REASON_STALE
    assert source == "price"


def test_instrument_mismatch_rejected(tmp_path) -> None:
    result = _gate(tmp_path).evaluate_trade(
        **_gate_kwargs(price=1.10, price_instrument="GBP_USD")
    )
    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"] == REASON_INSTRUMENT_MISMATCH


def test_fx_and_crypto_paths_receive_price(tmp_path) -> None:
    fx = _gate(tmp_path).evaluate_trade(
        **_gate_kwargs(instrument="EUR_USD", price=1.085, price_instrument="EUR_USD")
    )
    crypto = _gate(tmp_path / "crypto").evaluate_trade(
        **_gate_kwargs(instrument="BTC-USD", price=65000.0, price_instrument="BTC-USD", notional=500.0)
    )
    assert fx["decision"]["final"] == "ALLOW"
    assert fx["debug"]["canonical_price"] == 1.085
    assert crypto["decision"]["final"] == "ALLOW"
    assert crypto["debug"]["canonical_price"] == 65000.0


def test_mobile_ticket_implied_price() -> None:
    price, source = _resolve_mobile_canonical_gate_price(
        {"symbol": "BTC-USD", "amount": 100.0, "qty": 2.0}
    )
    assert price == 50.0
    assert source == "ticket_implied_amount_over_qty"
    price2, source2 = _resolve_mobile_canonical_gate_price(
        {"symbol": "EUR_USD", "last_price": 1.1, "amount": 100.0, "qty": 2.0}
    )
    assert price2 == 1.1
    assert source2 == "last_price"


def test_direct_sizer_rejects_invalid_prices() -> None:
    sizer = VolatilityPositionSizer()
    for bad in (0.0, -1.0, float("nan"), float("inf"), float("-inf"), None, "x"):
        with pytest.raises(VolatilityPriceError):
            sizer.size(100.0, bad)  # type: ignore[arg-type]


def test_live_missing_microstructure_still_blocks(tmp_path) -> None:
    result = _gate(tmp_path).evaluate_trade(
        **_gate_kwargs(
            broker_mode="live",
            expected_move_bps=None,
            fee_bps=None,
            spread_bps=None,
            slippage_bps=None,
        )
    )
    assert result["decision"]["final"] == "BLOCK"
    assert str(result["reason"]).startswith("anti_bleed_guard:missing_anti_bleed_input")


def test_no_typeerror_missing_price_path(tmp_path) -> None:
    kwargs = _gate_kwargs()
    kwargs.pop("price")
    result = _gate(tmp_path).evaluate_trade(**kwargs)
    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"] == REASON_MISSING
    assert "missing 1 required positional argument" not in str(result.get("debug", {}))
