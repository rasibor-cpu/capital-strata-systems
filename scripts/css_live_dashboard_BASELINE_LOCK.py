# ===============================
# CSS DASHBOARD — BASELINE LOCK
# PCNRASS SAFE VERSION
# ===============================

import time
import random
from datetime import datetime

# ---------------------------------
# SAFE SIGNAL PROVIDER FALLBACK
# ---------------------------------
try:
    from backend.intelligence.safe_signal_provider import SafeSignalProvider
except Exception:
    class SafeSignalProvider:
        def get_signal(self, symbol):
            return {
                "score": round(random.uniform(6, 10), 2),
                "prob": round(random.uniform(0.4, 0.75), 3),
                "core": round(random.uniform(0.2, 0.6), 3),
                "vel": round(random.uniform(0.0, 0.1), 3),
                "acc": round(random.uniform(0.0, 0.1), 3),
                "press": round(random.uniform(0.0, 0.5), 3),
                "liq": round(random.uniform(0.0, 1.0), 3)
            }

signal_provider = SafeSignalProvider()

# ---------------------------------
# CONFIG
# ---------------------------------
CYCLE_SLEEP = 3
MAX_CYCLES = 999999

symbols = [
    "BTC-USD", "ETH-USD", "SOL-USD",
    "EUR_USD", "GBP_USD", "USD_JPY",
    "AAPL-C", "QQQ-C"
]

# ---------------------------------
# STATE
# ---------------------------------
cycle = 0
balance = 100.0
positions = {}

# ---------------------------------
# UTIL
# ---------------------------------
def print_header():
    print("\n" + "=" * 70)
    print(" CSS DASHBOARD — BASELINE LOCK (PCNRASS SAFE) ")
    print("=" * 70)

def print_decision(symbol, sig):
    print(f"[DECISION] {symbol} | score={sig['score']} prob={sig['prob']} core={sig['core']} vel={sig['vel']} acc={sig['acc']} press={sig['press']} liq={sig['liq']}")

def open_position(symbol):
    if symbol in positions:
        print(f"[BLOCK] {symbol} already open")
        return
    positions[symbol] = {
        "entry": round(random.uniform(1, 300), 4),
        "current": None
    }
    print(f"[OPEN] {symbol}")

def update_positions():
    for s in positions:
        positions[s]["current"] = positions[s]["entry"]

def print_positions():
    print("\n--- OPEN POSITION MTM ---")
    print("POS | SYMBOL | ENTRY | CURRENT | UPNL")
    i = 1
    for s, p in positions.items():
        print(f"{i} | {s} | {p['entry']} | {p['current']} | 0.0000")
        i += 1

def print_summary():
    print("\n--- PNL SUMMARY ---")
    print(f"BALANCE: {balance:.4f}")
    print(f"OPEN POSITIONS: {len(positions)}")

def pcnrass_pause():
    print("\n[PCNRASS REVIEW HOLD] Cycle complete.")
    print("Press ENTER to continue or Q to quit.")
    cmd = input(">> ").strip().lower()
    if cmd == "q":
        print("[STOP] Safe exit.")
        exit()

# ---------------------------------
# MAIN LOOP
# ---------------------------------
def run():
    global cycle

    print_header()

    while True:
        cycle += 1
        print(f"\n--- CYCLE {cycle} ---")

        for sym in symbols:
            sig = signal_provider.get_signal(sym)
            print_decision(sym, sig)

            # SIMPLE ENTRY RULE (baseline safe)
            if sig["prob"] > 0.6 and sig["score"] > 7:
                open_position(sym)

        update_positions()
        print_positions()
        print_summary()

        pcnrass_pause()

        time.sleep(CYCLE_SLEEP)

# ---------------------------------
# ENTRY
# ---------------------------------
if __name__ == "__main__":
    run()