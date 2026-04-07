from __future__ import annotations

import sys
import time
from pathlib import Path
from datetime import datetime, UTC
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.scanner.options_chain_adapter import OptionsChainAdapter
from backend.execution.position_manager import PositionManager
from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.market_regime_engine import MarketRegimeEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer


# =========================
# CONFIG
# =========================
CYCLE_SLEEP = 5

MIN_AI_SCORE = 0.32
MAX_SPREAD_BPS = 35

MIN_LONG_DEV = -0.003
MIN_SHORT_DEV = 0.003

MAX_OPEN_POSITIONS = 6

# NEW — CAPITAL BASE
ACCOUNT_EQUITY = 10000  # simulate $10k account
RISK_PER_TRADE = 0.01   # 1% risk per trade


# =========================
# INIT
# =========================
scanner = UnifiedMarketScanner()
options_adapter = OptionsChainAdapter()
position_manager = PositionManager()

feature_builder = FeatureBuilder()
regime_engine = MarketRegimeEngine()
pressure_engine = OpportunityPressureEngine()
acceleration_engine = PressureAccelerationEngine()
confluence_engine = SignalConfluenceEngine()
ai_scorer = AIOpportunityScorer()


def _safe_float(v, d=0.0):
    try:
        return float(v)
    except:
        return d


def _call(obj, names, rows):
    for n in names:
        fn = getattr(obj, n, None)
        if callable(fn):
            try:
                out = fn(rows)
                if isinstance(out, list):
                    return out
            except:
                return rows
    return rows


def compute_vwap(row):
    candles = row.get("candles")
    if not candles:
        return 0.0

    pv, vol = 0.0, 0.0

    for c in candles[-20:]:
        try:
            price = float(c.get("close", 0))
            v = float(c.get("volume", 1))
        except:
            continue

        pv += price * v
        vol += v

    return pv / vol if vol else 0.0


def enrich(rows):
    rows = _call(feature_builder, ["enrich_rows"], rows)
    rows = _call(regime_engine, ["enrich_rows", "process_rows"], rows)
    rows = _call(pressure_engine, ["enrich_rows"], rows)
    rows = _call(acceleration_engine, ["enrich_rows"], rows)
    rows = _call(confluence_engine, ["enrich_rows"], rows)

    out = []

    for r in rows:
        r = dict(r)

        if "price" not in r:
            r["price"] = _safe_float(r.get("close", 0))

        r["ai_score"] = _safe_float(ai_scorer.score(r))
        r["tradable"] = r.get("tradable", True)

        out.append(r)

    return out


# =========================
# REAL POSITION SIZING
# =========================
def compute_position_size(price, sl):

    risk_amount = ACCOUNT_EQUITY * RISK_PER_TRADE

    stop_distance = abs(price - sl)

    if stop_distance <= 0:
        return 0

    size = risk_amount / stop_distance

    return size


# =========================
# MAIN LOOP
# =========================
def run():

    cycle = 0

    while True:
        cycle += 1

        print("\n" + "=" * 70)
        print(f"Cycle {cycle} | {datetime.now(UTC)}")
        print("=" * 70)

        rows = scanner.scan()
        rows += options_adapter.fetch_option_rows(rows)

        rows = enrich(rows)

        open_positions = position_manager.get_open_positions()

        for r in rows:

            if len(open_positions) >= MAX_OPEN_POSITIONS:
                break

            if not r.get("tradable", True):
                continue

            ai = r.get("ai_score", 0)
            spread = abs(_safe_float(r.get("spread_bps", 10)))

            if ai < MIN_AI_SCORE or spread > MAX_SPREAD_BPS:
                continue

            price = _safe_float(r["price"])
            vwap = r.get("vwap") or compute_vwap(r)

            if not vwap or vwap <= 0:
                continue

            deviation = (price - vwap) / vwap

            symbol = r["symbol"]

            if symbol in {p["symbol"] for p in open_positions}:
                continue

            # =========================
            # LONG
            # =========================
            if deviation <= MIN_LONG_DEV:

                sl = price * 0.995
                tp = price + abs(vwap - price)

                size = compute_position_size(price, sl)

                position_manager.open_long_position(
                    symbol=symbol,
                    entry_price=price,
                    size=size,
                    take_profit=tp,
                    stop_loss=sl,
                    confidence=ai,
                    regime="LONG"
                )

            # =========================
            # SHORT
            # =========================
            elif deviation >= MIN_SHORT_DEV:

                sl = price * 1.005
                tp = price - abs(price - vwap)

                size = compute_position_size(price, sl)

                position_manager.open_short_position(
                    symbol=symbol,
                    entry_price=price,
                    size=size,
                    take_profit=tp,
                    stop_loss=sl,
                    confidence=ai,
                    regime="SHORT"
                )

        latest = {r["symbol"]: r.get("price", 0) for r in rows}
        position_manager.update_positions(latest)

        pnl = position_manager.get_total_pnl()

        closed = position_manager.get_closed_positions()
        wins = sum(1 for t in closed if t["pnl"] > 0)
        total = len(closed)

        print(f"\nPnL: {round(pnl,2)}")
        print(f"Trades: {total} | Wins: {wins} | Win Rate: {(wins/total*100 if total else 0):.1f}%")

        time.sleep(CYCLE_SLEEP)


if __name__ == "__main__":
    run()