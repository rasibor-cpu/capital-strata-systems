"""Issue #118 P2: CAD 40 aggregate and two-concurrent-parent pilot envelope (CAD 20 per parent kept).

Unit tests of the envelope plus engine integration through the real canonical gates.
The canonical live caps (order_limit_config: CAD 20 total, 1 position) are asserted unchanged.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from css118_support import NOW, activate, follower, signal, system
from backend.config.order_limit_config import CanonicalOrderLimitConfig
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, CopyTradeEngine
from backend.trading_profiles.exits import CopiedPosition
from backend.trading_profiles.pilot_envelope import (
    APPROVED_MAX_CONCURRENT_PARENTS,
    APPROVED_MAX_PARENT_CAD,
    APPROVED_MAX_TOTAL_CAD,
    PilotEnvelopeConfig,
    PilotParentExposure,
    evaluate_pilot_envelope,
    remaining_parent_budget,
)

D = Decimal


def _p(pid, committed, pending="0.00"):
    return PilotParentExposure(pid, D(committed), D(pending))


# ------------------------------------------------------------------ envelope unit tests
def test_approved_ceilings_are_cad20_parent_cad40_aggregate_two_parents():
    assert (APPROVED_MAX_PARENT_CAD, APPROVED_MAX_TOTAL_CAD, APPROVED_MAX_CONCURRENT_PARENTS) == (D("20.00"), D("40.00"), 2)


def test_existing_live_canonical_caps_are_unchanged():
    cfg = CanonicalOrderLimitConfig()
    assert (cfg.live_pilot_max_total_cad, cfg.live_pilot_max_position_cad, cfg.live_pilot_max_concurrent_positions) == (
        D("20.00"), D("20.00"), 1)


def test_first_parent_up_to_cad20_including_fees():
    ok = evaluate_pilot_envelope([], parent_id="p1", proposed_child_cad="19.90", estimated_fees_cad="0.10")
    assert ok.approved and ok.projected_parent_cad == D("20.00")
    over = evaluate_pilot_envelope([], parent_id="p1", proposed_child_cad="19.91", estimated_fees_cad="0.10")
    assert (over.approved, over.reason) == (False, "PILOT_PARENT_EXPOSURE_CEILING")


def test_scale_in_to_same_parent_cannot_exceed_cad20():
    d = evaluate_pilot_envelope([_p("p1", "15.00", "4.00")], parent_id="p1", proposed_child_cad="1.01")
    assert (d.approved, d.reason) == (False, "PILOT_PARENT_EXPOSURE_CEILING")
    assert evaluate_pilot_envelope([_p("p1", "15.00", "4.00")], parent_id="p1", proposed_child_cad="1.00").approved


def test_second_parent_allowed_to_cad40_aggregate():
    d = evaluate_pilot_envelope([_p("p1", "20.00")], parent_id="p2", proposed_child_cad="20.00")
    assert d.approved and (d.projected_total_cad, d.projected_parent_count) == (D("40.00"), 2)


def test_third_parent_rejected_even_with_budget_left():
    d = evaluate_pilot_envelope([_p("p1", "5.00"), _p("p2", "5.00")], parent_id="p3", proposed_child_cad="1.00")
    assert (d.approved, d.reason) == (False, "PILOT_CONCURRENT_PARENT_CEILING")


def test_aggregate_ceiling_with_tightened_config():
    cfg = PilotEnvelopeConfig(max_total_cad=D("30.00"))
    d = evaluate_pilot_envelope([_p("p1", "20.00")], parent_id="p2", proposed_child_cad="10.01", config=cfg)
    assert (d.approved, d.reason) == (False, "PILOT_AGGREGATE_EXPOSURE_CEILING")


def test_non_cad_currency_rejected():
    assert evaluate_pilot_envelope([], parent_id="p1", proposed_child_cad="5.00", currency="USD").reason == "PILOT_CURRENCY_NOT_CAD"


@pytest.mark.parametrize("cfg", [
    PilotEnvelopeConfig(max_parent_cad=D("20.01")),
    PilotEnvelopeConfig(max_total_cad=D("40.01")),
    PilotEnvelopeConfig(max_concurrent_parents=3),
    PilotEnvelopeConfig(max_parent_cad=D("0.00")),
    PilotEnvelopeConfig(max_concurrent_parents=True),
])
def test_configuration_can_tighten_but_never_raise(cfg):
    with pytest.raises(ValueError):
        cfg.validate()
    d = evaluate_pilot_envelope([], parent_id="p1", proposed_child_cad="1.00", config=cfg)
    assert (d.approved, d.reason) == (False, "PILOT_ENVELOPE_EVALUATION_ERROR")


@pytest.mark.parametrize("parents,kwargs", [
    ([_p("p1", "1.00"), _p("p1", "1.00")], {}),                      # duplicate parent
    ([_p("p1", "25.00")], {}),                                        # already over the parent ceiling
    ([], {"proposed_child_cad": "1.001"}),                            # fractional cent
    ([], {"proposed_child_cad": "-1.00"}),
    ([], {"proposed_child_cad": "NaN"}),
    ([], {"proposed_child_cad": True}),
    ([], {"estimated_fees_cad": "abc"}),
    ([object()], {}),                                                 # malformed state
])
def test_malformed_inputs_fail_closed(parents, kwargs):
    args = {"parent_id": "p9", "proposed_child_cad": "1.00", **kwargs}
    d = evaluate_pilot_envelope(parents, **args)
    assert (d.approved, d.reason) == (False, "PILOT_ENVELOPE_EVALUATION_ERROR")


def test_remaining_budget():
    assert remaining_parent_budget([]) == D("20.00")
    assert remaining_parent_budget([_p("p1", "20.00")]) == D("20.00")
    assert remaining_parent_budget([_p("p1", "20.00"), _p("p2", "1.00")]) == D("0.00")
    assert remaining_parent_budget([_p("p1", "15.00")], config=PilotEnvelopeConfig(max_total_cad=D("30.00"))) == D("15.00")


# ------------------------------------------------------------------ engine integration
@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


def _engine(tmp_path, user="pilot-user"):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=None)
    activate(engine.consent, user, "CSS Autonomous Trading", "Balanced")
    return engine


def _pos(pid, notional, symbol="GBP/USD"):
    return CopiedPosition(pid, "pilot-user", symbol, "FX", "BUY", notional, 1.25, 2.0, NOW - timedelta(minutes=5), 1.25)


def _pilot(**kw):
    return follower("pilot-user", pilot_envelope=True, **kw)


def test_engine_caps_pilot_order_to_cad20_parent_including_fee(tmp_path):
    engine = _engine(tmp_path)
    d = engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID), _pilot(), system(), now=NOW)
    # Sized to CAD 19.99 + CAD 0.01 estimated fee (2 bps, rounded up) = CAD 20.00, then the
    # canonical chain runs: AntiBleedGuard's minimum size (50) still rejects it. Nothing is relaxed.
    assert d.notional == 19.99 and d.outcome == "REJECTED"
    assert (d.stage, d.reason) == ("execution_gate", "anti_bleed_guard:trade_size_too_small")


def test_engine_second_parent_uses_remaining_aggregate(tmp_path):
    engine = _engine(tmp_path)
    d = engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID), _pilot(open_positions=(_pos("p1", 20.0),)), system(), now=NOW)
    assert d.notional == 19.99 and d.reason == "anti_bleed_guard:trade_size_too_small"  # envelope passed; AntiBleed governs


def test_engine_third_parent_rejected_by_envelope(tmp_path):
    engine = _engine(tmp_path)
    opened = (_pos("p1", 5.0), _pos("p2", 5.0, "AUD/USD"))
    d = engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID), _pilot(open_positions=opened), system(), now=NOW)
    assert (d.outcome, d.stage, d.reason) == ("REJECTED", "pilot_envelope", "PILOT_CONCURRENT_PARENT_CEILING")


def test_engine_aggregate_exhausted_rejected_by_envelope(tmp_path):
    engine = _engine(tmp_path)
    cfg_free = (_pos("p1", 20.0),)
    assert engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID, signal_id="s-a"), _pilot(open_positions=cfg_free),
                           system(), now=NOW).stage != "pilot_envelope"
    full = (_pos("p1", 20.0), _pos("p2", 20.0, "AUD/USD"))
    d = engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID, signal_id="s-b"), _pilot(open_positions=full), system(), now=NOW)
    assert (d.stage, d.reason) == ("pilot_envelope", "PILOT_CONCURRENT_PARENT_CEILING")


def test_engine_non_cad_pilot_account_rejected(tmp_path):
    engine = _engine(tmp_path)
    d = engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID), _pilot(account_currency="USD"), system(), now=NOW)
    assert (d.stage, d.reason) == ("pilot_envelope", "PILOT_CURRENCY_NOT_CAD")


def test_engine_without_pilot_flag_is_unchanged(tmp_path):
    engine = _engine(tmp_path)
    d = engine.evaluate(signal(trader_id=AUTONOMOUS_SOURCE_ID), follower("pilot-user"), system(), now=NOW)
    assert d.outcome == "COPIED" and d.notional == 500.0  # capital governor 5% of 10,000 paper equity
