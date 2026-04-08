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
MAX_TRADES_PER_CYCLE = 10
BASE_THRESHOLD = 0.15
CYCLE_SLEEP = 3

TP_PCT = 0.006
SL_PCT = 0.004
MAX_HOLD_CYCLES = 3

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
# HELPERS
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


def candle_price_candidates(candle: Any) -> List[float]:
    vals: List[float] = []

    if isinstance(candle, dict):
        for key in (
            "price", "close", "c", "last", "last_price",
            "mark", "mark_price", "settle", "settlement",
            "open", "high", "low"
        ):
            if key in candle:
                px = safe_float(candle.get(key), 0.0)
                if px > 0:
                    vals.append(px)
        return vals

    if isinstance(candle, (list, tuple)):
        nums = [safe_float(x, 0.0) for x in candle]

        for idx in (4, 3, 2, 1, 5, -1):
            try:
                px = nums[idx]
                if px > 0:
                    vals.append(px)
            except Exception:
                pass

        for px in nums:
            if px > 0:
                vals.append(px)

    return vals


def choose_reasonable_price(candidates: List[float]) -> float:
    if not candidates:
        return 0.0

    filtered = [x for x in candidates if 0.0000001 < x < 10_000_000]
    if not filtered:
        return 0.0

    for px in filtered:
        if px < 1_000_000:
            return px

    return filtered[0]


def extract_price_from_runtime(raw: Any, candles: List[Any]) -> float:
    if isinstance(raw, dict):
        for key in ("price", "last_price", "close", "current_price", "spot_price", "last"):
            if key in raw:
                px = safe_float(raw.get(key), 0.0)
                if px > 0:
                    return px

    if candles:
        return choose_reasonable_price(candle_price_candidates(candles[-1]))

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

        print(f"[WARN] open_position returned without creating position for {symbol}")
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

    # FETCH
    for symbol in SYMBOLS:
        try:
            raw = load_runtime_asset(symbol)
            candles = extract_candles(raw)

            if not candles:
                print(f"[WARN] No candles for {symbol}")
                continue

            runtime_price = extract_price_from_runtime(raw, candles)

            if isinstance(raw, dict) and "start" in raw and "end" in raw:
                print(f"Fetched {len(candles)} candles for {symbol} [{raw.get('start')} -> {raw.get('end')}]")
            else:
                print(f"Fetched {len(candles)} candles for {symbol}")

            raw_rows.append({
                "symbol": symbol,
                "candles": candles,
                "price": runtime_price,
                "raw_runtime": raw,
            })

        except Exception as e:
            print(f"[ERROR] fetch failed for {symbol}: {e}")

    if not raw_rows:
        time.sleep(CYCLE_SLEEP)
        continue

    # FEATURES
    try:
        rows = feature_builder.enrich_rows(raw_rows)
    except Exception as e:
        print(f"[FATAL] feature_builder failed: {e}")
        time.sleep(CYCLE_SLEEP)
        continue

    # restore raw runtime if enrich_rows rewrites rows
    raw_map = {r["symbol"]: r for r in raw_rows}
    for row in rows:
        sym = row.get("symbol")
        if sym in raw_map:
            row["raw_runtime"] = raw_map[sym].get("raw_runtime")
            if safe_float(row.get("price", 0.0), 0.0) <= 0:
                row["price"] = raw_map[sym].get("price", 0.0)

        row["confluence_score"] = 0.5
        row["pressure_score"] = 0.5

    # SCORING
    scores = []
    for row in rows:
        sc = safe_float(ai_scorer.score(row), 0.0)
        row["ai_score"] = sc
        scores.append(sc)

    avg = sum(scores) / len(scores) if scores else 0.0
    threshold = max(BASE_THRESHOLD, avg * 0.8)

    # adaptive pass band
    adaptive_min_pass = max(0.12, threshold)

    print(
        f"\nAI avg={avg:.4f} threshold={threshold:.4f} "
        f"adaptive_min_pass={adaptive_min_pass:.4f}"
    )

    # EXECUTION
    signals = passed = executed = 0
    skipped_zero_price = 0
    skipped_low_score = 0
    skipped_existing_position = 0

    for row in rows:
        score = safe_float(row.get("ai_score", 0.0), 0.0)

        if score >= threshold:
            signals += 1

            if score < adaptive_min_pass:
                skipped_low_score += 1
                continue

            passed += 1

            if executed >= MAX_TRADES_PER_CYCLE:
                continue

            symbol = str(row.get("symbol", "")).strip()
            price = get_effective_price(row)

            if price <= 0:
                skipped_zero_price += 1
                print(f"[SKIP] {symbol}: invalid execution price ({price})")
                continue

            if symbol in position_manager.positions:
                skipped_existing_position += 1
                continue

            if open_position(symbol, price, score):
                executed += 1

                try:
                    trade_logger.log_trade({
                        "timestamp": str(datetime.utcnow()),
                        "symbol": symbol,
                        "entry_price": price,
                        "take_profit": price * (1 + TP_PCT),
                        "stop_loss": price * (1 - SL_PCT),
                        "score": score,
                        "action": "OPEN",
                    })
                except Exception:
                    pass

    # UPDATE
    price_map = {}
    for row in rows:
        symbol = str(row.get("symbol", "")).strip()
        price = get_effective_price(row)
        if symbol and price > 0:
            price_map[symbol] = price

    try:
        position_manager.update_positions(price_map)
    except Exception as e:
        print(f"[WARN] update_positions failed: {e}")

    # POSITION DEBUG + TIME EXIT
    print("\n--- POSITION DEBUG ---")
    for sym, pos in list(position_manager.positions.items()):
        entry = safe_float(pos.get("entry_price"), 0.0)
        tp = safe_float(pos.get("take_profit"), 0.0)
        sl = safe_float(pos.get("stop_loss"), 0.0)
        current = safe_float(price_map.get(sym, 0.0), 0.0)

        position_cycles[sym] = position_cycles.get(sym, 0) + 1

        print(
            f"{sym} | entry={entry:.4f} | current={current:.4f} | "
            f"TP={tp:.4f} | SL={sl:.4f} | cycles={position_cycles[sym]}"
        )

        if current >= tp and tp > 0:
            print(f"👉 TP HIT: {sym}")
        elif current <= sl and sl > 0:
            print(f"👉 SL HIT: {sym}")

        if position_cycles[sym] >= MAX_HOLD_CYCLES:
            print(f"⏳ TIME EXIT: {sym}")
            close_position(sym, current, "TIME")

            try:
                trade_logger.log_trade({
                    "timestamp": str(datetime.utcnow()),
                    "symbol": sym,
                    "exit_price": current,
                    "reason": "TIME",
                    "action": "CLOSE",
                })
            except Exception:
                pass

    # PERFORMANCE
    closed = position_manager.closed_log
    pnl = sum(safe_float(t.get("pnl", 0.0), 0.0) for t in closed)
    wins = sum(1 for t in closed if safe_float(t.get("pnl", 0.0), 0.0) > 0)

    print("\n--- DIAGNOSTICS ---")
    print(
        f"Signals: {signals} | Passed: {passed} | Executed: {executed} | "
        f"Skipped Zero Price: {skipped_zero_price} | "
        f"Skipped Low Score: {skipped_low_score} | "
        f"Skipped Existing: {skipped_existing_position}"
    )

    print("\n--- PERFORMANCE ---")
    print(f"PnL: {pnl:.4f}")
    print(f"Open Positions: {len(position_manager.positions)}")
    print(f"Closed Trades: {len(closed)}")
    print(f"Wins: {wins}")

    time.sleep(CYCLE_SLEEP)