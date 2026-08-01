"""Phase 185A — market data and FX conversion framework offline tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from backend.app.market.fx_conversion_contract import (
    FXConversionError,
    FXConversionQuote,
    normalize_currency_code,
)
from backend.app.market.live_market_snapshot import LiveMarketSnapshot, LiveMarketSnapshotError
from backend.app.market.provider_interfaces import (
    DEFAULT_FEE_MODEL_PROVIDER,
    DEFAULT_FX_CONVERSION_PROVIDER,
    DEFAULT_MARKET_SNAPSHOT_PROVIDER,
    DEFAULT_SLIPPAGE_PROVIDER,
    FeeEstimate,
    SlippageEstimate,
    UnavailableFXConversionProvider,
    UnavailableMarketSnapshotProvider,
)
from backend.app.market.status import FRAMEWORK_VERSION, STATUS_NOT_AVAILABLE, STATUS_UNKNOWN
from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from backend.app.risk.anti_bleed_policy import MICRO_PILOT
from backend.app.risk.live_microstructure_provider import (
    DEFAULT_LIVE_MICROSTRUCTURE_PROVIDER,
    DEFAULT_MARKET_FRAMEWORK_MICROSTRUCTURE_PROVIDER,
    MarketFrameworkMicrostructureProvider,
)
from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG
from backend.runtime.live_execution_authority import AUTHORITY_CONDITIONS
from engine.execution.execution_gate import ExecutionGate
from engine.risk.margin_snapshot import MarginSnapshot, MarginState


REPO_ROOT = Path(__file__).resolve().parents[1]
GOV_DOC = REPO_ROOT / "docs" / "governance" / "PHASE_185A_MARKET_DATA_AND_FX_FRAMEWORK.md"


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


def test_phase185a_governance_document_exists() -> None:
    text = GOV_DOC.read_text(encoding="utf-8")
    assert "Does not authorize live trading" in text
    assert "NOT_AVAILABLE" in text
    assert "MarketSnapshotProvider" in text
    assert FRAMEWORK_VERSION in text or "185A" in text


def test_live_market_snapshot_immutability() -> None:
    snap = LiveMarketSnapshot.not_available()
    assert snap.status == STATUS_NOT_AVAILABLE
    assert snap.is_usable() is False
    assert snap.schema_id == "LIVE_MARKET_SNAPSHOT"
    assert snap.schema_version == "185A.1"
    with pytest.raises(FrozenInstanceError):
        snap.status = "AVAILABLE"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snap.schema_version = "MUTATED"  # type: ignore[misc]


def test_schema_ids_and_versions_present() -> None:
    snap = LiveMarketSnapshot.not_available()
    fx = FXConversionQuote.not_available(base_currency="USD", quote_currency="CAD")
    assert snap.schema_id == "LIVE_MARKET_SNAPSHOT"
    assert snap.schema_version == "185A.1"
    assert fx.schema_id == "FX_CONVERSION"
    assert fx.schema_version == "185A.1"
    assert snap.identity()["schema_id"] == "LIVE_MARKET_SNAPSHOT"
    assert fx.identity()["schema_version"] == "185A.1"


def test_provider_metadata_present_and_versioned() -> None:
    for provider in (
        DEFAULT_MARKET_SNAPSHOT_PROVIDER,
        DEFAULT_FX_CONVERSION_PROVIDER,
        DEFAULT_FEE_MODEL_PROVIDER,
        DEFAULT_SLIPPAGE_PROVIDER,
    ):
        assert provider.provider_name == "UNAVAILABLE_PROVIDER"
        assert provider.provider_version == "185A.1"
        assert provider.provider_status == STATUS_NOT_AVAILABLE
        meta = provider.metadata()
        assert meta.provider_name == "UNAVAILABLE_PROVIDER"
        assert meta.provider_version == "185A.1"
        assert meta.provider_status == STATUS_NOT_AVAILABLE
        with pytest.raises(FrozenInstanceError):
            meta.provider_version = "X"  # type: ignore[misc]

    snap = DEFAULT_MARKET_SNAPSHOT_PROVIDER.get_snapshot(symbol="EUR_USD")
    assert snap.provider == "UNAVAILABLE_PROVIDER"
    assert snap.provider_version == "185A.1"
    fx = DEFAULT_FX_CONVERSION_PROVIDER.get_conversion(
        base_currency="USD", quote_currency="CAD"
    )
    assert fx.provider_version == "185A.1"


def test_live_market_snapshot_unknown_fail_closed() -> None:
    snap = LiveMarketSnapshot.unknown()
    assert snap.status == STATUS_UNKNOWN
    assert snap.is_usable() is False
    assert snap.bid is None


def test_available_snapshot_requires_quotes() -> None:
    with pytest.raises(LiveMarketSnapshotError):
        LiveMarketSnapshot(
            bid=None,
            ask=1.1,
            mid=1.1,
            spread=0.0,
            spread_bps=0.0,
            estimated_slippage=None,
            estimated_fee=None,
            currency="USD",
            quote_timestamp="2026-08-01T00:00:00Z",
            provider="TEST",
            provider_version="1",
            quality="CERTIFIED",
            freshness="0",
            status="AVAILABLE",
        )


def test_fx_conversion_not_available_and_unknown() -> None:
    missing = FXConversionQuote.not_available(base_currency="USD", quote_currency="CAD")
    assert missing.status == STATUS_NOT_AVAILABLE
    assert missing.convert(20.0) is None
    assert missing.is_usable() is False

    unknown = FXConversionQuote.unknown(base_currency="USD", quote_currency="CAD")
    assert unknown.status == STATUS_UNKNOWN
    assert unknown.convert(20.0) is None


def test_fx_conversion_immutability_and_deterministic_convert() -> None:
    quote = FXConversionQuote(
        base_currency="USD",
        quote_currency="CAD",
        rate=1.25,
        timestamp="2026-08-01T00:00:00Z",
        provider="FIXTURE",
        provider_version="1",
        quality="CERTIFIED",
        status="AVAILABLE",
    )
    assert quote.convert(20.0) == 25.0
    with pytest.raises(FrozenInstanceError):
        quote.rate = 9.9  # type: ignore[misc]


def test_fx_available_requires_positive_rate() -> None:
    with pytest.raises(FXConversionError):
        FXConversionQuote(
            base_currency="USD",
            quote_currency="CAD",
            rate=None,
            timestamp=None,
            provider="X",
            provider_version="1",
            quality="CERTIFIED",
            status="AVAILABLE",
        )


def test_normalize_currency_code_fail_closed() -> None:
    assert normalize_currency_code("cad") == "CAD"
    assert normalize_currency_code(None) is None
    assert normalize_currency_code("UNKNOWN") is None
    assert normalize_currency_code("  ") is None


def test_provider_interfaces_return_not_available() -> None:
    snap = DEFAULT_MARKET_SNAPSHOT_PROVIDER.get_snapshot(symbol="EUR_USD")
    assert snap.status == STATUS_NOT_AVAILABLE
    fx = DEFAULT_FX_CONVERSION_PROVIDER.get_conversion(
        base_currency="USD", quote_currency="CAD"
    )
    assert fx.status == STATUS_NOT_AVAILABLE
    assert DEFAULT_FEE_MODEL_PROVIDER.estimate_fee(
        symbol="EUR_USD", notional=20.0, side="BUY"
    ).status == STATUS_NOT_AVAILABLE
    assert DEFAULT_SLIPPAGE_PROVIDER.estimate_slippage(
        symbol="EUR_USD", notional=20.0, side="BUY"
    ).status == STATUS_NOT_AVAILABLE


def test_fee_and_slippage_estimates_immutable() -> None:
    fee = FeeEstimate.not_available()
    slip = SlippageEstimate.not_available()
    with pytest.raises(FrozenInstanceError):
        fee.status = "AVAILABLE"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        slip.status = "AVAILABLE"  # type: ignore[misc]


def test_antibleed_default_microstructure_still_fail_closed() -> None:
    assert (
        DEFAULT_LIVE_MICROSTRUCTURE_PROVIDER.provide(
            symbol="EUR_USD", side="BUY", notional=20.0
        )
        is None
    )
    assert DEFAULT_LIVE_MICROSTRUCTURE_PROVIDER.provider_name == "UNAVAILABLE_PROVIDER"
    assert DEFAULT_LIVE_MICROSTRUCTURE_PROVIDER.provider_version == "185A.1"
    assert (
        DEFAULT_MARKET_FRAMEWORK_MICROSTRUCTURE_PROVIDER.provide(
            symbol="EUR_USD", side="BUY", notional=20.0
        )
        is None
    )
    assert DEFAULT_MARKET_FRAMEWORK_MICROSTRUCTURE_PROVIDER.metadata().provider_version == "185A.1"


def test_market_framework_bridge_requires_usable_providers() -> None:
    bridge = MarketFrameworkMicrostructureProvider(
        market_snapshot_provider=UnavailableMarketSnapshotProvider(),
        fee_model_provider=DEFAULT_FEE_MODEL_PROVIDER,
        slippage_provider=DEFAULT_SLIPPAGE_PROVIDER,
    )
    assert bridge.provide(symbol="EUR_USD", side="BUY", notional=20.0) is None


def test_execution_gate_consumes_market_and_fx_without_reorder(tmp_path) -> None:
    gate = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "ab.json"),
        )
    )
    snap = LiveMarketSnapshot.not_available()
    fx = UnavailableFXConversionProvider().get_conversion(
        base_currency="USD", quote_currency="CAD"
    )
    result = gate.evaluate_trade(
        **_gate_kwargs(market_snapshot=snap, fx_conversion=fx)
    )
    assert result["decision"]["final"] == "ALLOW"
    assert result["debug"]["market_snapshot"]["status"] == STATUS_NOT_AVAILABLE
    assert result["debug"]["market_snapshot"]["usable"] is False
    assert result["debug"]["market_snapshot"]["schema_id"] == "LIVE_MARKET_SNAPSHOT"
    assert result["debug"]["market_snapshot"]["schema_version"] == "185A.1"
    assert result["debug"]["market_snapshot"]["provider_name"] == "UNAVAILABLE_PROVIDER"
    assert result["debug"]["market_snapshot"]["provider_version"] == "185A.1"
    assert result["debug"]["fx_conversion"]["status"] == STATUS_NOT_AVAILABLE
    assert result["debug"]["fx_conversion"]["usable"] is False
    assert result["debug"]["fx_conversion"]["schema_id"] == "FX_CONVERSION"
    assert result["debug"]["fx_conversion"]["schema_version"] == "185A.1"
    assert result["debug"]["fx_conversion"]["provider_name"] == "UNAVAILABLE_PROVIDER"
    assert result["debug"]["fx_conversion"]["provider_version"] == "185A.1"
    # AntiBleed still evaluated first (present in debug; margin also present after allow path)
    assert "anti_bleed_guard" in result["debug"]
    assert "margin_trade_gate" in result["debug"]


def test_execution_gate_missing_inputs_still_fail_closed_with_market_debug(tmp_path) -> None:
    gate = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(state_file=str(tmp_path / "ab.json"))
    )
    result = gate.evaluate_trade(
        **_gate_kwargs(
            fee_bps=None,
            market_snapshot=LiveMarketSnapshot.unknown(),
            fx_conversion=FXConversionQuote.unknown(),
        )
    )
    assert result["decision"]["final"] == "BLOCK"
    assert "missing_anti_bleed_input:fee_bps" in result["reason"]
    assert result["debug"]["market_snapshot"]["status"] == STATUS_UNKNOWN
    assert "margin_trade_gate" not in result["debug"]


def test_antibleed_micro_pilot_still_aligns_with_phase152a(tmp_path) -> None:
    cad20 = float(DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_position_cad)
    guard = AntiBleedGuard(policy=MICRO_PILOT, state_file=str(tmp_path / "ab.json"))
    ok = guard.evaluate(
        symbol="EUR_USD",
        trade_size=cad20,
        expected_move_bps=50.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
    )
    assert ok["approved"] is True
    assert cad20 == 20.0


def test_live_authority_anti_bleed_requirement_unchanged() -> None:
    assert any(key == "anti_bleed_guard_pass" for key, _ in AUTHORITY_CONDITIONS)


def test_snapshot_identity_excludes_authority_and_secrets() -> None:
    identity = LiveMarketSnapshot.not_available().identity()
    assert "secret" not in identity
    assert "authority" not in identity
    assert identity["status"] == STATUS_NOT_AVAILABLE
    assert identity["schema_id"] == "LIVE_MARKET_SNAPSHOT"
    assert identity["schema_version"] == "185A.1"
    assert identity["provider_name"] == "UNAVAILABLE_PROVIDER"
