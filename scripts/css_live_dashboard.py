from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import time
import random
from datetime import datetime
from typing import Any

from backend.app.pnl.pnl_engine import Portfolio, Position
from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.app.security.auth_gate import await_login_ready_state

# =========================
# CONFIG
# =========================
SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD"]
FX_SYMBOLS = ["EUR_USD", "GBP_USD", "EUR_JPY", "GBP_JPY"]
OPTION_SYMBOLS = ["SPY_CALL", "QQQ_PUT"]
FUTURES_SYMBOLS = ["ES", "NQ", "CL", "GC"]

CYCLE_SLEEP = 6
MAX_OPEN_PER_CYCLE = 4

# =========================
# CAPITAL GOVERNOR
# =========================
class CapitalGovernor:
    def __init__(self):
        self.capital = 200.0
        self.used = 0.0
        self.per_trade = 20.0

    def available(self):
        return self.capital - self.used

    def allocate(self):
        if self.available() >= self.per_trade:
            self.used += self.per_trade
            return True
        return False

    def release(self):
        self.used = max(0, self.used - self.per_trade)


capital_governor = CapitalGovernor()

# =========================
# PORTFOLIO ENGINE
# =========================
pnl_observer = Portfolio(
    starting_balance=200.0,
    current_balance=200.0,
)

# =========================
# POSITION STORE
# =========================
positions = []
position_id = 0
# =========================
# SAFE SIGNAL ENGINE (FIXED)
# =========================
def generate_signal(candles):

    if not candles or len(candles) < 20:
        return 0.0, 0.0

    closes = []

    for c in candles:

        # Candle object (CRITICAL FIX)
        if hasattr(c, "close"):
            try:
                closes.append(float(c.close))
                continue
            except:
                pass

        # dict candle
        if isinstance(c, dict):
            close = c.get("close") or c.get("c")
            if close is not None:
                try:
                    closes.append(float(close))
                except:
                    pass

    if len(closes) < 20:
        return 0.0, 0.0

    momentum = (closes[-1] - closes[-10]) / (closes[-10] + 1e-9)

    volatility = (max(closes[-20:]) - min(closes[-20:])) / (closes[-1] + 1e-9)

    signal = abs(momentum) * 20 + volatility * 10
    prob = min(0.85, max(0.55, 0.5 + momentum * 2))

    return round(signal, 4), round(prob, 4)


# =========================
# DATA LOADER
# =========================
def load_data(symbol):
    try:
        raw = load_runtime_asset(symbol)

        if isinstance(raw, dict) and "candles" in raw:
            return raw["candles"]

        if isinstance(raw, list):
            return raw

        return []
    except:
        return []


# =========================
# SELECT CANDIDATES
# =========================
def select_candidates():

    all_symbols = (
        [("CRYPTO", s) for s in SYMBOLS]
        + [("FX", s) for s in FX_SYMBOLS]
        + [("OPTIONS", s) for s in OPTION_SYMBOLS]
        + [("FUTURES", s) for s in FUTURES_SYMBOLS]
    )

    candidates = []

    for asset, symbol in all_symbols:

        candles = load_data(symbol)

        if len(candles) < 20:
            continue

        sig, prob = generate_signal(candles)

        # QUALITY FILTER
        if sig < 10.5 or prob < 0.62:
            continue

        candidates.append((asset, symbol, sig, prob))

    candidates.sort(key=lambda x: x[2], reverse=True)

    return candidates[:MAX_OPEN_PER_CYCLE]
# =========================
# MAIN LOOP
# =========================
def run_dashboard():

    print("\n=== CSS REAL ENGINE (STABLE + FIXED) ===\n")

    await_login_ready_state()

    global position_id
    cycle = 0

    while True:

        cycle += 1

        print(f"\n{'='*60}")
        print(f"Cycle {cycle} | {datetime.now()}")
        print(f"{'='*60}")

        # =========================
        # OPEN POSITIONS
        # =========================
        for asset, symbol, sig, prob in select_candidates():

            if not capital_governor.allocate():
                continue

            position_id += 1

            size = max(0.01, round(sig / 20.0, 4))

            pos = {
                "id": f"P{position_id}",
                "symbol": symbol,
                "asset": asset,
                "pnl": 0.0,
                "prob": prob,
                "closed": False
            }

            positions.append(pos)

            observer_position = Position(
                symbol=f"{pos['id']}::{symbol}",
                asset_class=asset,
                side="LONG",
                quantity=size,
                entry_price=100.0,
                current_price=100.0,
            )

            pnl_observer.open_position(observer_position)

            print(f"[OPEN] {symbol} | Size={size} | Prob={prob:.2f}")

        # =========================
        # UPDATE + DRIFT
        # =========================
        mtm = 0.0

        for pos in positions:

            if pos["closed"]:
                continue

            drift = random.uniform(-0.05, 0.10)
            drift *= max(0.5, min(1.5, pos["prob"]))

            pos["pnl"] += drift
            mtm += pos["pnl"]

            key = f"{pos['id']}::{pos['symbol']}"
            pnl_observer.update_market_price(key, 100.0 + pos["pnl"])

            # EXIT LOGIC
            if pos["pnl"] > 3 or pos["pnl"] < -2:
                pos["closed"] = True
                capital_governor.release()

                pnl_observer.close_position(key, 100.0 + pos["pnl"])

                tag = "PROFIT" if pos["pnl"] > 0 else "LOSS"
                print(f"[EXIT {tag}] {pos['symbol']} | PnL={pos['pnl']:.2f}")

        # =========================
        # SUMMARY
        # =========================
        unreal = pnl_observer.compute_unrealized_pnl()
        real = pnl_observer.realized_pnl
        equity = pnl_observer.equity()

        print("\n--- PNL ---")
        print(f"REALIZED: {real:+.2f}")
        print(f"UNREALIZED: {unreal:+.2f}")
        print(f"EQUITY: {equity:+.2f}")

        if abs(unreal - mtm) > 0.5:
            print("[SYNC WARNING]")

        time.sleep(CYCLE_SLEEP)


# =========================
# ENTRY
# =========================
if __name__ == "__main__":
    run_dashboard()