from __future__ import annotations

"""
MT5 Manual Runner v2 (CSV-driven, NO manual VWAP entry)

This version:
- Uses MT5-exported CSV bars
- Computes rolling mean (VWAP proxy) automatically
- Uses last close as price
- Applies epsilon gate from config.json
- Exports MT5 trade ticket for manual execution

No broker API.
No KYC.
Fully aligned with personal module objectives.
"""

import json
import os
from typing import Any, Dict, Optional

from mt5_barfeed_csv import compute_rolling_mean_from_mt5_csv
from mt5_ticket_export import MT5TicketExporter, make_mt5_ticket


# -------------------------
# Helpers
# -------------------------

def load_config(path: str = "config.json") -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
        if not raw:
            raise ValueError("config.json is empty.")
        return json.loads(raw)


def pip_value(instrument: str) -> float:
    return 0.01 if instrument.endswith("_JPY") else 0.0001


def vwap_distance_signal(price: float, mean_level: float, epsilon: float) -> str:
    if abs(price - mean_level) < epsilon:
        return ""
    return "buy" if price < mean_level else "sell"


def compute_sl_tp(
    side: str,
    price: float,
    instrument: str,
    require_sl_tp: bool,
    sl_pips: int,
    tp_pips: int
) -> tuple[Optional[float], Optional[float]]:
    if not require_sl_tp:
        return None, None

    pv = pip_value(instrument)
    if side == "buy":
        sl = price - sl_pips * pv
        tp = price + tp_pips * pv
    else:
        sl = price + sl_pips * pv
        tp = price - tp_pips * pv
    return sl, tp


# -------------------------
# Main
# -------------------------

def main() -> int:
    cfg = load_config("config.json")

    instruments = cfg["instruments"]["enabled"]
    if not instruments:
        print("No instruments enabled in config.json.")
        return 0

    print("\nEnabled instruments:")
    for i, inst in enumerate(instruments, start=1):
        print(f" {i}) {inst}")

    sel = input("\nSelect instrument number (e.g., 1): ").strip()
    if not sel.isdigit():
        print("Invalid selection.")
        return 1

    idx = int(sel) - 1
    if idx < 0 or idx >= len(instruments):
        print("Selection out of range.")
        return 1

    inst = instruments[idx]

    lookback = int(cfg["strategy"].get("lookback_points", 30))

    print("\nExport bars from MT5 for the SAME symbol/timeframe.")
    print("Example: C:\\Users\\rasib\\Downloads\\EURUSD_M5.csv\n")

    csv_path = input(f"Enter MT5 CSV path for {inst}: ").strip().strip('"')

    try:
        res = compute_rolling_mean_from_mt5_csv(csv_path, lookback=lookback)
    except Exception as e:
        print(f"CSV processing failed: {e}")
        return 1

    price = res.last_close
    mean_level = res.mean_level

    mode = cfg["strategy"]["accuracy_mode"]
    epsilon = float(cfg["strategy"]["modes"][mode]["epsilon_gate"])

    side = vwap_distance_signal(price, mean_level, epsilon)
    if not side:
        print(f"\nNo signal generated.")
        print(f"price={price:.6f} mean={mean_level:.6f} epsilon={epsilon}")
        return 0

    units = int(cfg["risk"]["default_units"])
    units = min(units, int(cfg["risk"]["max_units"]))

    sl, tp = compute_sl_tp(
        side=side,
        price=price,
        instrument=inst,
        require_sl_tp=bool(cfg["risk"].get("require_sl_tp", False)),
        sl_pips=int(cfg["risk"]["default_sl_pips"]),
        tp_pips=int(cfg["risk"]["default_tp_pips"]),
    )

    ticket = make_mt5_ticket(
        instrument=inst,
        side=side,
        units=units,
        price_snapshot=price,
        stop_loss=sl,
        take_profit=tp,
        reason=f"MT5 v2 | rolling-mean | mode={mode} | epsilon={epsilon}"
    )

    exporter = MT5TicketExporter("out/mt5_trade_tickets.csv")
    exporter.export(ticket)

    print("\n" + "=" * 70)
    print("MT5 TRADE TICKET CREATED (manual execution)")
    print("=" * 70)
    print(f"Symbol:        {ticket.symbol}")
    print(f"Side:          {ticket.side}")
    print(f"Volume (lots): {ticket.volume_lots}")
    print(f"Price:         {ticket.price_snapshot:.6f}")
    print(f"Mean level:    {mean_level:.6f}")
    print(f"Stop Loss:     {ticket.stop_loss if ticket.stop_loss else 'NONE'}")
    print(f"Take Profit:   {ticket.take_profit if ticket.take_profit else 'NONE'}")
    print("=" * 70)
    print("Saved to: out/mt5_trade_tickets.csv\n")

    print("MT5 Execution:")
    print("1) Open MT5 → select symbol")
    print("2) New Order → set Volume")
    print("3) Market Execution → BUY or SELL")
    print("4) Optional: set SL/TP")
    print("5) Place trade\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())