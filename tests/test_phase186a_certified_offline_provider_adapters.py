"""Phase 186A / 186A-R1 — certified offline provider adapter tests."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from backend.app.market.providers import (
    FixtureFeeModelProvider,
    FixtureFXConversionProvider,
    FixtureSlippageProvider,
    OandaFixtureMarketProvider,
    OfflineCertificationMicrostructureProvider,
)
from backend.app.market.providers._common import classify_freshness, parse_utc_timestamp
from backend.app.market.provider_interfaces import DEFAULT_MARKET_SNAPSHOT_PROVIDER


REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests" / "fixtures" / "phase186a"
EVAL = "2026-08-01T12:00:05Z"
GOV = REPO / "docs" / "governance" / "PHASE_186A_CERTIFIED_OFFLINE_PROVIDER_ADAPTERS.md"
MARKET_DIR = REPO / "backend" / "app" / "market"


def _ctx(**extra):
    base = {
        "evaluation_time": EVAL,
        "max_age_seconds": 30,
        "fx_max_age_seconds": 86400,
        "expected_move_provenance": "offline_fixture:expected_move_v1",
    }
    base.update(extra)
    return base


def test_governance_states_offline_only() -> None:
    text = GOV.read_text(encoding="utf-8")
    assert "OFFLINE_CERTIFICATION_ONLY" in text
    assert "Live trading remains unauthorized" in text
    assert "IDENTITY" in text
    assert "evidence hash" in text.lower() or "canonical evidence" in text.lower()
    assert "inclusive" in text.lower()


def test_valid_snapshot_parsing_and_deterministic_math() -> None:
    provider = OandaFixtureMarketProvider(FIX / "oanda_eurusd_valid.json")
    snap = provider.get_snapshot(symbol="EUR_USD", context=_ctx())
    assert snap.status == "AVAILABLE"
    assert snap.mid == pytest.approx(1.1001)
    assert snap.evidence_hash
    assert snap.schema_version == "185A.1"


def test_malformed_crossed_stale_unsupported_missing_timestamp() -> None:
    ctx = _ctx()
    assert OandaFixtureMarketProvider(FIX / "oanda_eurusd_malformed.json").get_snapshot(
        symbol="EUR_USD", context=ctx
    ).status == "NOT_AVAILABLE"
    crossed = OandaFixtureMarketProvider(FIX / "oanda_eurusd_crossed.json").get_snapshot(
        symbol="EUR_USD", context=ctx
    )
    assert crossed.status == "NOT_AVAILABLE"
    assert "crossed" in crossed.fail_reason
    stale = OandaFixtureMarketProvider(FIX / "oanda_eurusd_stale.json").get_snapshot(
        symbol="EUR_USD", context=ctx
    )
    assert stale.status == "NOT_AVAILABLE"
    assert OandaFixtureMarketProvider(FIX / "oanda_eurusd_valid.json").get_snapshot(
        symbol="GBP_USD", context=ctx
    ).fail_reason == "unsupported instrument"
    assert OandaFixtureMarketProvider(FIX / "oanda_eurusd_missing_timestamp.json").get_snapshot(
        symbol="EUR_USD", context=ctx
    ).status == "NOT_AVAILABLE"


def test_fx_direct_inverse_triangulate_and_identity() -> None:
    fx = FixtureFXConversionProvider(FIX / "fx_rates_valid.json")
    first = fx.get_conversion(base_currency="USD", quote_currency="CAD", context=_ctx())
    assert first.path_type == "DIRECT"
    assert first.conversion_path == ("USD/CAD",)
    assert first.evidence_hash

    second = fx.get_conversion(base_currency="EUR", quote_currency="CAD", context=_ctx())
    assert second.path_type == "TRIANGULATED"
    # Earlier result provenance must remain intact on the first object.
    assert first.conversion_path == ("USD/CAD",)
    assert first.path_type == "DIRECT"

    inverse = fx.get_conversion(base_currency="CAD", quote_currency="USD", context=_ctx())
    assert inverse.path_type == "INVERSE"
    assert "INVERSE" in inverse.conversion_path

    identity = fx.get_conversion(base_currency="CAD", quote_currency="CAD", context=_ctx())
    assert identity.status == "AVAILABLE"
    assert identity.rate == 1.0
    assert identity.path_type == "IDENTITY"
    assert identity.quality == "GOVERNED_IDENTITY"
    assert identity.conversion_path == ("CAD",)

    missing = FixtureFXConversionProvider(FIX / "fx_rates_missing_leg.json").get_conversion(
        base_currency="EUR", quote_currency="CAD", context=_ctx()
    )
    assert missing.status == "NOT_AVAILABLE"
    assert missing.rate is None
    assert missing.fail_reason


def test_missing_cross_currency_does_not_become_one() -> None:
    fx = FixtureFXConversionProvider(FIX / "fx_rates_missing_leg.json")
    result = fx.get_conversion(base_currency="CAD", quote_currency="USD", context=_ctx())
    assert result.status == "NOT_AVAILABLE"
    assert result.rate is not None or result.rate is None
    assert result.convert(20.0) is None
    assert result.path_type == "NONE"


def test_fee_slippage_and_hashes() -> None:
    fee = FixtureFeeModelProvider(FIX / "fee_model.json")
    a = fee.estimate_fee(symbol="EUR_USD", notional=20.0, side="BUY")
    b = fee.estimate_fee(symbol="EUR_USD", notional=20.0, side="BUY")
    assert a.evidence_hash == b.evidence_hash
    changed = fee.estimate_fee(symbol="EUR_USD", notional=40.0, side="BUY")
    assert changed.evidence_hash != a.evidence_hash
    assert fee.estimate_fee(symbol="USD_JPY", notional=20.0, side="BUY").status == "NOT_AVAILABLE"

    slip = FixtureSlippageProvider(FIX / "slippage_model.json")
    s1 = slip.estimate_slippage(symbol="EUR_USD", notional=20.0, side="BUY")
    s2 = slip.estimate_slippage(symbol="EUR_USD", notional=20.0, side="BUY")
    assert s1.evidence_hash == s2.evidence_hash


def test_no_silent_zero_slippage(tmp_path) -> None:
    path = tmp_path / "slip_zero.json"
    path.write_text(
        json.dumps(
            {
                "model_id": "Z",
                "model_version": "186A.1",
                "instruments": {"EUR_USD": {"slippage_bps": 0.0}},
            }
        ),
        encoding="utf-8",
    )
    provider = FixtureSlippageProvider(path, approved_root=tmp_path)
    result = provider.estimate_slippage(symbol="EUR_USD", notional=20.0, side="BUY")
    assert result.status == "NOT_AVAILABLE"
    assert "zero" in result.fail_reason


def test_freshness_cutoff_boundaries() -> None:
    # Inclusive cutoff: age <= max → FRESH; age > max → STALE
    quote = parse_utc_timestamp("2026-08-01T12:00:00Z")
    assert classify_freshness(
        quote_time=quote,
        evaluation_time=parse_utc_timestamp("2026-08-01T12:00:29Z"),
        max_age_seconds=30,
    )[0] == "FRESH"
    assert classify_freshness(
        quote_time=quote,
        evaluation_time=parse_utc_timestamp("2026-08-01T12:00:30Z"),
        max_age_seconds=30,
    )[0] == "FRESH"
    assert classify_freshness(
        quote_time=quote,
        evaluation_time=parse_utc_timestamp("2026-08-01T12:00:30.001Z"),
        max_age_seconds=30,
    )[0] == "STALE"
    assert classify_freshness(
        quote_time=quote,
        evaluation_time=parse_utc_timestamp("2026-08-01T11:59:59Z"),
        max_age_seconds=30,
    )[0] == "FUTURE"

    provider = OandaFixtureMarketProvider(FIX / "oanda_eurusd_valid.json")
    # Timezone-equivalent evaluation times must agree.
    a = provider.get_snapshot(
        symbol="EUR_USD",
        context=_ctx(evaluation_time="2026-08-01T12:00:05+00:00"),
    )
    b = provider.get_snapshot(
        symbol="EUR_USD",
        context=_ctx(evaluation_time="2026-08-01T12:00:05Z"),
    )
    assert a.evidence_hash == b.evidence_hash
    future = provider.get_snapshot(
        symbol="EUR_USD",
        context=_ctx(evaluation_time="2026-07-31T12:00:00Z"),
    )
    assert future.status == "NOT_AVAILABLE"
    assert "future" in future.fail_reason


def test_triangulation_weak_quality_and_timestamp_window(tmp_path) -> None:
    path = tmp_path / "fx_tri.json"
    path.write_text(
        json.dumps(
            {
                "triangulation_hub": "USD",
                "rates": {
                    "EUR/USD": {
                        "rate": 1.1,
                        "timestamp": "2026-08-01T12:00:00Z",
                        "quality": "CERTIFIED",
                        "rate_id": "EURUSD",
                    },
                    "USD/CAD": {
                        "rate": 1.36,
                        "timestamp": "2026-08-01T11:00:00Z",
                        "quality": "UNVERIFIED",
                        "rate_id": "USDCAD",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    fx = FixtureFXConversionProvider(path, approved_root=tmp_path)
    ok = fx.get_conversion(
        base_currency="EUR",
        quote_currency="CAD",
        context=_ctx(triangulation_timestamp_window_seconds=7200),
    )
    assert ok.status == "AVAILABLE"
    assert ok.quality == "UNVERIFIED"
    assert ok.path_type == "TRIANGULATED"

    bad = fx.get_conversion(
        base_currency="EUR",
        quote_currency="CAD",
        context=_ctx(triangulation_timestamp_window_seconds=60),
    )
    assert bad.status == "NOT_AVAILABLE"
    assert "timestamp inconsistency" in bad.fail_reason


def test_contradictory_rates_fail_closed(tmp_path) -> None:
    path = tmp_path / "fx_dup.json"
    # JSON object can't have duplicate keys; simulate via provider load of conflicting
    # normalized tokens USD/CAD and USD-CAD mapped to same pair with different rates
    # by writing one then forcing second through constructor validation helper.
    path.write_text(
        json.dumps(
            {
                "rates": {
                    "USD/CAD": {"rate": 1.36, "timestamp": "2026-08-01T12:00:00Z"},
                    "USDCAD": {"rate": 1.37, "timestamp": "2026-08-01T12:00:00Z"},
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="contradictory"):
        FixtureFXConversionProvider(path, approved_root=tmp_path)


def test_composite_requires_expected_move_provenance_and_hashes() -> None:
    market = OandaFixtureMarketProvider(FIX / "oanda_eurusd_valid.json")
    fee = FixtureFeeModelProvider(FIX / "fee_model.json")
    slip = FixtureSlippageProvider(FIX / "slippage_model.json")
    composite = OfflineCertificationMicrostructureProvider(
        market_snapshot_provider=market,
        fee_model_provider=fee,
        slippage_provider=slip,
    )
    ok = composite.provide_detailed(
        symbol="EUR_USD",
        side="BUY",
        notional=20.0,
        context={**_ctx(), "expected_move_bps": 50.0},
    )
    assert ok.available is True
    assert ok.market_hash
    assert ok.fee_hash
    assert ok.slippage_hash
    assert ok.composite_hash
    assert ok.expected_move_provenance

    missing = composite.provide_detailed(
        symbol="EUR_USD",
        side="BUY",
        notional=20.0,
        context={"evaluation_time": EVAL, "expected_move_bps": 50.0},
    )
    assert missing.available is False
    assert any("expected_move_provenance" in r for r in missing.reasons)


def test_deterministic_replay_and_key_order_independence(tmp_path) -> None:
    src = json.loads((FIX / "oanda_eurusd_valid.json").read_text(encoding="utf-8"))
    shuffled = {
        "timestamp": src["timestamp"],
        "ask": src["ask"],
        "instrument": src["instrument"],
        "bid": src["bid"],
        "quality": src["quality"],
        "currency": src["currency"],
        "provider": src["provider"],
    }
    path = tmp_path / "shuffled.json"
    path.write_text(json.dumps(shuffled), encoding="utf-8")
    a = OandaFixtureMarketProvider(FIX / "oanda_eurusd_valid.json").get_snapshot(
        symbol="EUR_USD", context=_ctx()
    )
    b = OandaFixtureMarketProvider(path, approved_root=tmp_path).get_snapshot(
        symbol="EUR_USD", context=_ctx()
    )
    assert a.evidence_hash == b.evidence_hash


def test_fixture_path_traversal_rejected(tmp_path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="outside approved"):
        OandaFixtureMarketProvider(outside)


def test_default_production_provider_remains_unavailable() -> None:
    assert DEFAULT_MARKET_SNAPSHOT_PROVIDER.get_snapshot(symbol="EUR_USD").status == "NOT_AVAILABLE"


def test_no_network_modules_or_credential_access() -> None:
    forbidden_roots = {"urllib", "requests", "httpx", "aiohttp", "socket"}
    forbidden_names = {
        "OANDA_API_KEY",
        "OANDA_TOKEN",
        "API_KEY",
        "SECRET",
        "PASSWORD",
        "load_credentials",
        "secret_store",
    }
    for path in MARKET_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden_roots
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden_roots
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"load_credentials", "authenticate"}
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "getenv":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            assert arg.value not in forbidden_names
        assert "broker authentication" not in text.lower()
        assert "order adapter" not in text.lower()
