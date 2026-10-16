"""Issue #118: startup modes, risk personalities, mandates, exits and attribution.

Every account is activated through the real consent flow (css118_support.activate).
All evaluations run through the real canonical gates (R7 CSSUnifiedTradeGate,
ExecutionGate with AntiBleedGuard and MarginTradeGate, R14F, TradeQualityScoringEngine,
CAIE) and the paper validation pipeline.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta

import pytest

from css118_support import KEY, NOW, SAFE_FLAGS, SESSION, TRADER, activate, follower, mandate_request, signal, system
from backend.trading_profiles.attribution import AttributionError, reconcile
from backend.trading_profiles.consent import ConsentError
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, CopyTradeEngine
from backend.trading_profiles.exits import CopiedPosition, evaluate_exit, realized_pnl
from backend.trading_profiles.mandates import MandateError, MandateRegistry, ReauthorizationPolicy, evaluate_mandate
from backend.trading_profiles.operating_modes import OperatingMode, permissions_for
from backend.trading_profiles.risk_personalities import LEGACY_ENGINE_MODE_MAPPING, RiskPersonality, policy_for


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


def _engine(tmp_path, key=KEY) -> CopyTradeEngine:
    return CopyTradeEngine(tmp_path / "tp", key_provider=(lambda: key) if key else None)


def _setup(engine, user_id, personality, *, mode=OperatingMode.COPY_CSS_TRADER, limits=None, **mandate_kw):
    if mode is OperatingMode.COPY_CSS_TRADER and "asset_classes" not in mandate_kw:
        mandate_kw["asset_classes"] = sorted(policy_for(personality).allowed_asset_classes)
    mandate = mandate_request(**mandate_kw) if mode is OperatingMode.COPY_CSS_TRADER else None
    receipt = activate(engine.consent, user_id, mode.value, personality.value if personality else None,
                       limits=limits, mandate=mandate)
    active = engine.preferences.get(user_id).active
    return engine.mandates.get(active.mandate_id) if active.mandate_id else receipt


def _uid(p: RiskPersonality) -> str:
    return "follower-" + p.name.lower()


# --------------------------------------------------------------- catalog
def test_exactly_four_modes_and_five_personalities_with_owner_names():
    assert [m.value for m in OperatingMode] == [
        "Simulated Trading", "CSS-Assisted Trading", "Copy a CSS Trader", "CSS Autonomous Trading"]
    assert [p.value for p in RiskPersonality] == ["Safe", "Conservative", "Balanced", "Aggressive", "Ultra Aggressive"]


def test_personalities_are_not_legacy_engine_modes():
    assert LEGACY_ENGINE_MODE_MAPPING == {}
    for legacy in ("EXPANSION", "expansion"):
        with pytest.raises(ValueError):
            RiskPersonality.parse(legacy)
    assert RiskPersonality.parse("Ultra Aggressive") is RiskPersonality.ULTRA_AGGRESSIVE


def test_no_mode_permits_live_orders_or_broker_paths():
    for mode in OperatingMode:
        p = permissions_for(mode)
        assert p.live_broker_orders_permitted is False
        assert p.broker_order_path_reachable is False
        assert p.simulated_fills_only is True
    assert permissions_for(OperatingMode.SIMULATED_TRADING).governed_paper_pipeline is False
    assert permissions_for(OperatingMode.CSS_ASSISTED_TRADING).requires_per_order_approval is True
    assert permissions_for(OperatingMode.COPY_CSS_TRADER).requires_trader_mandate is True
    assert permissions_for(OperatingMode.CSS_AUTONOMOUS_TRADING).requires_per_order_approval is False


def test_personality_limits_are_monotonic_and_within_global_caps():
    policies = [policy_for(p) for p in RiskPersonality]
    for field in ("risk_per_trade_pct", "max_position_pct_of_equity", "max_total_exposure_pct_of_equity",
                  "max_open_copied_positions", "max_stop_distance_pct", "time_stop_hours"):
        values = [getattr(p, field) for p in policies]
        assert values == sorted(values), field
    floors = [p.min_trade_quality_score for p in policies]
    assert floors == sorted(floors, reverse=True)
    assert all(p.max_open_copied_positions <= 10 for p in policies)


def test_account_without_accepted_settings_cannot_trade(tmp_path):
    engine = _engine(tmp_path)
    d = engine.evaluate(signal(), follower("nobody"), system(), now=NOW)
    assert (d.outcome, d.stage, d.reason) == ("REJECTED", "consent", "consent_missing")


# --------------------------------------------------------------- the core claim
def test_same_signal_produces_personality_specific_outcomes(tmp_path):
    engine = _engine(tmp_path)
    results = {}
    for p in RiskPersonality:
        _setup(engine, _uid(p), p)
        results[p] = engine.evaluate(signal(), follower(_uid(p)), system(), now=NOW)

    safe = results[RiskPersonality.SAFE]
    assert (safe.outcome, safe.stage, safe.reason) == ("REJECTED", "trade_quality", "quality_recommendation_not_accepted")
    copied = [results[p] for p in RiskPersonality if p is not RiskPersonality.SAFE]
    assert all(d.outcome == "COPIED" for d in copied)
    assert [d.notional for d in copied] == [400.0, 600.0, 800.0, 1000.0]
    assert [d.stop_distance_pct for d in copied] == [1.5, 2.0, 2.5, 2.5]
    tps = [d.fill["take_profit_price"] for d in copied]
    assert tps == sorted(tps) and len(set(tps)) == 4
    for d in copied:
        assert d.gate_results["css_unified_trade_gate"].startswith("approved")
        assert d.gate_results["execution_gate"] == "approved"
        assert d.pipeline_status == "validated_not_executed"
        assert d.fill["source"] == "SIMULATED_PAPER_FILL"
        assert d.r14f["allowed"] is True


def test_outcomes_are_deterministic_across_independent_runs(tmp_path):
    def run(root):
        engine = CopyTradeEngine(root, key_provider=lambda: KEY)
        out = []
        for p in RiskPersonality:
            _setup(engine, _uid(p), p)
            d = engine.evaluate(signal(), follower(_uid(p)), system(), now=NOW)
            out.append((d.outcome, d.stage, d.reason, d.notional, d.stop_distance_pct, d.quality_score,
                        d.caie_score, None if d.fill is None else d.fill["price"]))
        return out

    assert run(tmp_path / "a") == run(tmp_path / "b")


def test_asset_class_eligibility_differs_by_personality(tmp_path):
    engine = _engine(tmp_path)
    outcomes = {}
    for p in RiskPersonality:  # autonomous mode: no mandate scope in the way, only the personality
        _setup(engine, _uid(p), p, mode=OperatingMode.CSS_AUTONOMOUS_TRADING)
        outcomes[p] = engine.evaluate(signal(signal_id="fut-1", symbol="ES", asset_class="FUTURES",
                                             trader_id=AUTONOMOUS_SOURCE_ID), follower(_uid(p)), system(), now=NOW)
    assert outcomes[RiskPersonality.SAFE].reason == "asset_class_not_allowed"
    assert outcomes[RiskPersonality.CONSERVATIVE].reason == "asset_class_not_allowed"
    for p in (RiskPersonality.BALANCED, RiskPersonality.AGGRESSIVE, RiskPersonality.ULTRA_AGGRESSIVE):
        assert outcomes[p].stage != "personality"


# --------------------------------------------------------------- no bypass of canonical gates
def test_aggressive_personalities_cannot_relax_r7_probability(tmp_path):
    engine = _engine(tmp_path)
    for p in (RiskPersonality.AGGRESSIVE, RiskPersonality.ULTRA_AGGRESSIVE):
        _setup(engine, _uid(p), p)
    sig = signal(probability=0.54)  # Ultra floor .53 < R7 BALANCED .58
    ultra = engine.evaluate(sig, follower(_uid(RiskPersonality.ULTRA_AGGRESSIVE)), system(), now=NOW)
    aggr = engine.evaluate(sig, follower(_uid(RiskPersonality.AGGRESSIVE)), system(), now=NOW)
    assert aggr.reason == "probability_below_personality_floor"
    assert ultra.outcome == "REJECTED" and ultra.stage in {"r14f", "css_unified_trade_gate"} and ultra.fill is None


def test_r7_threshold_follows_legacy_engine_mode_not_personality(tmp_path):
    engine = _engine(tmp_path)
    _setup(engine, "u-ultra", RiskPersonality.ULTRA_AGGRESSIVE)
    sig = signal(probability=0.57, signal_score=20.0)
    blocked = engine.evaluate(sig, follower("u-ultra"), system(engine_mode="BALANCED"), now=NOW)
    assert (blocked.stage, blocked.reason) == ("css_unified_trade_gate", "rejected: probability below threshold")
    allowed = engine.evaluate(replace(sig, signal_id="sig-2", symbol="GBP/USD"), follower("u-ultra"),
                              system(engine_mode="EXPANSION"), now=NOW)
    assert allowed.outcome == "COPIED"


def test_r14f_blocks_every_personality(tmp_path):
    engine = _engine(tmp_path)
    for p in RiskPersonality:
        _setup(engine, _uid(p), p)
    sig = signal(signal_score=10.0)
    for p in RiskPersonality:
        d = engine.evaluate(sig, follower(_uid(p)), system(), now=NOW)
        assert d.outcome == "REJECTED"
        if d.stage not in {"trade_quality", "personality"}:
            assert d.stage == "r14f" and d.r14f["threshold"] == pytest.approx(14.9)


def test_antibleed_minimum_size_is_never_bypassed_by_upsizing(tmp_path):
    engine = _engine(tmp_path)
    _setup(engine, "small", RiskPersonality.CONSERVATIVE)
    d = engine.evaluate(signal(), follower("small", equity=1_000.0, equity_peak=1_000.0, day_start_equity=1_000.0,
                                           buying_power=1_000.0), system(), now=NOW)
    assert d.notional == 40.0
    assert (d.stage, d.reason) == ("execution_gate", "anti_bleed_guard:trade_size_too_small")
    assert d.fill is None


def test_antibleed_net_edge_after_costs_blocks_all_personalities(tmp_path):
    engine = _engine(tmp_path)
    for p in RiskPersonality:
        _setup(engine, _uid(p), p)
    sig = signal(expected_move_bps=30.0, fee_bps=4.0, spread_bps=2.0, slippage_bps=2.0)
    reasons = {engine.evaluate(sig, follower(_uid(p)), system(), now=NOW).reason for p in RiskPersonality
               if p is not RiskPersonality.SAFE}
    assert reasons == {"anti_bleed_guard:insufficient_net_edge"}


def test_antibleed_cooldown_is_per_follower(tmp_path):
    engine = _engine(tmp_path)
    for uid in ("a", "b"):
        _setup(engine, uid, RiskPersonality.BALANCED)
    assert engine.evaluate(signal(), follower("a"), system(), now=NOW).outcome == "COPIED"
    assert engine.evaluate(signal(signal_id="sig-2"), follower("a"), system(), now=NOW).reason == \
        "anti_bleed_guard:cooldown_active"
    assert engine.evaluate(signal(signal_id="sig-2"), follower("b"), system(), now=NOW).outcome == "COPIED"


def _open(uid, asset, symbol, i, notional=100.0, mandate_id=None):
    return CopiedPosition(position_id=f"p{i}", follower_user_id=uid, symbol=symbol, asset_class=asset, side="BUY",
                          notional=notional, entry_price=1.0, stop_distance_pct=1.0, opened_at=NOW, best_price=1.0,
                          mandate_id=mandate_id)


def test_r7_per_asset_cap_applies_to_copied_positions(tmp_path):
    engine = _engine(tmp_path)
    _setup(engine, "capped", RiskPersonality.AGGRESSIVE)
    opened = tuple(_open("capped", "FX", f"X{i}/USD", i) for i in range(3))
    d = engine.evaluate(signal(), follower("capped", open_positions=opened), system(), now=NOW)
    assert (d.stage, d.reason) == ("css_unified_trade_gate", "rejected: position limit reached")


def test_personality_open_position_and_exposure_limits(tmp_path):
    engine = _engine(tmp_path)
    _setup(engine, "cons", RiskPersonality.CONSERVATIVE, asset_classes=["FX", "CRYPTO"])
    three = tuple(_open("cons", "CRYPTO", f"C{i}", i) for i in range(3))
    assert engine.evaluate(signal(), follower("cons", open_positions=three), system(), now=NOW).reason == \
        "personality_open_position_limit"
    full = (_open("cons", "CRYPTO", "BIG", 9, notional=1_000.0),)
    d = engine.evaluate(signal(signal_id="s3"), follower("cons", open_positions=full), system(), now=NOW)
    assert (d.stage, d.reason) == ("sizing", "exposure_limit_reached")


def test_drawdown_and_daily_loss_halts_differ_by_personality(tmp_path):
    engine = _engine(tmp_path)
    for p in RiskPersonality:
        _setup(engine, _uid(p), p, asset_classes=["FX"])
    dd = {p: engine.evaluate(signal(signal_id=f"dd-{p.name}"), follower(_uid(p), equity=9_600.0, day_start_equity=9_600.0),
                             system(), now=NOW).reason for p in RiskPersonality}
    assert dd[RiskPersonality.SAFE] == "drawdown_halt"
    assert dd[RiskPersonality.CONSERVATIVE] != "drawdown_halt"
    daily = {p: engine.evaluate(signal(signal_id=f"dl-{p.name}", symbol="AUD/USD"),
                                follower(_uid(p), equity=9_750.0, equity_peak=9_750.0, day_start_equity=10_000.0),
                                system(), now=NOW).reason for p in RiskPersonality}
    assert daily[RiskPersonality.CONSERVATIVE] == "daily_loss_halt"
    assert daily[RiskPersonality.BALANCED] != "daily_loss_halt"


def test_kill_switches_block_copied_paper_trades(tmp_path):
    engine = _engine(tmp_path)
    _setup(engine, "k", RiskPersonality.BALANCED)
    d = engine.evaluate(signal(), follower("k"), system(mobile_controls={"live_order_kill_switch": True}), now=NOW)
    assert (d.stage, d.reason) == ("safety", "kill_switch:mobile_control_kill_switch_engaged")
    d = engine.evaluate(signal(signal_id="s2"), follower("k"), system(env={"CSS_LIVE_ORDER_KILL_SWITCH": "1"}), now=NOW)
    assert d.reason == "kill_switch:env_kill_switch_engaged"


@pytest.mark.parametrize("flags", [
    None,
    {"verdict": "NOT_OBSERVED", "fail_closed": True},
    {**SAFE_FLAGS, "execution_allowed": True},
    {**SAFE_FLAGS, "live_trading_blocked": False},
    {**SAFE_FLAGS, "verdict": "UNSAFE"},
])
def test_unsafe_or_unobserved_safety_flags_fail_closed(tmp_path, flags):
    engine = _engine(tmp_path)
    _setup(engine, "f", RiskPersonality.BALANCED)
    d = engine.evaluate(signal(), follower("f"), system(safety_flags=flags), now=NOW)
    assert (d.stage, d.reason) == ("safety", "safety_flags_not_safe")


def test_unknown_engine_mode_fails_closed(tmp_path):
    engine = _engine(tmp_path)
    _setup(engine, "f", RiskPersonality.BALANCED)
    assert engine.evaluate(signal(), follower("f"), system(engine_mode="ULTRA"), now=NOW).reason == "engine_mode_unknown"


# --------------------------------------------------------------- mandates
def test_mandate_expiry_revocation_and_supersession(tmp_path):
    engine = _engine(tmp_path)
    first = _setup(engine, "m", RiskPersonality.BALANCED, valid_days=1)
    assert engine.evaluate(signal(), follower("m"), system(), now=NOW + timedelta(days=2)).reason == "mandate_expired"
    second = _setup(engine, "m", RiskPersonality.BALANCED)
    assert engine.mandates.get(first.mandate_id).revoked_at_utc  # superseded by the newly accepted mandate
    assert engine.evaluate(signal(signal_id="t"), follower("m"), system(), now=NOW).outcome == "COPIED"
    engine.mandates.revoke(second.mandate_id, follower_user_id="m", reason="user", now=NOW)
    assert engine.evaluate(signal(signal_id="t2", symbol="USD/JPY"), follower("m"), system(), now=NOW).reason == "mandate_revoked"
    assert engine.mandates.verify_audit_chain() == 4


def test_mandate_trader_and_scope_and_personality_checks(tmp_path):
    engine = _engine(tmp_path)
    mandate = _setup(engine, "m", RiskPersonality.BALANCED, asset_classes=["FX"])
    assert engine.evaluate(signal(trader_id="trader-beta"), follower("m"), system(), now=NOW).reason == "mandate_trader_mismatch"
    crypto = signal(signal_id="c", symbol="BTC-USD", asset_class="CRYPTO")
    assert engine.evaluate(crypto, follower("m"), system(), now=NOW).reason == "mandate_asset_class_out_of_scope"
    decision = evaluate_mandate(mandate, key_provider=lambda: KEY, follower_user_id="m", trader_id=TRADER,
                                personality=RiskPersonality.AGGRESSIVE, asset_class="FX", session_id=SESSION, now=NOW)
    assert decision.reason == "mandate_personality_mismatch"


def test_reauthorization_each_sign_on_and_interval(tmp_path):
    engine = _engine(tmp_path)
    m = _setup(engine, "s", RiskPersonality.BALANCED, reauthorization_policy="EACH_SIGN_ON", reauthorization_interval_hours=0)
    new_session = follower("s", session_id="sess-2")
    assert engine.evaluate(signal(), new_session, system(), now=NOW).reason == "mandate_reauthorization_required_at_sign_on"
    engine.mandates.reauthorize(m.mandate_id, follower_user_id="s", session_id="sess-2", now=NOW)
    assert engine.evaluate(signal(signal_id="s2"), new_session, system(), now=NOW).outcome == "COPIED"
    _setup(engine, "i", RiskPersonality.BALANCED, reauthorization_interval_hours=24)
    assert engine.evaluate(signal(signal_id="s3"), follower("i"), system(), now=NOW + timedelta(hours=25)).reason == \
        "mandate_reauthorization_overdue"


def test_mandate_tampering_and_missing_key_fail_closed(tmp_path):
    engine = _engine(tmp_path)
    m = _setup(engine, "t", RiskPersonality.BALANCED, max_allocation=500.0)
    document = json.loads(engine.mandates.path.read_text())
    document["mandates"][m.mandate_id]["max_allocation"] = 1_000_000.0
    engine.mandates.path.write_text(json.dumps(document))
    d = engine.evaluate(signal(), follower("t"), system(), now=NOW)
    assert (d.stage, d.reason) == ("consent", "active_settings_tampered")

    keyless = MandateRegistry(tmp_path / "nokey", key_provider=None)
    with pytest.raises(MandateError, match="signing_key_unavailable"):
        keyless.authorize(follower_user_id="x", trader_id=TRADER, personality=RiskPersonality.SAFE, asset_classes=("FX",),
                          max_allocation=10, currency="CAD", valid_days=1,
                          reauthorization_policy=ReauthorizationPolicy.EACH_SIGN_ON, reauthorization_interval_hours=0,
                          session_id="s", now=NOW)
    with pytest.raises(ConsentError, match="activation_failed"):
        _setup(engine, "self", RiskPersonality.SAFE, trader_id="self", asset_classes=["FX"])
    assert engine.preferences.get("self").active is None

    audit = engine.mandates.audit_path.read_text().splitlines()
    tampered = json.loads(audit[0])
    tampered["trader_id"] = "someone-else"
    engine.mandates.audit_path.write_text("\n".join([json.dumps(tampered)] + audit[1:]) + "\n")
    with pytest.raises(MandateError, match="chain broken"):
        engine.mandates.verify_audit_chain()


def test_forged_reauthorization_is_caught_by_mandate_signature(tmp_path):
    """Fields outside the consented policy hash (renewal session/time) are protected by the HMAC signature."""
    engine = _engine(tmp_path)
    m = _setup(engine, "f", RiskPersonality.BALANCED, reauthorization_policy="EACH_SIGN_ON", reauthorization_interval_hours=0)
    document = json.loads(engine.mandates.path.read_text())
    document["mandates"][m.mandate_id]["authorized_session_id"] = "sess-attacker"  # forge a renewal for a new session
    engine.mandates.path.write_text(json.dumps(document))
    d = engine.evaluate(signal(), follower("f", session_id="sess-attacker"), system(), now=NOW)
    assert (d.stage, d.reason) == ("authority", "mandate_signature_invalid")


def test_mandate_allocation_caps_copy_size(tmp_path):
    engine = _engine(tmp_path)
    _setup(engine, "cap", RiskPersonality.ULTRA_AGGRESSIVE, max_allocation=500.0)
    d = engine.evaluate(signal(), follower("cap"), system(), now=NOW)
    assert d.outcome == "COPIED" and d.notional == 500.0


# --------------------------------------------------------------- modes
def test_simulated_mode_never_reaches_validation_pipeline(tmp_path, monkeypatch):
    from backend.execution import unified_execution_pipeline

    def _forbidden(self, request):
        raise AssertionError("simulated mode must not use the execution pipeline")

    monkeypatch.setattr(unified_execution_pipeline.UnifiedExecutionPipeline, "execute", _forbidden)
    engine = _engine(tmp_path)
    _setup(engine, "sim", RiskPersonality.BALANCED, mode=OperatingMode.SIMULATED_TRADING)
    d = engine.evaluate(signal(), follower("sim"), system(), now=NOW)
    assert d.outcome == "SIMULATED" and d.pipeline_status == "simulated_not_routed"
    assert d.gate_results["execution_gate"] == "approved"


def test_autonomous_mode_uses_css_engine_signals_within_personality(tmp_path):
    engine = _engine(tmp_path)
    _setup(engine, "auto", RiskPersonality.CONSERVATIVE, mode=OperatingMode.CSS_AUTONOMOUS_TRADING)
    assert engine.evaluate(signal(), follower("auto"), system(), now=NOW).reason == \
        "autonomous_mode_accepts_css_engine_signals_only"
    d = engine.evaluate(signal(signal_id="a1", trader_id=AUTONOMOUS_SOURCE_ID), follower("auto"), system(), now=NOW)
    assert d.outcome == "COPIED" and d.notional == 400.0 and d.mandate_id is None


def test_copy_mode_rejects_autonomous_and_manual_sources(tmp_path):
    engine = _engine(tmp_path)
    _setup(engine, "c", RiskPersonality.BALANCED)
    assert engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID), follower("c"), system(), now=NOW).reason == \
        "copy_mode_requires_trader_signal"
    assert engine.evaluate(signal(signal_id="x", trader_id="USER_MANUAL:c"), follower("c"), system(), now=NOW).reason == \
        "copy_mode_requires_trader_signal"


# --------------------------------------------------------------- exits
def _position(stop_pct: float) -> CopiedPosition:
    return CopiedPosition(position_id="p", follower_user_id="u", symbol="EUR/USD", asset_class="FX", side="BUY",
                          notional=1000.0, entry_price=100.0, stop_distance_pct=stop_pct, opened_at=NOW, best_price=100.0)


def test_exits_differ_by_personality_on_identical_price_path():
    results = {p: evaluate_exit(_position(policy_for(p).max_stop_distance_pct), policy_for(p), mark_price=103.0,
                                now=NOW + timedelta(hours=1)).reason for p in RiskPersonality}
    assert results[RiskPersonality.CONSERVATIVE] == "TAKE_PROFIT"
    assert results[RiskPersonality.ULTRA_AGGRESSIVE] == "within_limits"
    late = {p: evaluate_exit(_position(1.0), policy_for(p), mark_price=100.2, now=NOW + timedelta(hours=30)).reason
            for p in RiskPersonality}
    assert late[RiskPersonality.SAFE] == "TIME_STOP" and late[RiskPersonality.BALANCED] == "within_limits"


def test_stop_trailing_and_source_exit():
    policy = policy_for(RiskPersonality.BALANCED)
    pos = _position(2.0)
    assert evaluate_exit(pos, policy, mark_price=97.9, now=NOW).reason == "STOP_LOSS"
    assert evaluate_exit(replace(pos, best_price=103.0), policy, mark_price=101.5, now=NOW).reason == "TRAILING_STOP"
    assert evaluate_exit(pos, policy, mark_price=100.5, now=NOW, source_exited=True).reason == "SOURCE_TRADER_EXITED"
    assert realized_pnl(pos, 101.0, fee_bps=2.0) == pytest.approx(9.8)


def test_revoked_mandate_blocks_new_trades_but_existing_positions_keep_exit_protection(tmp_path):
    engine = _engine(tmp_path)
    m = _setup(engine, "e", RiskPersonality.BALANCED)
    d = engine.evaluate(signal(), follower("e"), system(), now=NOW)
    position = engine.position_from_decision(d, signal(), opened_at=NOW)
    engine.mandates.revoke(m.mandate_id, follower_user_id="e", reason="user", now=NOW)
    assert engine.evaluate(signal(signal_id="n"), follower("e", open_positions=(position,)), system(), now=NOW).outcome == "REJECTED"
    assert evaluate_exit(position, policy_for(RiskPersonality.BALANCED), mark_price=position.entry_price * 0.97,
                         now=NOW).reason == "STOP_LOSS"


# --------------------------------------------------------------- attribution
def test_attribution_reconciles_and_separates_follower_pnl(tmp_path):
    engine = _engine(tmp_path)
    for p in RiskPersonality:
        _setup(engine, _uid(p), p, asset_classes=["FX"])
    sig = signal()
    positions = []
    for p in RiskPersonality:
        d = engine.evaluate(sig, follower(_uid(p)), system(), now=NOW)
        if d.copied:
            positions.append(engine.position_from_decision(d, sig, opened_at=NOW))
    for pos in positions:
        exit_price = pos.entry_price * 1.01
        engine.record_exit(pos, exit_price=exit_price, reason="TEST_EXIT", pnl=realized_pnl(pos, exit_price, 2.0), now=NOW)
    report = reconcile(engine.ledger.records())
    assert report["ok"], report["discrepancies"]
    assert report["counts"] == {"source_signals": 1, "follower_decisions": 5, "copied": 4, "rejected": 1, "exits": 4}
    statements = [engine.ledger.follower_statement(_uid(p)) for p in RiskPersonality]
    assert len({s["your_realized_pnl"] for s in statements[1:]}) == 4
    assert statements[0]["trades"] == [] and statements[0]["skipped_signals_by_reason"] == {"quality_recommendation_not_accepted": 1}
    assert statements[1]["trades"][0]["trader_signal"]["reference_price"] == 1.08
    assert statements[1]["trades"][0]["your_fill"]["price"] != 1.08


def test_attribution_detects_tampering_and_orphans(tmp_path):
    engine = _engine(tmp_path)
    _setup(engine, "a", RiskPersonality.BALANCED)
    engine.evaluate(signal(), follower("a"), system(), now=NOW)
    engine.record_exit(_open("a", "FX", "EUR/USD", 99), exit_price=1.0, reason="X", pnl=0.0, now=NOW)
    assert "exit_without_copied_position:p99" in reconcile(engine.ledger.records())["discrepancies"]
    lines = engine.ledger.path.read_text().splitlines()
    record = json.loads(lines[1])
    record["notional"] = 999999
    engine.ledger.path.write_text("\n".join([lines[0], json.dumps(record)] + lines[2:]) + "\n")
    with pytest.raises(AttributionError):
        engine.ledger.records()
