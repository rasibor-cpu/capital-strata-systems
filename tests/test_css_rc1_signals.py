"""RC1 signal pipeline: data validation, no look-ahead, conservative labelling, walk-forward without
leakage, release gates, dual-control calibration approval, producer and governed routing.

SYNTHETIC candles are used here only to verify mechanics. They are never evidence of strategy
performance; that evidence must come from tools/css_calibrate.py on real cached market data.
"""
from __future__ import annotations

import json
import math
import random
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from css118_support import ADMIN_A, ADMIN_B, KEY, SESSION, activate, system
from backend.signals.calibration import (
    GateThresholds,
    OOSResult,
    artifact_digest,
    build_artifact,
    evaluate_gates,
    walk_forward,
)
from backend.signals.candles import (
    Candle,
    CandleError,
    CandleSeries,
    CoinbasePublicCandles,
    CsvCandleStore,
    OandaPracticeCandles,
    check_fresh,
    validate,
)
from backend.signals.producer import CalibrationApprovalError, CalibrationApprovals, SignalProducer
from backend.signals.research import (
    DEFAULT_COSTS,
    BarrierParams,
    Candidate,
    CostModel,
    Event,
    compute_features,
    label_events,
    triple_barrier,
)
from backend.trading_profiles.copy_engine import CopyTradeEngine
from backend.trading_profiles.engine_bridge import CssEngineSignalBridge, Provenance
from backend.trading_profiles.router import PaperBook, TradingRouter

H = 3600
T0 = 1_790_000_000 - 1_790_000_000 % H


@pytest.fixture(autouse=True)
def _no_ambient_kill_switch(monkeypatch):
    for name in ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)


def synthetic(seed=11, n=400, drift=0.0008, noise=0.004):
    rnd = random.Random(seed)
    px, out = 100.0, []
    for i in range(n):
        o = px
        px = px * math.exp(drift + rnd.gauss(0, noise))
        hi = max(o, px) * (1 + abs(rnd.gauss(0, noise / 3)))
        lo = min(o, px) * (1 - abs(rnd.gauss(0, noise / 3)))
        out.append(Candle(T0 + i * H, o, hi, lo, px, 1000.0))
    return CandleSeries("BTC-USD", "CRYPTO", H, "synthetic", tuple(out))


# ------------------------------------------------------------------ data validation
@pytest.mark.parametrize("mutate,reason", [
    (lambda cs: cs[:5] + (replace(cs[5], ts=cs[4].ts),) + cs[6:], "not_strictly_increasing"),
    (lambda cs: cs[:5] + (replace(cs[5], ts=cs[5].ts + 7),) + cs[6:], "bar_misaligned"),
    (lambda cs: cs[:5] + (replace(cs[5], high=cs[5].low * 0.5),) + cs[6:], "ohlc_inconsistent"),
    (lambda cs: cs[:5] + (replace(cs[5], close=float("nan")),) + cs[6:], "price_invalid"),
    (lambda cs: cs[:5] + cs[7:], "gap"),
])
def test_validation_rejects_bad_data(mutate, reason):
    s = synthetic(n=60)
    with pytest.raises(CandleError, match=reason):
        validate(replace(s, candles=mutate(s.candles)))


def test_freshness_rejects_stale_and_future_data():
    s = synthetic(n=60)
    close_time = datetime.fromtimestamp(s.candles[-1].ts + H, tz=timezone.utc)
    check_fresh(s, now=close_time + timedelta(minutes=5))
    with pytest.raises(CandleError, match="data_stale"):
        check_fresh(s, now=close_time + timedelta(hours=3))
    with pytest.raises(CandleError, match="data_from_future"):
        check_fresh(s, now=close_time - timedelta(hours=2))


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class _Http:
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def get(self, url, params=None, headers=None, timeout=10.0):
        self.calls.append((url, params, headers))
        return _Resp(self.payload)


def test_coinbase_parsing_newest_first_to_validated_series():
    rows = [[T0 + 2 * H, 99, 102, 100, 101, 5], [T0 + H, 98, 101, 99, 100, 4], [T0, 97, 100, 98, 99, 3]]
    http = _Http(rows)
    s = CoinbasePublicCandles(http).fetch("BTC-USD", granularity_s=H)
    assert [c.ts for c in s.candles] == [T0, T0 + H, T0 + 2 * H] and s.candles[0].open == 98.0
    assert http.calls[0][0].startswith("https://api.exchange.coinbase.com/products/BTC-USD/candles")


def test_oanda_practice_only_complete_bars_and_token_required():
    with pytest.raises(CandleError, match="oanda_non_practice_host_refused"):
        OandaPracticeCandles(_Http({}), token="t", base_url="https://api-fxtrade.oanda.com/v3")
    with pytest.raises(CandleError, match="oanda_practice_token_missing"):
        OandaPracticeCandles(_Http({}), token="").fetch("EUR_USD", granularity_s=H)
    t = datetime.fromtimestamp(T0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    t2 = datetime.fromtimestamp(T0 + H, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    payload = {"candles": [
        {"time": f"{t}.000000000Z", "complete": True, "volume": 10, "mid": {"o": "1.08", "h": "1.09", "l": "1.07", "c": "1.085"}},
        {"time": f"{t2}.000000000Z", "complete": False, "volume": 3, "mid": {"o": "1.085", "h": "1.09", "l": "1.08", "c": "1.088"}},
    ]}
    http = _Http(payload)
    s = OandaPracticeCandles(http, token="synthetic").fetch("EUR_USD", granularity_s=H)
    assert [c.ts for c in s.candles] == [T0] and s.instrument == "EUR/USD"  # forming bar never used
    assert http.calls[0][2]["Authorization"] == "Bearer synthetic"


def test_cache_roundtrip_preserves_digest(tmp_path):
    s = synthetic(n=120)
    store = CsvCandleStore(tmp_path)
    store.save(s)
    assert store.load("synthetic", "BTC-USD", "CRYPTO", H).digest == s.digest


# ------------------------------------------------------------------ research
def test_features_have_no_look_ahead():
    s = synthetic(n=320)
    full = compute_features(s.candles)
    for k in (250, 280, 319):
        partial = compute_features(s.candles[:k + 1])
        assert partial[k] == full[k]


def _cand(side="BUY", atr=1.0):
    f = compute_features(synthetic(n=260).candles)[-1]
    return Candidate("TREND_BREAKOUT", side, 1.0, replace(f, i=0, atr=atr))


def _bars(*rows):
    return [Candle(T0 + k * H, *r, 1.0) for k, r in enumerate(rows)]


def test_triple_barrier_tie_is_a_loss_and_costs_are_subtracted():
    costs = CostModel(fee_bps=10, spread_bps=5, slippage_bps=5)
    p = BarrierParams(stop_atr=1.0, reward_risk=2.0, horizon_bars=3)
    # bar 1 entry at 100; bar 1 touches both 99 (stop) and 102 (target) -> LOSS
    tie = triple_barrier(_bars((100, 100, 100, 100), (100, 102.5, 98.5, 101)), _cand(), p, costs)
    assert tie is None or tie.result == "LOSS"
    win = triple_barrier(_bars((100, 100, 100, 100), (100, 101, 99.5, 100.5), (100.5, 102.5, 100.2, 102),
                               (102, 102, 101, 101)), _cand(), p, costs)
    assert win.result == "WIN" and win.gross_bps == pytest.approx(200.0) and win.net_bps == pytest.approx(200.0 - costs.round_trip_bps)


def test_triple_barrier_with_insufficient_future_is_excluded():
    p = BarrierParams(stop_atr=1.0, reward_risk=2.0, horizon_bars=10)
    assert triple_barrier(_bars((100, 100, 100, 100), (100, 100.5, 99.5, 100)), _cand(), p, DEFAULT_COSTS["FX"]) is None


def _ev(i, score, win, net):
    return Event("TREND_BREAKOUT", "BUY", score, "TRENDING", i, i + 1, net, win)


def test_walk_forward_never_uses_test_outcomes():
    # single fold: train period every trade loses, test period every trade wins -> nothing may be selected;
    # the boundary trade entering at 398 resolves after t=400 and must not enter training either
    events = [_ev(i, 1.0 + (i % 5) * 0.1, False, -50) for i in range(0, 396, 4)]
    events.append(Event("TREND_BREAKOUT", "BUY", 1.2, "TRENDING", 398, 405, 5000.0, True))
    events += [_ev(i, 1.0 + (i % 5) * 0.1, True, +80) for i in range(400, 800, 4)]
    r = walk_forward(events, n_bars=800, train_bars=400, step_bars=400)
    assert r.folds == 1 and r.trades == 0


def test_walk_forward_selects_positive_train_bins_and_reports_oos():
    rnd = random.Random(3)
    events = []
    for i in range(0, 2000, 2):
        score = rnd.random() * 3
        win = rnd.random() < (0.35 + 0.15 * score)  # higher score -> more wins (synthetic)
        events.append(_ev(i, score, win, 120.0 if win else -60.0))
    r = walk_forward(events, n_bars=2000, train_bars=800, step_bars=200)
    assert r.trades > 0 and r.folds == 6 and len(r.per_fold_mean_bps) <= r.folds


def test_folds_without_trades_count_against_positive_fold_fraction():
    # 4 folds evaluated; only the last selects (profitable) trades -> fraction 1/4, not 1/1
    events = [_ev(i, 1.0, False, -50) for i in range(0, 700, 4)]
    events += [_ev(i, 2.0 + (i % 3) * 0.1, True, 80) for i in range(0, 700, 4)]
    events += [_ev(i, 1.0, False, -50) for i in range(700, 1000, 4)]
    r = walk_forward(events, n_bars=1000, train_bars=600, step_bars=100)
    assert r.folds == 4 and r.positive_fold_fraction <= 0.25 + 1e-9


def test_gates_each_check_can_fail():
    good = OOSResult(150, 20.0, 60.0, 4.0, 0.0001, 12.0, 0.20, 0.25, 0.8, 500.0, 6)
    assert evaluate_gates(good, GateThresholds())["passed"] is True
    for change, check in [({"trades": 10}, "min_oos_trades"), ({"lower_bound_net_bps": -1.0}, "lower_bound_net_bps_positive"),
                          ({"brier": 0.3}, "brier_beats_base_rate"), ({"positive_fold_fraction": 0.5}, "positive_fold_fraction"),
                          ({"max_drawdown_bps": 9999.0}, "max_drawdown_bps")]:
        verdict = evaluate_gates(replace(good, **change), GateThresholds())
        assert verdict["passed"] is False and verdict["checks"][check] is False


# ------------------------------------------------------------------ artifacts, approvals, producer
def _artifact(passing=True, positive=True):
    rnd = random.Random(5)
    events = [_ev(i, rnd.random() * 4, (rnd.random() < 0.7) == positive, 150.0 if positive else -40.0)
              for i in range(0, 300)]
    events = [replace(e, net_bps=(150.0 if e.win else -60.0)) for e in events]
    oos = OOSResult(150, 25.0, 60.0, 5.1, 0.00001, 16.0, 0.20, 0.24, 0.83, 400.0, 6) if passing else \
        OOSResult(20, -5.0, 60.0, -0.4, 0.66, -27.0, 0.26, 0.24, 0.33, 900.0, 6)
    return build_artifact(strategy="TREND_BREAKOUT", instrument="BTC-USD", asset_class="CRYPTO", granularity_s=H,
                          events=events, oos=oos, gates=GateThresholds(), data_digests=["synthetic"],
                          barrier={"stop_atr": 1.5, "reward_risk": 2.0, "horizon_bars": 24},
                          costs={"fee_bps": 60.0, "spread_bps": 5.0, "slippage_bps": 5.0}, code_revision="test")


def test_artifact_digest_detects_tampering():
    art = _artifact()
    assert artifact_digest(art) == art["artifact_sha256"]
    tampered = json.loads(json.dumps(art))
    tampered["model"]["expectancy_bps"][0] = 999.0
    assert artifact_digest(tampered) != tampered["artifact_sha256"]


def test_approvals_need_two_distinct_super_users_and_passing_gates(tmp_path):
    ap = CalibrationApprovals(tmp_path)
    art = _artifact()
    with pytest.raises(CalibrationApprovalError, match="super_user_required"):
        ap.approve(art, actor_ctx={"user_id": "t", "role": "TRADER"})
    ap.approve(art, actor_ctx=ADMIN_A)
    ap.approve(art, actor_ctx=ADMIN_A)  # same person twice still counts once
    assert ap.status(art) == (False, "approvals_insufficient:1")
    ap.approve(art, actor_ctx=ADMIN_B)
    assert ap.status(art) == (True, "approved_dual_control")
    ap.revoke(art, actor_ctx=ADMIN_A)
    assert ap.status(art) == (False, "revoked")
    with pytest.raises(CalibrationApprovalError, match="gates_not_passed"):
        ap.approve(_artifact(passing=False), actor_ctx=ADMIN_A)


def test_approved_artifact_becomes_unroutable_if_edited(tmp_path):
    ap = CalibrationApprovals(tmp_path)
    art = _artifact()
    ap.approve(art, actor_ctx=ADMIN_A)
    ap.approve(art, actor_ctx=ADMIN_B)
    edited = json.loads(json.dumps(art))
    edited["score_map"]["per_bps"] = 10.0
    assert ap.status(edited) == (False, "artifact_digest_mismatch")


class _Provider:
    """Stub of a LIVE feed for mechanics tests. The bars are synthetic; the explicit LIVE label is
    what a real provider would attach. Unlabelled synthetic bars are refused (test below)."""
    source = "synthetic"

    def __init__(self, series, classification="LIVE"):
        self.series = series
        self.classification = classification

    def fetch(self, instrument, *, granularity_s, end=None):
        return replace(self.series, classification=self.classification)


def _now_for(series):
    return datetime.fromtimestamp(series.candles[-1].ts + H + 60, tz=timezone.utc)


@pytest.fixture()
def world(tmp_path):
    engine = CopyTradeEngine(tmp_path / "tp", key_provider=lambda: KEY)
    sess = (SESSION, time.time())
    router = TradingRouter(engine, book=PaperBook(engine.root), role_resolver=lambda u: "TRADER",
                           session_resolver=lambda u: sess, system_provider=lambda: system())
    activate(engine.consent, "auto-1", "CSS Autonomous Trading", "Balanced")
    approvals = CalibrationApprovals(engine.root)
    return router, approvals


def test_producer_refuses_unapproved_calibration(world):
    router, approvals = world
    s = synthetic()
    (p,) = SignalProducer(_Provider(s), approvals, [_artifact()], DEFAULT_COSTS).produce("BTC-USD", granularity_s=H, now=_now_for(s))
    assert p.signal is None and p.reason == "calibration_not_routable:approvals_insufficient:0"


def test_producer_refuses_stale_data(world):
    router, approvals = world
    s = synthetic()
    (p,) = SignalProducer(_Provider(s), approvals, [_artifact()], DEFAULT_COSTS).produce(
        "BTC-USD", granularity_s=H, now=_now_for(s) + timedelta(hours=5))
    assert p.signal is None and p.reason.startswith("market_data_unavailable:data_stale")


def test_producer_emits_calibrated_signal_and_bridge_routes_it(world):
    router, approvals = world
    art = _artifact()
    approvals.approve(art, actor_ctx=ADMIN_A)
    approvals.approve(art, actor_ctx=ADMIN_B)
    s = synthetic()
    (p,) = SignalProducer(_Provider(s), approvals, [art], DEFAULT_COSTS).produce("BTC-USD", granularity_s=H, now=_now_for(s))
    assert p.reason == "ok" and p.signal.side == "BUY" and p.signal.trader_id == "CSS_AUTONOMOUS_ENGINE"
    cost = DEFAULT_COSTS["CRYPTO"]
    prob, ev = p.signal.probability, p.signal.expected_move_bps - cost.round_trip_bps
    assert 0 < prob < 1 and ev > 0 and p.signal.fee_bps == 2 * cost.fee_bps
    assert p.signal.reference_price == s.candles[-1].close
    result = CssEngineSignalBridge(router).publish_real_data(p, art, approvals, now=_now_for(s))
    (d,) = result.decisions
    assert result.accepted and d.follower_user_id == "auto-1"
    assert d.stage not in {"routing", "consent", "authority"}  # reached the trading gates


def test_bridge_refuses_real_data_signal_when_approval_missing_or_mismatched(world):
    router, approvals = world
    art = _artifact()
    approvals.approve(art, actor_ctx=ADMIN_A)
    approvals.approve(art, actor_ctx=ADMIN_B)
    s = synthetic()
    (p,) = SignalProducer(_Provider(s), approvals, [art], DEFAULT_COSTS).produce("BTC-USD", granularity_s=H, now=_now_for(s))
    bridge = CssEngineSignalBridge(router)
    approvals.revoke(art, actor_ctx=ADMIN_A)
    assert bridge.publish_real_data(p, art, approvals).reason == "calibration_not_routable:revoked"
    other = _artifact(positive=False)
    assert bridge.publish_real_data(p, other, approvals).reason == "signal_artifact_mismatch"
    generic = bridge.publish(p.signal, Provenance.REAL_DATA_CALIBRATED)
    assert generic.accepted is False and "provenance_not_approved" in generic.reason
    assert router.book.positions() == []


def test_label_events_one_trade_per_strategy_at_a_time():
    events = label_events(synthetic(seed=3, n=900).candles, BarrierParams(), DEFAULT_COSTS["FX"])
    for strat in {e.strategy for e in events}:
        evs = sorted((e for e in events if e.strategy == strat), key=lambda e: e.entry_index)
        assert all(b.entry_index > a.exit_index for a, b in zip(evs, evs[1:]))


def test_shadow_runner_journals_heartbeats_and_decisions(world, tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("shadow", Path(__file__).resolve().parents[1] / "tools" / "css_signal_shadow.py")
    shadow = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shadow)
    router, approvals = world
    art = _artifact()
    approvals.approve(art, actor_ctx=ADMIN_A)
    approvals.approve(art, actor_ctx=ADMIN_B)
    s = synthetic()
    t = {"now": s.candles[-1].ts + H + 60.0}
    summary = shadow.run(router=router, bridge=CssEngineSignalBridge(router),
                         producer=SignalProducer(_Provider(s), approvals, [art], DEFAULT_COSTS), approvals=approvals,
                         artifacts=[art], instruments=["BTC-USD"], granularity_s=H, hours=1.0,
                         journal=tmp_path / "j.jsonl", poll_s=0, clock=lambda: t["now"],
                         sleep=lambda _s: t.__setitem__("now", t["now"] + 1), max_cycles=3)
    lines = [json.loads(x) for x in (tmp_path / "j.jsonl").read_text().splitlines()]
    assert [r["type"] for r in lines].count("HEARTBEAT") == 3 and lines[-1]["type"] == "SUMMARY"
    assert summary["signals"] == 3 and summary["routed"] == 3


def test_producer_never_acts_on_synthetic_or_replay_data(world):
    router, approvals = world
    art = _artifact()
    approvals.approve(art, actor_ctx=ADMIN_A)
    approvals.approve(art, actor_ctx=ADMIN_B)
    s = synthetic()
    for label in ("SYNTHETIC", "REPLAY", "UNCLASSIFIED", "DELAYED", "INDICATIVE"):
        (p,) = SignalProducer(_Provider(s, label), approvals, [art], DEFAULT_COSTS).produce(
            "BTC-USD", granularity_s=H, now=_now_for(s))
        assert p.signal is None and p.reason == f"data_classification_not_permitted:{label}"
    with pytest.raises(ValueError, match="never_permitted"):
        SignalProducer(_Provider(s), approvals, [art], DEFAULT_COSTS, allowed_classifications=frozenset({"REPLAY"}))


# ------------------------------------------------------------------ closeout: market quality and provenance
class _Quotes:
    def __init__(self, bid, ask, depth=1e6, error=None):
        self.bid, self.ask, self.depth, self.error = bid, ask, depth, error

    def quote(self, instrument):
        from backend.signals.market_data import QuoteSnapshot
        if self.error:
            raise CandleError(self.error)
        return QuoteSnapshot(instrument, "stub", self.bid, self.ask, datetime.now(timezone.utc), self.depth, self.depth)


def _approved(approvals, **kw):
    art = _artifact()
    if kw:
        body = {k: v for k, v in {**art, **kw}.items() if k != "artifact_sha256"}
        from backend.signals.calibration import artifact_digest
        art = {**body, "artifact_sha256": artifact_digest(body)}
    approvals.approve(art, actor_ctx=ADMIN_A)
    approvals.approve(art, actor_ctx=ADMIN_B)
    return art


def test_producer_records_data_provenance_on_every_decision(world):
    router, approvals = world
    art = _approved(approvals)
    s = synthetic()
    (p,) = SignalProducer(_Provider(s), approvals, [art], DEFAULT_COSTS).produce("BTC-USD", granularity_s=H, now=_now_for(s))
    assert p.reason == "ok" and p.data_source == "synthetic" and p.data_classification == "LIVE"
    assert p.data_digest == s.digest and p.last_bar_ts == s.candles[-1].ts


def test_producer_refuses_wide_spread_thin_book_or_missing_quote(world):
    router, approvals = world
    art = _approved(approvals)
    s = synthetic()
    now = _now_for(s)
    px = s.candles[-1].close
    wide = SignalProducer(_Provider(s), approvals, [art], DEFAULT_COSTS, quote_provider=_Quotes(px, px * 1.002))
    (p,) = wide.produce("BTC-USD", granularity_s=H, now=now)  # 20 bps > 2 x 5 bps model
    assert p.signal is None and p.reason.startswith("market_quality:spread_exceeds_cost_model:")
    thin = SignalProducer(_Provider(s), approvals, [art], DEFAULT_COSTS, quote_provider=_Quotes(px, px * 1.0001, depth=50),
                          min_depth_notional=10_000)
    (p,) = thin.produce("BTC-USD", granularity_s=H, now=now)
    assert p.signal is None and p.reason.startswith("market_quality:depth_insufficient")
    dead = SignalProducer(_Provider(s), approvals, [art], DEFAULT_COSTS, quote_provider=_Quotes(0, 0, error="quote_stale"))
    (p,) = dead.produce("BTC-USD", granularity_s=H, now=now)
    assert p.signal is None and p.reason == "market_quality:quote_unavailable:quote_stale"
    tight = SignalProducer(_Provider(s), approvals, [art], DEFAULT_COSTS, quote_provider=_Quotes(px, px * 1.0004))
    (p,) = tight.produce("BTC-USD", granularity_s=H, now=now)
    assert p.reason == "ok" and p.observed_spread_bps == pytest.approx(4.0, rel=1e-2)


def test_producer_refuses_bars_from_a_venue_other_than_the_calibrated_one(world):
    router, approvals = world
    art = _approved(approvals, data_source="coinbase_exchange_public")
    s = synthetic()
    (p,) = SignalProducer(_Provider(s), approvals, [art], DEFAULT_COSTS).produce("BTC-USD", granularity_s=H, now=_now_for(s))
    assert p.signal is None and p.reason == "data_source_mismatch:synthetic!=coinbase_exchange_public"


def test_producer_refuses_zero_volume_and_forming_bar(world):
    router, approvals = world
    art = _approved(approvals)
    s = synthetic()
    dead = replace(s, candles=s.candles[:-1] + (replace(s.candles[-1], volume=0.0),))
    (p,) = SignalProducer(_Provider(dead), approvals, [art], DEFAULT_COSTS).produce("BTC-USD", granularity_s=H,
                                                                                    now=_now_for(s))
    assert p.reason == "market_quality:last_bar_no_volume"
    # A provider that leaks the forming bar: the producer drops it and decides on the last closed bar.
    forming_now = datetime.fromtimestamp(s.candles[-1].ts + 600, tz=timezone.utc)
    (p,) = SignalProducer(_Provider(s), approvals, [art], DEFAULT_COSTS).produce("BTC-USD", granularity_s=H,
                                                                                 now=forming_now)
    assert p.last_bar_ts in (None, s.candles[-2].ts)
