from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ========================
# IMPORTS
# ========================
from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.execution.position_manager import PositionManager

from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_position_manager import FuturesPositionManager

from backend.scanner.options_chain_adapter import OptionsChainAdapter

# ========================
# CONFIG
# ========================
CYCLE_SLEEP = 3

MAX_CRYPTO = 3
MAX_FUTURES = 2

TP_PCT = 0.006
SL_PCT = 0.004
MAX_HOLD = 3

MIN_SCORE = 0.08

SYMBOLS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
    "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD",
    "LTC-USD", "BCH-USD",
]

FUTURES_SYMBOLS = ["ES", "NQ"]

# ========================
# INIT
# ========================
pm = PositionManager()

futures_adapter = FuturesSimAdapter(max_portfolio_allocation=5.0)
futures_pm = FuturesPositionManager(futures_adapter)

options_adapter = OptionsChainAdapter()

prev_prices: Dict[str, float] = {}
pos_cycles: Dict[str, int] = {}

# ========================
# HELPERS
# ========================
def safe(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def candles_of(x: Any) -> List[Any]:
    if isinstance(x, dict):
        candles = x.get("candles", [])
        return candles if isinstance(candles, list) else []
    if isinstance(x, list):
        return x
    return []


def close_of(c: Any) -> float:
    if isinstance(c, dict):
        return safe(c.get("close"))
    if isinstance(c, (list, tuple)) and len(c) > 4:
        return safe(c[4])
    return 0.0


def price_of(raw: Any, candles: List[Any]) -> float:
    if isinstance(raw, dict):
        for k in ("price", "last_price", "close", "current_price", "spot_price", "last"):
            p = safe(raw.get(k))
            if p > 0:
                return p
    return close_of(candles[-1]) if candles else 0.0


def score(symbol: str, price: float, candles: List[Any]) -> float:
    prev = prev_prices.get(symbol, 0.0)
    move = abs((price - prev) / prev) if prev > 0 else 0.0

    closes = [close_of(c) for c in candles[-6:] if close_of(c) > 0]
    vol = 0.0
    if len(closes) > 1:
        vol = sum(
            abs((closes[i] - closes[i - 1]) / closes[i - 1])
            for i in range(1, len(closes))
            if closes[i - 1] > 0
        ) / (len(closes) - 1)

    return (move * 0.7 + vol * 0.3) * 10000.0


def build_tp_sl(price: float):
    return price * (1 + TP_PCT), price * (1 - SL_PCT)


def get_open_crypto_unrealized(price_map: Dict[str, float]) -> float:
    total = 0.0
    for sym, pos in pm.positions.items():
        entry = safe(pos.get("entry_price"))
        cur = safe(price_map.get(sym))
        size = safe(pos.get("size", 1.0), 1.0)
        if entry > 0 and cur > 0:
            total += (cur - entry) * size
    return total


def get_closed_crypto_realized() -> float:
    return sum(safe(t.get("pnl", 0.0)) for t in pm.closed_log)


def get_closed_crypto_wins() -> int:
    return sum(1 for t in pm.closed_log if safe(t.get("pnl", 0.0)) > 0)


def get_closed_crypto_losses() -> int:
    return sum(1 for t in pm.closed_log if safe(t.get("pnl", 0.0)) < 0)


def print_recent_closed_trades(limit: int = 5) -> None:
    recent = pm.closed_log[-limit:]
    if not recent:
        print("No closed crypto trades yet.")
        return

    for t in reversed(recent):
        symbol = t.get("symbol", "?")
        entry = safe(t.get("entry_price", 0.0))
        exit_price = safe(t.get("exit_price", 0.0))
        pnl = safe(t.get("pnl", 0.0))
        reason = t.get("reason", "N/A")
        print(
            f"{symbol} | entry={entry:.4f} | exit={exit_price:.4f} | "
            f"pnl={pnl:.4f} | reason={reason}"
        )


def force_close_crypto_position(symbol: str, current_price: float, reason: str) -> None:
    """
    Hard-close wrapper:
    1. Calls the existing PositionManager close logic
    2. Force-removes the position from the open-position store
    """
    try:
        pm.close_position(symbol, current_price, reason)
    except Exception as e:
        print(f"[CLOSE ERROR] {symbol}: {e}")
    finally:
        pm.positions.pop(symbol, None)


# ========================
# MAIN LOOP
# ========================
cycle = 0

while True:
    cycle += 1
    print(f"\n=== Cycle {cycle} | {datetime.now()} ===")

    rows: List[Dict[str, Any]] = []
    price_map: Dict[str, float] = {}

    # =====================
    # CRYPTO DATA
    # =====================
    for s in SYMBOLS:
        try:
            raw = load_runtime_asset(s)
            cds = candles_of(raw)
            if not cds:
                continue

            px = price_of(raw, cds)
            sc = score(s, px, cds)

            row = {
                "symbol": s,
                "price": px,
                "score": sc,
                "candles": cds,
            }
            rows.append(row)
            price_map[s] = px

            print(f"Fetched {len(cds)} candles for {s}")
        except Exception as e:
            print(f"[DATA ERROR] {s}: {e}")

    rows.sort(key=lambda x: -x["score"])

    print("\n--- CRYPTO ---")
    for r in rows[:5]:
        print(f"{r['symbol']} | score={r['score']:.2f}")

    # =====================
    # UPDATE + EXIT (CRYPTO)
    # =====================
    try:
        pm.update_positions(price_map)
    except Exception as e:
        print("[UPDATE ERROR]", e)

    print("\n--- POSITION DEBUG ---")
    for sym, pos in list(pm.positions.items()):
        entry = safe(pos.get("entry_price"))
        cur = safe(price_map.get(sym))
        if entry <= 0 or cur <= 0:
            continue

        pnl_pct = (cur - entry) / entry
        pos_cycles[sym] = pos_cycles.get(sym, 0) + 1

        print(f"{sym} | pnl={pnl_pct:.4%} | cycles={pos_cycles[sym]}")

        if pnl_pct >= TP_PCT:
            print(f"[TP] {sym}")
            force_close_crypto_position(sym, cur, "TP")
            pos_cycles.pop(sym, None)

        elif pnl_pct <= -SL_PCT:
            print(f"[SL] {sym}")
            force_close_crypto_position(sym, cur, "SL")
            pos_cycles.pop(sym, None)

        elif pos_cycles[sym] >= MAX_HOLD:
            print(f"[TIME EXIT] {sym}")
            force_close_crypto_position(sym, cur, "TIME")
            pos_cycles.pop(sym, None)

    # =====================
    # ENTRY (CRYPTO)
    # =====================
    open_crypto = len(pm.positions)
    executed_crypto = 0

    for r in rows:
        if open_crypto >= MAX_CRYPTO:
            break

        if r["symbol"] in pm.positions:
            continue

        if r["score"] < MIN_SCORE:
            continue

        tp, sl = build_tp_sl(r["price"])

        try:
            pm.open_position(
                symbol=r["symbol"],
                entry_price=r["price"],
                size=1,
                take_profit=tp,
                stop_loss=sl,
                side="LONG",
                confidence=r["score"],
            )
            print(f"[CRYPTO OPEN] {r['symbol']} @ {r['price']:.4f}")
            open_crypto += 1
            executed_crypto += 1
        except Exception as e:
            print(f"[CRYPTO ERROR] {r['symbol']}: {e}")

    # =====================
    # ENTRY (FUTURES)
    # =====================
    futures_open = len(futures_pm.get_open_positions())
    executed_futures = 0

    for f in FUTURES_SYMBOLS:
        if futures_open >= MAX_FUTURES:
            break

        proxy_symbol = "BTC-USD" if f == "ES" else "ETH-USD"

        px = price_map.get(proxy_symbol, 0.0)
        sc = next((r["score"] for r in rows if r["symbol"] == proxy_symbol), 0.0)

        if px <= 0:
            print(f"[FUTURES SKIP] {f} no price")
            continue

        if sc < MIN_SCORE:
            print(f"[FUTURES SKIP] {f} weak score")
            continue

        already_open_same = any(
            p.get("symbol") == f and p.get("status") == "OPEN"
            for p in futures_pm.get_open_positions()
        )
        if already_open_same:
            print(f"[FUTURES SKIP] {f} already open")
            continue

        try:
            res = futures_pm.open_position(
                symbol=f,
                entry_price=px,
                stop_price=px * (1 - SL_PCT),
                contracts=1,
                current_equity=10000,
                state={},
            )

            if res.get("status") == "OPENED":
                print(f"[FUTURES OPEN] {f}")
                futures_open += 1
                executed_futures += 1
            else:
                print(f"[FUTURES BLOCKED] {f} {res}")
        except Exception as e:
            print(f"[FUTURES ERROR] {f}: {e}")

    # =====================
    # OPTIONS SCAN
    # =====================
    option_rows: List[Dict[str, Any]] = []
    try:
        option_inputs = [
            {"symbol": r["symbol"], "price": r["price"]}
            for r in rows[:3]
            if r["price"] > 0
        ]
        option_rows = options_adapter.fetch_option_rows(option_inputs)

        print("\n--- OPTIONS ---")
        print(f"Visible option contracts: {len(option_rows)}")
        for opt in option_rows[:5]:
            print(
                f"{opt.get('symbol')} {opt.get('option_type')} "
                f"strike={safe(opt.get('strike')):.4f} "
                f"price={safe(opt.get('price')):.4f}"
            )
    except Exception as e:
        print("[OPTIONS ERROR]", e)

    # =====================
    # PROFIT DASHBOARD
    # =====================
    realized = get_closed_crypto_realized()
    unrealized = get_open_crypto_unrealized(price_map)
    wins = get_closed_crypto_wins()
    losses = get_closed_crypto_losses()
    closed = len(pm.closed_log)
    win_rate = (wins / closed * 100.0) if closed > 0 else 0.0

    print("\n--- PROFIT DASHBOARD ---")
    print(f"Executed Crypto This Cycle: {executed_crypto}")
    print(f"Executed Futures This Cycle: {executed_futures}")
    print(f"Closed Crypto Trades: {closed}")
    print(f"Wins: {wins} | Losses: {losses} | Win Rate: {win_rate:.2f}%")
    print(f"Realized Crypto PnL: {realized:.4f}")
    print(f"Unrealized Crypto PnL: {unrealized:.4f}")

    print("\n--- RECENT CLOSED CRYPTO TRADES ---")
    print_recent_closed_trades(limit=5)

    # =====================
    # STATUS
    # =====================
    print("\n--- STATUS ---")
    print(f"Crypto Open: {len(pm.positions)}")
    print(f"Futures Open: {len(futures_pm.get_open_positions())}")
    print(f"Options Visible: {len(option_rows)}")

    # =====================
    # STORE
    # =====================
    for r in rows:
        if r["price"] > 0:
            prev_prices[r["symbol"]] = r["price"]

    time.sleep(CYCLE_SLEEP)