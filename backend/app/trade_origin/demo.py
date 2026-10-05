"""Synthetic, clearly labelled sample data for the performance view. Not real trades, not real results."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .lifecycle import TradeLifecycle
from .model import InMemoryRecommendationRegistry, OrderIntent, OriginLedger, TradeCard, classify_order


def demo_lifecycle() -> tuple[TradeLifecycle, dict]:
    t0 = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    reg, ledger = InMemoryRecommendationRegistry(), OriginLedger()
    lc = TradeLifecycle(ledger)
    card_a = TradeCard("REC-DEMO-1", "SAMPLEA", "BUY", 10, "LIMIT", t0, t0 + timedelta(hours=2), limit_price=100.0,
                       stop_price=96.0, target_price=110.0, trade_card_id="CARD-DEMO-1")
    card_b = TradeCard("REC-DEMO-2", "SAMPLEB", "BUY", 20, "LIMIT", t0, t0 + timedelta(hours=2), limit_price=50.0,
                       stop_price=48.0, target_price=56.0, trade_card_id="CARD-DEMO-2")
    card_c = TradeCard("REC-DEMO-3", "SAMPLEC", "BUY", 5, "LIMIT", t0, t0 + timedelta(hours=2), limit_price=200.0,
                       stop_price=192.0, target_price=220.0, trade_card_id="CARD-DEMO-3")
    for c in (card_a, card_b, card_c):
        reg.add(c)
    act = t0 + timedelta(minutes=5)
    orders = [
        OrderIntent("O-1", "SAMPLEA", "BUY", 10, "LIMIT", act, 100.0, 96.0, 110.0, "REC-DEMO-1", card_a.fingerprint, True),
        OrderIntent("O-2", "SAMPLEB", "BUY", 20, "LIMIT", act, 50.0, 48.0, 56.0, "REC-DEMO-2", card_b.fingerprint, True),
        OrderIntent("O-3", "SAMPLEC", "BUY", 8, "LIMIT", act, 200.0, None, 220.0, "REC-DEMO-3", card_c.fingerprint, True),
        OrderIntent("O-4", "SAMPLED", "BUY", 15, "MARKET", act),
        OrderIntent("O-5", "SAMPLEE", "SELL", 30, "MARKET", act),
    ]
    for o in orders:
        ledger.record(classify_order(o, reg, act))
    fills = [("O-1", "SAMPLEA", "BUY", 10, 100.0), ("O-2", "SAMPLEB", "BUY", 20, 50.0),
             ("O-3", "SAMPLEC", "BUY", 8, 200.0), ("O-4", "SAMPLED", "BUY", 15, 40.0),
             ("O-5", "SAMPLEE", "SELL", 30, 25.0)]
    for i, (oid, sym, side, q, px) in enumerate(fills):
        lc.apply_open_fill(oid, f"F-{i}", sym, side, q, px, act)
    later = act + timedelta(days=1)
    for o in ("C-1", "C-2", "C-3", "C-4"):
        ledger.record(classify_order(OrderIntent(o, "X", "SELL", 1, "MARKET", later), reg, later))
    lc.apply_close_fill("C-1", "F-10", 10, 108.0, later, lot_id="O-1")          # CSS recommended, win
    lc.apply_close_fill("C-2", "F-11", 10, 48.5, later, lot_id="O-2")           # CSS recommended, partial close at a loss
    lc.apply_close_fill("C-3", "F-12", 8, 207.0, later, lot_id="O-3")           # CSS recommended (modified), win
    lc.apply_close_fill("C-4", "F-13", 15, 37.0, later, lot_id="O-4")           # user trade, loss
    marks = {"SAMPLEB": 51.0, "SAMPLEE": 24.0}
    return lc, marks
