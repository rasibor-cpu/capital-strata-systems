"""
CSS Portfolio Dashboard v60
Professional Portfolio Monitor
Backward-compatible with older position schemas
"""

import json
import time
from pathlib import Path
from datetime import datetime, UTC

STATE_DIR = Path("backend/state")
POSITION_FILE = STATE_DIR / "spot_position.json"

REFRESH = 5
DEFAULT_TRAIL_PCT = 0.01


def load_position():
    if not POSITION_FILE.exists():
        return None
    try:
        with open(POSITION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def clear():
    print("\033[2J\033[H", end="")


def print_header():
    print("=" * 70)
    print(" CAPITAL STRATA SYSTEMS — PROFESSIONAL PORTFOLIO DASHBOARD ")
    print("=" * 70)


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return bool(value)


def print_position(pos):
    print("\nPOSITION STATUS\n")

    asset = pos.get("asset", "UNKNOWN")
    entry = _to_float(pos.get("entry_price"), 0.0)

    original_units = _to_float(
        pos.get("original_units", pos.get("units", 0.0)),
        0.0,
    )
    remaining_units = _to_float(
        pos.get("remaining_units", pos.get("units", 0.0)),
        0.0,
    )

    realized = _to_float(pos.get("realized_profit", 0.0), 0.0)
    highest = _to_float(pos.get("highest_price", entry), entry)

    ladder1 = _to_bool(pos.get("ladder1_done", False), False)
    ladder2 = _to_bool(pos.get("ladder2_done", False), False)

    opened_at = pos.get("timestamp", "N/A")

    print(f"Asset               : {asset}")
    print(f"Entry Price         : {entry:.6f}")
    print(f"Original Units      : {original_units:.6f}")
    print(f"Remaining Units     : {remaining_units:.6f}")
    print(f"Highest Price       : {highest:.6f}")

    print("\nPROFIT STATUS\n")
    print(f"Realized Profit     : {realized:.2f}")

    print("\nLADDER STATUS\n")
    print(f"Ladder 1 Executed   : {ladder1}")
    print(f"Ladder 2 Executed   : {ladder2}")

    trail = highest * (1 - DEFAULT_TRAIL_PCT)

    print("\nRISK CONTROL\n")
    print(f"Trailing Stop Level : {trail:.6f}")

    print("\nTRADE OPENED\n")
    print(opened_at)


def main():
    while True:
        clear()
        print_header()

        pos = load_position()

        if not pos:
            print("\nNO OPEN POSITION\n")
        else:
            print_position(pos)

        print("\nLast Update:", datetime.now(UTC).isoformat())
        print(f"\nRefreshing in {REFRESH} seconds...")

        time.sleep(REFRESH)


if __name__ == "__main__":
    main()