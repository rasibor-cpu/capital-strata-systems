from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.execution.position_manager import PositionManager
from backend.execution.trade_logger import TradeLogger

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.feature_builder import FeatureBuilder

# ========================
# CONFIG
# ========================
MAX_TRADES_PER_CYCLE = 5
BASE_THRESHOLD = 0.15
CYCLE_SLEEP = 3

TP_PCT = 0.006
SL_PCT = 0.004
MAX_HOLD_CYCLES = 2

PROFIT_LOCK_PCT = 0.002
STRONG_PROFIT_PCT = 0.004
WEAK_MOVE_PCT = 0.001

SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
    "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD",
    "LTC-USD", "BCH-USD",
]

feature_builder = FeatureBuilder()
ai_scorer = AIOpportunityScorer()

position_manager = PositionManager()
trade_logger = TradeLogger()

position_cycles: Dict[str, int] = {}

# ========================
# HELPERS (UNCHANGED)
# ========================
def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def extract_candles(data: Any) -> List[Any]:
    if isinstance(data, dict):
        candles = data.get("candles", [])
        return candles if isinstance(candles, list) else []
    if isinstance(data, list):
        return data
    return []


def extract_price_from_runtime(raw: Any, candles: List[Any]) -> float:
    if isinstance(raw, dict):
        for key in ("price", "last_price", "close", "current_price", "spot_price", "last"):
            if key in raw:
                px = safe_float(raw.get(key), 0.0)
                if px > 0:
                    return px

    if candles:
        last = candles[-1]
        if isinstance(last, (list, tuple)) and len(last) > 4:
            px = safe_float(last[4], 0.0)
            if px > 0:
                return px

    return 0.0


def get_effective_price(row: Dict[str, Any]) -> float:
    for key in ("price", "close", "last_price", "current_price"):
        if key in row:
            px = safe_float(row.get(key), 0.0)
            if px > 0:
                return px

    raw = row.get("raw_runtime")
    candles = row.get("candles", [])
    if isinstance(candles, list):
        px = extract_price_from_runtime(raw, candles)
        if px > 0:
            return px

    return 0.0


def build_tp_sl(price: float):
    return price * (1 + TP_PCT), price * (1 - SL_PCT)


def open_position(symbol: str, price: float, score: float) -> bool:
    tp, sl = build_tp_sl(price)

    try:
        position_manager.open_position(
            symbol=symbol,
            entry_price=price,
            size=1.0,
            take_profit=tp,
            stop_loss=sl,
            side="LONG",
            confidence=score,
            regime="RECOVERY",
        )

        if symbol in position_manager.positions:
            position_cycles[symbol] = 0
            print(f"[OPEN] {symbol} @ {price:.4f} | TP={tp:.4f} | SL={sl:.4f} | score={score:.4f}")
            return True

        return False

    except Exception as e:
        print(f"[WARN] open failed for {symbol}: {e}")
        return False


def close_position(symbol: str, price: float, reason: str):
    try:
        position_manager.close_position(symbol, price, reason)
        position_cycles.pop(symbol, None)
        print(f"[CLOSE] {symbol} @ {price:.4f} | reason={reason}")
    except Exception as e:
        print(f"[WARN] close failed for {symbol}: {e}")


# ========================
# MAIN LOOP
# ========================
cycle = 0

while True:
    cycle += 1
    print("\n" + "=" * 70)
    print(f"Cycle {cycle} | {datetime.now(timezone.utc)}")
    print("=" * 70)

    raw_rows: List[Dict[str, Any]] = []

    for symbol in SYMBOLS:
        try:
            raw = load_runtime_asset(symbol)
            candles = extract_candles(raw)

            if not candles:
                continue

            runtime_price = extract_price_from_runtime(raw, candles)

            raw_rows.append({
                "symbol": symbol,
                "candles": candles,
                "price": runtime_price,
                "raw_runtime": raw,
            })

        except Exception:
            continue

    if not raw_rows:
        time.sleep(CYCLE_SLEEP)
        continue

    try:
        rows = feature_builder.enrich_rows(raw_rows)
    except Exception:
        time.sleep(CYCLE_SLEEP)
        continue

    raw_map = {r["symbol"]: r for r in raw_rows}
    for row in rows:
        sym = row.get("symbol")
        if sym in raw_map:
            row["raw_runtime"] = raw_map[sym].get("raw_runtime")
            if safe_float(row.get("price", 0.0), 0.0) <= 0:
                row["price"] = raw_map[sym].get("price", 0.0)

        row["confluence_score"] = 0.5
        row["pressure_score"] = 0.5

    scores = []
    for row in rows:
        sc = safe_float(ai_scorer.score(row), 0.0)
        row["ai_score"] = sc
        scores.append(sc)

    avg = sum(scores) / len(scores) if scores else 0.0
    threshold = max(BASE_THRESHOLD, avg * 0.8)
    adaptive_min_pass = max(0.12, threshold)

    print(
        f"\nAI avg={avg:.4f} threshold={threshold:.4f} "
        f"adaptive_min_pass={adaptive_min_pass:.4f}"
    )

    signals = passed = executed = 0

    for row in rows:
        score = safe_float(row.get("ai_score", 0.0), 0.0)

        if score < threshold or score < adaptive_min_pass:
            continue

        signals += 1
        passed += 1

        if executed >= MAX_TRADES_PER_CYCLE:
            continue

        symbol = str(row.get("symbol", "")).strip()
        price = get_effective_price(row)

        if price <= 0 or symbol in position_manager.positions:
            continue

        if open_position(symbol, price, score):
            executed += 1

    price_map = {}
    for row in rows:
        symbol = str(row.get("symbol", "")).strip()
        price = get_effective_price(row)
        if symbol and price > 0:
            price_map[symbol] = price

    try:
        position_manager.update_positions(price_map)
    except Exception:
        pass

    print("\n--- POSITION DEBUG ---")
    for sym, pos in list(position_manager.positions.items()):
        entry = safe_float(pos.get("entry_price"), 0.0)
        current = safe_float(price_map.get(sym, 0.0), 0.0)

        if current <= 0:
            continue

        position_cycles[sym] = position_cycles.get(sym, 0) + 1
        pnl_pct = (current - entry) / entry

        print(f"{sym} | pnl={pnl_pct:.4%} | cycles={position_cycles[sym]}")

        # STRONG PROFIT
        if pnl_pct >= STRONG_PROFIT_PCT:
            close_position(sym, current, "STRONG_PROFIT")

        # NORMAL PROFIT LOCK
        elif pnl_pct >= PROFIT_LOCK_PCT:
            close_position(sym, current, "PROFIT_LOCK")

        # WEAK EXIT
        elif position_cycles[sym] >= MAX_HOLD_CYCLES and pnl_pct < WEAK_MOVE_PCT:
            close_position(sym, current, "WEAK_EXIT")

        # TIME EXIT
        elif position_cycles[sym] >= MAX_HOLD_CYCLES:
            close_position(sym, current, "TIME")

    closed = position_manager.closed_log
    pnl = sum(safe_float(t.get("pnl", 0.0), 0.0) for t in closed)
    wins = sum(1 for t in closed if safe_float(t.get("pnl", 0.0), 0.0) > 0)

    print("\n--- PERFORMANCE ---")
    print(f"PnL: {pnl:.4f}")
    print(f"Open Positions: {len(position_manager.positions)}")
    print(f"Closed Trades: {len(closed)}")
    print(f"Wins: {wins}")

    time.sleep(CYCLE_SLEEP)