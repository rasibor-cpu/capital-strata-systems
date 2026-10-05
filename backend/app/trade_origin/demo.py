"""Synthetic, clearly labelled sample data for the results view. Not real trades, not real results."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .lifecycle import TradeLifecycle
from .model import InMemoryRecommendationRegistry, OrderIntent, OriginLedger, TradeCard, classify_order


def demo_lifecycle() -> tuple[TradeLifecycle, dict]:
    t0 = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    reg, ledger = InMemoryRecommendationRegistry(), OriginLedger()
    lc = TradeLifecycle(ledger)
    end = t0 + timedelta(hours=2)
    cards = [TradeCard("REC-DEMO-1", "SAMPLEA", "BUY", 10, "LIMIT", t0, end, limit_price=100.0, entry_low=99.5,
                       entry_high=100.5, max_slippage_bps=30, stop_price=96.0, target_price=110.0, trade_card_id="CARD-DEMO-1"),
             TradeCard("REC-DEMO-2", "SAMPLEB", "BUY", 20, "LIMIT", t0, end, limit_price=50.0, entry_low=49.8,
                       entry_high=50.2, max_slippage_bps=30, stop_price=48.0, target_price=56.0, trade_card_id="CARD-DEMO-2"),
             TradeCard("REC-DEMO-3", "SAMPLEC", "BUY", 5, "LIMIT", t0, end, limit_price=200.0, entry_low=199.0,
                       entry_high=201.0, max_slippage_bps=30, stop_price=192.0, target_price=220.0, trade_card_id="CARD-DEMO-3")]
    for c in cards:
        reg.add(c)
    act = t0 + timedelta(minutes=5)
    a, b, c = cards
    orders = [
        OrderIntent("O-1", "demo", "SAMPLEA", "BUY", 10, "LIMIT", act, 100.0, 96.0, 110.0, 1.0, a.recommendation_id, 1, a.fingerprint, True),
        OrderIntent("O-2", "demo", "SAMPLEB", "BUY", 12, "LIMIT", act, 50.0, 48.0, 56.0, 1.0, b.recommendation_id, 1, b.fingerprint, True),  # smaller: still CSS
        OrderIntent("O-3", "demo", "SAMPLEC", "BUY", 8, "LIMIT", act, 200.0, None, 220.0, 1.0, c.recommendation_id, 1, c.fingerprint, True),  # larger, no stop: modified
        OrderIntent("O-4", "demo", "SAMPLED", "BUY", 15, "MARKET", act),
        OrderIntent("O-5", "demo", "SAMPLEE", "SELL", 30, "MARKET", act),
    ]
    for o in orders:
        ledger.record(classify_order(o, reg, act))
    for i, (oid, sym, side, q, px) in enumerate([("O-1", "SAMPLEA", "BUY", 10, 100.0), ("O-2", "SAMPLEB", "BUY", 12, 50.0),
                                                 ("O-3", "SAMPLEC", "BUY", 8, 200.0), ("O-4", "SAMPLED", "BUY", 15, 40.0),
                                                 ("O-5", "SAMPLEE", "SELL", 30, 25.0)]):
        lc.apply_open_fill(oid, f"F-{i}", sym, side, q, px, act)
    later = act + timedelta(days=1)
    for o in ("C-1", "C-2", "C-3", "C-4"):
        ledger.record(classify_order(OrderIntent(o, "demo", "X", "SELL", 1, "MARKET", later), reg, later))
    lc.apply_close_fill("C-1", "F-10", 10, 108.0, later, lot_id="O-1")
    lc.apply_close_fill("C-2", "F-11", 6, 48.5, later, lot_id="O-2")
    lc.apply_close_fill("C-3", "F-12", 8, 207.0, later, lot_id="O-3")
    lc.apply_close_fill("C-4", "F-13", 15, 37.0, later, lot_id="O-4")
    return lc, {"SAMPLEB": 51.0, "SAMPLEE": 24.0}
