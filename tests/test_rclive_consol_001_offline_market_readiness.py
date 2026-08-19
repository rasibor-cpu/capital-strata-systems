"""RC-LIVE-CONSOL-001 — isolation, determinism, and fail-closed live-network proofs."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from backend.app.market.oanda_readonly_certification.boundary import verify_execution_boundary
from backend.app.market.provider_interfaces import (
    DEFAULT_FEE_MODEL_PROVIDER,
    DEFAULT_FX_CONVERSION_PROVIDER,
    DEFAULT_MARKET_SNAPSHOT_PROVIDER,
    DEFAULT_SLIPPAGE_PROVIDER,
)
from backend.app.market.providers import (
    FixtureFeeModelProvider,
    FixtureFXConversionProvider,
    FixtureSlippageProvider,
    LiveNetworkMarketAccessError,
    LiveNetworkMarketProvider,
    OandaFixtureMarketProvider,
    OfflineCertificationMicrostructureProvider,
    OfflineCertificationQuoteFacts,
)
from backend.app.market.providers._common import classify_freshness, parse_utc_timestamp
from backend.app.market.status import ADVISORY_ONLY, EXECUTION_ALLOWED, LIVE_NETWORK_INGESTION

REPO = Path(__file__).resolve().parents[1]
MARKET = REPO / "backend" / "app" / "market"
FIX = REPO / "tests" / "fixtures" / "phase186a"
EVAL = "2026-08-01T12:00:05Z"

FORBIDDEN_IMPORT_FRAGMENTS = (
    "backend.app.brokers",
    "backend.app.risk.anti_bleed_guard",
    "backend.app.risk.anti_bleed_policy",
    "backend.app.risk.live_microstructure_provider",
    "backend.app.risk.capital_allocation_governor",
    "backend.governance.css_unified_trade_gate",
    "engine.execution.execution_gate",
    "engine.execution.kill_switch",
    "backend.runtime.live_authorization_ttl",
    "backend.runtime.live_authority_lease",
    "backend.runtime.live_micro_pilot_governor",
    "backend.runtime.live_execution_authority",
    "backend.app.brokers.credential_loader",
    "requests",
    "httpx",
    "aiohttp",
)

FORBIDDEN_CALLS = (
    "place_order",
    "submit_order",
    "cancel_order",
    "modify_order",
    "create_order",
    "arm_live_authority",
    "load_credentials",
    "urlopen",
)

UNTOUCHED_PATHS = (
    "engine/execution/execution_gate.py",
    "backend/app/risk/anti_bleed_guard.py",
    "backend/governance/css_unified_trade_gate.py",
    "backend/runtime/live_authorization_ttl.py",
    "backend/runtime/live_authority_lease.py",
    "backend/runtime/live_micro_pilot_governor.py",
    "backend/app/risk/live_microstructure_provider.py",
)


def _ctx(**extra):
    base = {
        "evaluation_time": EVAL,
        "max_age_seconds": 30,
        "fx_max_age_seconds": 86400,
        "expected_move_bps": 50.0,
        "expected_move_provenance": "offline_fixture:expected_move_v1",
    }
    base.update(extra)
    return base


def test_recovery_posture_is_advisory_offline_only() -> None:
    assert ADVISORY_ONLY is True
    assert EXECUTION_ALLOWED is False
    assert LIVE_NETWORK_INGESTION is False
    assert DEFAULT_MARKET_SNAPSHOT_PROVIDER.get_snapshot(symbol="EUR_USD").status == "NOT_AVAILABLE"
    assert DEFAULT_FX_CONVERSION_PROVIDER.get_conversion(
        base_currency="USD", quote_currency="CAD"
    ).status == "NOT_AVAILABLE"
    assert DEFAULT_FEE_MODEL_PROVIDER.estimate_fee(
        symbol="EUR_USD", notional=20.0, side="BUY"
    ).status == "NOT_AVAILABLE"
    assert DEFAULT_SLIPPAGE_PROVIDER.estimate_slippage(
        symbol="EUR_USD", notional=20.0, side="BUY"
    ).status == "NOT_AVAILABLE"


def test_live_network_provider_fails_closed() -> None:
    with pytest.raises(LiveNetworkMarketAccessError, match="unauthorized"):
        LiveNetworkMarketProvider()


def test_fx_and_fee_and_slippage_are_deterministic() -> None:
    fx = FixtureFXConversionProvider(FIX / "fx_rates_valid.json")
    first = fx.get_conversion(base_currency="USD", quote_currency="CAD", context=_ctx())
    second = fx.get_conversion(base_currency="USD", quote_currency="CAD", context=_ctx())
    assert first.as_dict() == second.as_dict()
    assert first.rate == pytest.approx(1.36)
    fee = FixtureFeeModelProvider(FIX / "fee_model.json").estimate_fee(
        symbol="EUR_USD", notional=20.0, side="BUY", context=_ctx()
    )
    slip = FixtureSlippageProvider(FIX / "slippage_model.json").estimate_slippage(
        symbol="EUR_USD", notional=20.0, side="BUY", context=_ctx()
    )
    assert fee.status == "AVAILABLE"
    assert slip.status == "AVAILABLE"
    assert fee.evidence_hash
    assert slip.evidence_hash


def test_stale_and_fresh_fixture_behavior() -> None:
    fresh = OandaFixtureMarketProvider(FIX / "oanda_eurusd_valid.json").get_snapshot(
        symbol="EUR_USD", context=_ctx()
    )
    stale = OandaFixtureMarketProvider(FIX / "oanda_eurusd_stale.json").get_snapshot(
        symbol="EUR_USD", context=_ctx()
    )
    assert fresh.status == "AVAILABLE"
    assert fresh.freshness == "FRESH"
    assert stale.status == "NOT_AVAILABLE"
    eval_at = parse_utc_timestamp(EVAL)
    quote = parse_utc_timestamp("2026-08-01T12:00:05Z")
    status, _age = classify_freshness(quote_time=quote, evaluation_time=eval_at, max_age_seconds=30)
    assert status == "FRESH"
    future, _age = classify_freshness(
        quote_time=parse_utc_timestamp("2026-08-01T12:01:00Z"),
        evaluation_time=eval_at,
        max_age_seconds=30,
    )
    assert future == "FUTURE"


def test_composite_offline_provider_does_not_grant_execution() -> None:
    composite = OfflineCertificationMicrostructureProvider(
        market_snapshot_provider=OandaFixtureMarketProvider(FIX / "oanda_eurusd_valid.json"),
        fee_model_provider=FixtureFeeModelProvider(FIX / "fee_model.json"),
        slippage_provider=FixtureSlippageProvider(FIX / "slippage_model.json"),
    )
    result = composite.provide_detailed(
        symbol="EUR_USD", side="BUY", notional=20.0, context=_ctx()
    )
    assert result.available is True
    assert result.inputs is not None
    source = inspect.getsource(OfflineCertificationMicrostructureProvider)
    for token in FORBIDDEN_CALLS:
        assert f"{token}(" not in source


def test_market_package_ast_rejects_execution_network_and_gates() -> None:
    violations: list[str] = []
    for path in MARKET.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                names = []
            joined = " ".join(names)
            for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
                if fragment in joined:
                    violations.append(f"{path.name}: import {fragment}")
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                if name in FORBIDDEN_CALLS:
                    violations.append(f"{path.name}: call {name}")
        for token in ("place_order(", "submit_order(", "cancel_order(", "modify_order("):
            if token in source and path.name not in {"boundary.py", "framework.py"}:
                violations.append(f"{path.name}: token {token}")
        if "execution_allowed=True" in source.replace(" ", "") or "EXECUTION_ALLOWED=True" in source.replace(" ", ""):
            violations.append(f"{path.name}: execution_allowed=True")
    assert violations == []


def test_localized_quote_facts_are_not_antibleed() -> None:
    facts = OfflineCertificationQuoteFacts(
        expected_move_bps=50.0,
        fee_bps=0.5,
        spread_bps=1.8,
        slippage_bps=1.0,
    )
    assert facts.ADVISORY_ONLY is True
    assert facts.EXECUTION_ALLOWED is False
    assert facts.IS_ANTIBLEED_CONTROL is False
    assert facts.GRANTS_LIVE_AUTHORITY is False
    assert facts.MAY_SUBMIT_ORDERS is False
    assert facts.MAY_MUTATE_UNIFIED_TRADE_GATE is False
    assert "LiveMicrostructureInputs" not in facts.__class__.__name__
    assert "AntiBleed" not in facts.__class__.__name__
    for method in ("evaluate", "approve", "authorize", "place_order", "submit_order"):
        assert not hasattr(facts, method)
    source = inspect.getsource(OfflineCertificationQuoteFacts)
    assert "anti_bleed_guard" not in source
    assert "execution_gate" not in source


def test_composite_uses_localized_facts_and_fail_closes() -> None:
    composite = OfflineCertificationMicrostructureProvider(
        market_snapshot_provider=OandaFixtureMarketProvider(FIX / "oanda_eurusd_valid.json"),
        fee_model_provider=FixtureFeeModelProvider(FIX / "fee_model.json"),
        slippage_provider=FixtureSlippageProvider(FIX / "slippage_model.json"),
    )
    ok = composite.provide_detailed(
        symbol="EUR_USD", side="BUY", notional=20.0, context=_ctx()
    )
    assert ok.available is True
    assert isinstance(ok.inputs, OfflineCertificationQuoteFacts)
    assert ok.inputs.EXECUTION_ALLOWED is False
    assert ok.inputs.IS_ANTIBLEED_CONTROL is False

    stale = OfflineCertificationMicrostructureProvider(
        market_snapshot_provider=OandaFixtureMarketProvider(FIX / "oanda_eurusd_stale.json"),
        fee_model_provider=FixtureFeeModelProvider(FIX / "fee_model.json"),
        slippage_provider=FixtureSlippageProvider(FIX / "slippage_model.json"),
    ).provide_detailed(symbol="EUR_USD", side="BUY", notional=20.0, context=_ctx())
    assert stale.available is False
    assert stale.inputs is None

    malformed = OandaFixtureMarketProvider(FIX / "oanda_eurusd_malformed.json").get_snapshot(
        symbol="EUR_USD", context=_ctx()
    )
    assert malformed.status == "NOT_AVAILABLE"

    unsupported = OandaFixtureMarketProvider(FIX / "oanda_eurusd_valid.json").get_snapshot(
        symbol="GBP_USD", context=_ctx()
    )
    assert unsupported.status == "NOT_AVAILABLE"

    missing_ts = OandaFixtureMarketProvider(FIX / "oanda_eurusd_missing_timestamp.json").get_snapshot(
        symbol="EUR_USD", context=_ctx()
    )
    assert missing_ts.status == "NOT_AVAILABLE"


def test_package_does_not_import_antibleed_or_execution_controls() -> None:
    forbidden = (
        "backend.app.risk.anti_bleed_guard",
        "backend.app.risk.anti_bleed_policy",
        "backend.app.risk.live_microstructure_provider",
        "engine.execution.execution_gate",
        "backend.governance.css_unified_trade_gate",
        "backend.app.brokers.credential_loader",
    )
    for path in MARKET.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        joined = " ".join(imported)
        for fragment in forbidden:
            assert fragment not in joined, f"{path.name} imports {fragment}"


def test_oanda_readonly_ast_firewall() -> None:
    result = verify_execution_boundary()
    assert result["ok"] is True
    assert result["grants_execution"] is False
    assert result["violations"] == []


def test_forbidden_runtime_files_were_not_modified() -> None:
    import subprocess

    diff = subprocess.check_output(
        ["git", "diff", "--name-only", "origin/css-v1.0.1-maintenance"],
        cwd=str(REPO),
        text=True,
    )
    changed = {line.strip() for line in diff.splitlines() if line.strip()}
    for path in UNTOUCHED_PATHS:
        assert path not in changed, path
    assert "backend/runtime/oanda_live_read_only_adapter.py" not in changed
    assert "backend/app/brokers/oanda_adapter.py" not in changed
