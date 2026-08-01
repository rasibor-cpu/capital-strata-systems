"""Phase 184A — AntiBleed Policy Framework offline certification tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from backend.app.risk.anti_bleed_guard import AntiBleedGuard, AntiBleedGuardConfigurationError
from backend.app.risk.anti_bleed_policy import (
    ANTIBLEED_POLICY_FRAMEWORK_VERSION,
    BACKTEST,
    MICRO_PILOT,
    PAPER,
    POLICY_PROFILES,
    STANDARD,
    AntiBleedPolicy,
    AntiBleedPolicyError,
    AntiBleedPolicyResolver,
)
from backend.app.risk.live_microstructure_provider import (
    DEFAULT_LIVE_MICROSTRUCTURE_PROVIDER,
    LiveMicrostructureInputs,
    UnavailableLiveMicrostructureProvider,
)
from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG
from backend.runtime.live_execution_authority import AUTHORITY_CONDITIONS, evaluate_live_execution_authority
from backend.runtime.live_micro_pilot_governor import LiveMicroPilotGovernor
from engine.execution.execution_gate import ExecutionGate
from engine.risk.margin_snapshot import MarginSnapshot, MarginState


REPO_ROOT = Path(__file__).resolve().parents[1]
GOV_DOC = REPO_ROOT / "docs" / "governance" / "PHASE_184A_ANTIBLEED_POLICY_FRAMEWORK.md"


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


def test_phase184a_governance_document_exists() -> None:
    text = GOV_DOC.read_text(encoding="utf-8")
    assert "AntiBleed Policy Framework" in text
    assert "Does not authorize live trading" in text
    assert "MICRO_PILOT" in text
    assert "Phase 152A" in text
    assert "anti_bleed_guard_pass" in text


def test_policy_resolver_selection_rules() -> None:
    assert AntiBleedPolicyResolver.resolve("LIVE_MICRO_PILOT") is MICRO_PILOT
    assert AntiBleedPolicyResolver.resolve("MICRO_PILOT") is MICRO_PILOT
    assert AntiBleedPolicyResolver.resolve("PAPER") is PAPER
    assert AntiBleedPolicyResolver.resolve("BACKTEST") is BACKTEST
    assert AntiBleedPolicyResolver.resolve(None) is STANDARD
    assert AntiBleedPolicyResolver.resolve("UNKNOWN") is STANDARD
    assert AntiBleedPolicyResolver.resolve({"governed_execution_context": "PAPER"}) is PAPER
    assert AntiBleedPolicyResolver.resolve({"broker": "OANDA", "account_size": 1_000_000}) is STANDARD


def test_policy_immutability() -> None:
    for name, policy in POLICY_PROFILES.items():
        assert policy.name == name
        assert policy.policy_id == name
        assert policy.policy_version == ANTIBLEED_POLICY_FRAMEWORK_VERSION
        with pytest.raises(FrozenInstanceError):
            policy.minimum_profitable_trade_size = 1.0  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            policy.policy_version = "MUTATED"  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            policy.policy_id = "MUTATED"  # type: ignore[misc]


def test_policy_version_exists_on_all_profiles() -> None:
    assert ANTIBLEED_POLICY_FRAMEWORK_VERSION == "184A.1"
    for name, policy in POLICY_PROFILES.items():
        assert policy.policy_id == name
        assert policy.policy_version == "184A.1"
        identity = policy.identity()
        assert identity == {
            "policy_id": name,
            "policy_version": "184A.1",
            "name": name,
        }
        assert "secret" not in identity
        assert "authority" not in identity


def test_resolver_preserves_policy_version() -> None:
    resolved = AntiBleedPolicyResolver.resolve("LIVE_MICRO_PILOT")
    assert resolved is MICRO_PILOT
    assert resolved.policy_id == "MICRO_PILOT"
    assert resolved.policy_version == "184A.1"
    paper = AntiBleedPolicyResolver.resolve("PAPER")
    assert paper.policy_id == "PAPER"
    assert paper.policy_version == "184A.1"
    standard = AntiBleedPolicyResolver.resolve(None)
    assert standard.policy_id == "STANDARD"
    assert standard.policy_version == "184A.1"


def test_standard_profile_thresholds() -> None:
    assert STANDARD.minimum_profitable_trade_size == 50.0
    assert STANDARD.minimum_required_net_edge_bps == 25.0
    assert STANDARD.cooldown_minutes == 10
    assert STANDARD.maximum_symbol_frequency == 1
    assert STANDARD.require_complete_microstructure_inputs is True
    assert STANDARD.allow_dev_override is False


def test_paper_and_backtest_profiles_do_not_weaken_edge() -> None:
    for policy in (PAPER, BACKTEST):
        assert policy.minimum_required_net_edge_bps == 25.0
        assert policy.minimum_profitable_trade_size == 50.0
        assert policy.require_complete_microstructure_inputs is True
        assert policy.allow_dev_override is False


def test_micro_pilot_profile_aligns_with_phase152a_ceiling() -> None:
    cad20 = float(DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_position_cad)
    assert MICRO_PILOT.minimum_profitable_trade_size == cad20
    assert MICRO_PILOT.minimum_required_net_edge_bps == 25.0
    assert MICRO_PILOT.allow_dev_override is False
    assert MICRO_PILOT.require_complete_microstructure_inputs is True


def test_default_guard_still_uses_standard_min_size() -> None:
    guard = AntiBleedGuard()
    assert guard.policy is STANDARD or guard.policy.name.startswith("STANDARD")
    assert guard.minimum_profitable_trade_size == 50.0
    rejected = guard.evaluate(
        symbol="EUR_USD",
        trade_size=20.0,
        expected_move_bps=50.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
    )
    assert rejected["approved"] is False
    assert rejected["reason"] == "trade_size_too_small"


def test_micro_pilot_allows_cad20_with_edge_intact(tmp_path) -> None:
    guard = AntiBleedGuard(policy=MICRO_PILOT, state_file=str(tmp_path / "ab.json"))
    approved = guard.evaluate(
        symbol="EUR_USD",
        trade_size=20.0,
        expected_move_bps=50.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
        side="BUY",
    )
    assert approved["approved"] is True
    assert approved["anti_bleed_policy"] == "MICRO_PILOT"

    bleed = guard.evaluate(
        symbol="GBP_USD",
        trade_size=20.0,
        expected_move_bps=5.0,
        fee_bps=2.0,
        spread_bps=2.0,
        slippage_bps=2.0,
        side="BUY",
    )
    assert bleed["approved"] is False
    assert bleed["reason"] == "expected_move_below_cost"


def test_reject_reasons_unchanged(tmp_path) -> None:
    guard = AntiBleedGuard(
        policy=STANDARD,
        cooldown_minutes=0,
        state_file=str(tmp_path / "ab.json"),
    )
    assert guard.evaluate(
        symbol="EUR_USD",
        trade_size=100.0,
        expected_move_bps=5.0,
        fee_bps=2.0,
        spread_bps=2.0,
        slippage_bps=2.0,
    )["reason"] == "expected_move_below_cost"
    assert guard.evaluate(
        symbol="EUR_USD",
        trade_size=100.0,
        expected_move_bps=20.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
    )["reason"] == "insufficient_net_edge"
    assert guard.evaluate(
        symbol="EUR_USD",
        trade_size=10.0,
        expected_move_bps=80.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
    )["reason"] == "trade_size_too_small"


def test_execution_gate_resolves_policy_before_evaluation(tmp_path) -> None:
    gate = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "ab.json"),
        )
    )
    blocked = gate.evaluate_trade(**_gate_kwargs(notional=20.0, anti_bleed_context=None))
    assert blocked["decision"]["final"] == "BLOCK"
    assert blocked["reason"] == "anti_bleed_guard:trade_size_too_small"
    assert blocked["debug"]["anti_bleed_policy"] == "STANDARD"
    assert blocked["debug"]["policy_id"] == "STANDARD"
    assert blocked["debug"]["policy_version"] == "184A.1"

    allowed = gate.evaluate_trade(
        **_gate_kwargs(notional=20.0, anti_bleed_context="LIVE_MICRO_PILOT")
    )
    assert allowed["decision"]["final"] == "ALLOW"
    assert allowed["debug"]["anti_bleed_policy"] == "MICRO_PILOT"
    assert allowed["debug"]["policy_id"] == "MICRO_PILOT"
    assert allowed["debug"]["policy_version"] == "184A.1"
    assert allowed["debug"]["anti_bleed_guard"]["policy_id"] == "MICRO_PILOT"
    assert allowed["debug"]["anti_bleed_guard"]["policy_version"] == "184A.1"


def test_execution_gate_ordering_anti_bleed_still_first(tmp_path) -> None:
    gate = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "ab.json"),
        )
    )
    result = gate.evaluate_trade(**_gate_kwargs(expected_move_bps=None))
    assert result["decision"]["final"] == "BLOCK"
    assert result["reason"].startswith("anti_bleed_guard:missing_anti_bleed_input")
    assert "margin_trade_gate" not in result["debug"]
    assert "riskgov_path" not in result["debug"]


def test_fail_closed_missing_inputs_unchanged(tmp_path) -> None:
    gate = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(state_file=str(tmp_path / "ab.json"))
    )
    for context in (None, "PAPER", "LIVE_MICRO_PILOT", "BACKTEST"):
        result = gate.evaluate_trade(
            **_gate_kwargs(fee_bps=None, anti_bleed_context=context)
        )
        assert result["decision"]["final"] == "BLOCK"
        assert "missing_anti_bleed_input:fee_bps" in result["reason"]


def test_unavailable_live_microstructure_provider_returns_none() -> None:
    provider = UnavailableLiveMicrostructureProvider()
    assert provider.provide(symbol="EUR_USD", side="BUY", notional=20.0) is None
    assert DEFAULT_LIVE_MICROSTRUCTURE_PROVIDER.provide(
        symbol="EUR_USD", side="BUY", notional=20.0
    ) is None


def test_phase152a_governor_unchanged_and_compatible(tmp_path) -> None:
    config_path = tmp_path / "pilot_config.json"
    state_path = tmp_path / "pilot_state.json"
    audit_path = tmp_path / "pilot_audit.jsonl"
    governor = LiveMicroPilotGovernor(
        config_path=config_path,
        state_path=state_path,
        audit_path=audit_path,
    )
    status = governor.status()
    assert float(DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_position_cad) == 20.0
    assert float(status["max_position_size"]) == 20.0

    decision = governor.evaluate_order(
        {
            "broker": "OANDA",
            "broker_mode": "live",
            "symbol": "EUR_USD",
            "side": "BUY",
            "notional": 20.0,
        }
    )
    assert decision.approved is False

    guard = AntiBleedGuard(policy=MICRO_PILOT, state_file=str(tmp_path / "ab.json"))
    size_ok = guard.evaluate(
        symbol="EUR_USD",
        trade_size=20.0,
        expected_move_bps=50.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
    )
    assert size_ok["approved"] is True
    assert MICRO_PILOT.minimum_profitable_trade_size == float(
        DEFAULT_ORDER_LIMIT_CONFIG.live_pilot_max_position_cad
    )


def test_live_authority_still_requires_anti_bleed_pass() -> None:
    assert any(key == "anti_bleed_guard_pass" for key, _ in AUTHORITY_CONDITIONS)
    authority = evaluate_live_execution_authority(
        {
            "operator_requested_live": True,
            "go_no_go": "NO GO",
            "anti_bleed_guard": "PASS",
        }
    )
    assert authority.can_live_execute is False
    assert "anti_bleed_guard_pass" in authority.condition_status
    # Missing other conditions still fail; AntiBleed requirement remains listed.
    failed_without_ab = evaluate_live_execution_authority(
        {
            "operator_requested_live": True,
            "go_no_go": "GO",
            "anti_bleed_guard": "FAIL",
        }
    )
    assert failed_without_ab.condition_status["anti_bleed_guard_pass"] is False


def test_dev_override_still_blocked_in_production(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CSS_ENV", "production")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(AntiBleedGuardConfigurationError):
        AntiBleedGuard(dev_force_allow=True, state_file=str(tmp_path / "ab.json"))


def test_invalid_policy_construction_fails_closed() -> None:
    with pytest.raises(AntiBleedPolicyError):
        AntiBleedPolicy(
            name="BAD",
            policy_id="BAD",
            policy_version="184A.1",
            minimum_profitable_trade_size=0.0,
            minimum_required_net_edge_bps=25.0,
            cooldown_minutes=10,
            maximum_symbol_frequency=1,
            require_complete_microstructure_inputs=True,
            allow_dev_override=False,
        )


def test_live_microstructure_inputs_dataclass_is_frozen() -> None:
    inputs = LiveMicrostructureInputs(
        expected_move_bps=50.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
    )
    with pytest.raises(FrozenInstanceError):
        inputs.fee_bps = 0.0  # type: ignore[misc]


def test_rc001_regression_standard_path_still_allows_sized_paper(tmp_path) -> None:
    gate = ExecutionGate(
        anti_bleed_guard=AntiBleedGuard(
            cooldown_minutes=0,
            state_file=str(tmp_path / "ab.json"),
        )
    )
    result = gate.evaluate_trade(**_gate_kwargs(anti_bleed_context="PAPER"))
    assert result["decision"]["final"] == "ALLOW"
    assert result["debug"]["anti_bleed_policy"] == "PAPER"
    assert result["debug"]["policy_id"] == "PAPER"
    assert result["debug"]["policy_version"] == "184A.1"
