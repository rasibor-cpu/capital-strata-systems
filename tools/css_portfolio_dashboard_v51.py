import json
import time
from pathlib import Path
from datetime import datetime

STATE_DIR = Path("backend/state")
POSITION_FILE = STATE_DIR / "spot_position.json"
TRADE_LOG = Path("audit_logs/trades.jsonl")


def load_position():
    try:
        if POSITION_FILE.exists():
            with open(POSITION_FILE) as f:
                return json.load(f)
    except:
        pass
    return None


def load_trades():

    trades = []

    if not TRADE_LOG.exists():
        return trades

    with open(TRADE_LOG) as f:
        for line in f:
            try:
                trades.append(json.loads(line))
            except:
                pass

    return trades


def compute_realized(trades):

    pnl = 0

    for t in trades:
        pnl += t.get("pnl", 0)

    return pnl


def print_header():

    print("\n" + "=" * 70)
    print(" CAPITAL STRATA SYSTEMS — PORTFOLIO DASHBOARD ")
    print("=" * 70)


def dashboard_loop():

    while True:

        print_header()

        position = load_position()
        trades = load_trades()

        realized = compute_realized(trades)

        print("\nPORTFOLIO STATUS\n")

        if position:

            entry = position.get("entry_price")
            size = position.get("size_usd")
            ts = position.get("timestamp")

            print(f"Entry Price : {entry}")
            print(f"Position USD: ${size}")
            print(f"Opened At   : {ts}")

        else:

            print("No open position")

        print("\nTRADE SUMMARY\n")

        print(f"Total Trades : {len(trades)}")
        print(f"Realized PnL : ${realized:.2f}")

        print("\nLast Update:", datetime.utcnow())

        print("\nRefreshing in 5 seconds...")

        time.sleep(5)


if __name__ == "__main__":
    dashboard_loop()