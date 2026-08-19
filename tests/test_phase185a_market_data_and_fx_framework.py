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
)
from backend.app.market.status import FRAMEWORK_VERSION, STATUS_NOT_AVAILABLE, STATUS_UNKNOWN


REPO_ROOT = Path(__file__).resolve().parents[1]
GOV_DOC = REPO_ROOT / "docs" / "governance" / "PHASE_185A_MARKET_DATA_AND_FX_FRAMEWORK.md"


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


def test_snapshot_identity_excludes_authority_and_secrets() -> None:
    identity = LiveMarketSnapshot.not_available().identity()
    assert "secret" not in identity
    assert "authority" not in identity
    assert identity["status"] == STATUS_NOT_AVAILABLE
    assert identity["schema_id"] == "LIVE_MARKET_SNAPSHOT"
    assert identity["schema_version"] == "185A.1"
    assert identity["provider_name"] == "UNAVAILABLE_PROVIDER"
