"""Closeout: all four operating modes x all five risk personalities through the canonical router.

Each cell routes the same CSS engine signal (and, for Copy mode, the same signed trader signal)
through consent, personality, user limits, R14F, R7, ExecutionGate/AntiBleed and the paper book.
Synthetic signal values; this verifies routing semantics, not profitability.
"""
from __future__ import annotations

import time
from dataclasses import asdict

import pytest

from css118_support import (
    KEY,
    NOW,
    SESSION,
    TRADER,
    activate,
    approve_trader,
    mandate_request,
    signal,
    system,
    trader_key,
)
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, CopyTradeEngine
from backend.trading_profiles.operating_modes import OperatingMode
from backend.trading_profiles.risk_personalities import RiskPersonality
from backend.trading_profiles.router import PaperBook, TradingRouter
from backend.trading_profiles.signal_feed import sign_signal

EXPECTED_ACCEPT = {  # outcome when every gate passes, per mode
    OperatingMode.SIMULATED_TRADING: "SIMULATED",
    OperatingMode.CSS_ASSISTED_TRADING: "PROPOSED",          # user must approve each order
    OperatingMode.COPY_CSS_TRADER: "COPIED",                 # only from the mandated trader
    OperatingMode.CSS_AUTONOMOUS_TRADING: "COPIED",
}


@pytest.fixture(autouse=True)
def _no_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


def _router(tmp_path, mode, personality):
    root = tmp_path / f"{mode.name}-{personality.name}"
    engine = CopyTradeEngine(root, key_provider=lambda: KEY)
    router = TradingRouter(engine, book=PaperBook(root), role_resolver=lambda u: "TRADER",
                           session_resolver=lambda u: (SESSION, time.time()), system_provider=lambda: system())
    kw = {}
    if mode is OperatingMode.COPY_CSS_TRADER:
        approve_trader(engine.trader_registry, TRADER)
        kw["mandate"] = mandate_request(trader_id=TRADER, asset_classes=["FX"])
    activate(engine.consent, "u1", mode.value, personality.value, **kw)
    return router


def _trader_envelope():
    payload = {**asdict(signal()), "issued_at_utc": NOW.isoformat()}
    return sign_signal(trader_key(payload["trader_id"]), payload)


def _route(router, mode):
    css = router.on_css_engine_signal(signal(trader_id=AUTONOMOUS_SOURCE_ID), now=NOW).decisions
    if mode is OperatingMode.COPY_CSS_TRADER:
        assert css == ()  # a Copy-mode user never receives CSS's own signals
        return router.on_trader_signal(_trader_envelope(), now=NOW).decisions
    return css


@pytest.mark.parametrize("mode", list(OperatingMode), ids=lambda m: m.name)
def test_every_mode_and_personality_routes_through_the_governed_chain(tmp_path, mode):
    notionals = {}
    for personality in RiskPersonality:
        router = _router(tmp_path, mode, personality)
        (d,) = _route(router, mode)
        assert d.follower_user_id == "u1"
        if personality is RiskPersonality.SAFE:
            # Safe refuses this marginal-quality signal outright (strictest quality bar).
            assert (d.outcome, d.stage) == ("REJECTED", "trade_quality")
        else:
            assert d.outcome == EXPECTED_ACCEPT[mode], (personality, d.reason)
        notionals[personality] = d.notional
        opened = router.book.positions("u1")
        if d.outcome in {"COPIED", "SIMULATED"}:
            assert len(opened) == 1 and opened[0].notional == d.notional
        else:
            assert opened == []  # proposals and rejections never open positions
    # Sizing never decreases as risk appetite rises; capital governors cap the top end (B7).
    order = list(RiskPersonality)
    assert all(notionals[a] <= notionals[b] for a, b in zip(order, order[1:])), notionals
    assert notionals[RiskPersonality.CONSERVATIVE] < notionals[RiskPersonality.BALANCED]
