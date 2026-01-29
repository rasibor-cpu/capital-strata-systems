from __future__ import annotations

"""
Live Manual FX Runner (MT5 DEMO PATH)

Purpose:
- Load config.json
- Generate a simple signal (VWAP-distance baseline)
- Create an MT5-ready ticket
- Export ticket to out/mt5_trade_tickets.csv
- Print clear instructions for manual execution in MT5

No broker API required.
No KYC required.
This enables "place trades" immediately (MT5 demo/manual).

NOTE:
For this first MT5 version, live price input is USER-PROVIDED (fastest, most reliable):
- You read current price from MT5 (or TradingView)
- You paste it here when prompted

Next iteration: we plug in a live quote feed provider.
"""

import json
import os
from typing import Any, Dict, Optional

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


def vwap_distance_signal(price: float, vwap: float, epsilon: float) -> str:
    """
    Returns 'buy', 'sell', or ''.
    Baseline logic:
    - If price is below vwap by epsilon -> buy (mean reversion up)
    - If price is above vwap by epsilon -> sell (mean reversion down)
    """
    if abs(price - vwap) < epsilon:
        return ""
    return "buy" if price < vwap else "sell"


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

    # Personal module baseline: pick 1 instrument to generate a ticket quickly
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

    # --- PRICE INPUT (manual live feed for fastest deployment) ---
    px_s = input(f"Enter current MID price for {inst} (from MT5): ").strip()
    try:
        price = float(px_s)
    except Exception:
        print("Invalid price.")
        return 1

    # --- VWAP proxy (v1): use current price as vwap baseline
    # Next iteration: rolling VWAP from streamed prices.
    vwap = price

    mode = cfg["strategy"]["accuracy_mode"]
    mode_cfg = cfg["strategy"]["modes"][mode]
    epsilon = float(mode_cfg["epsilon_gate"])

    # With vwap=price, baseline signal will be empty.
    # So we ask user for a "reference vwap" to simulate the edge until live VWAP is wired.
    print("\nNOTE: For MT5 v1, paste a reference VWAP/mean level (from your chart indicator).")
    vwap_s = input(f"Enter reference VWAP/mean for {inst} (from MT5 indicator): ").strip()
    try:
        vwap = float(vwap_s)
    except Exception:
        print("Invalid VWAP/mean.")
        return 1

    side = vwap_distance_signal(price, vwap, epsilon)
    if not side:
        print(f"\nNo signal: |price - vwap| < epsilon ({epsilon}). No ticket created.")
        return 0

    # Units -> lots conversion happens inside exporter
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

    reason = f"MT5 manual ticket | VWAP-distance baseline | mode={mode} | epsilon={epsilon}"

    ticket = make_mt5_ticket(
        instrument=inst,
        side=side,
        units=units,
        price_snapshot=price,
        stop_loss=sl,
        take_profit=tp,
        reason=reason
    )

    exporter = MT5TicketExporter("out/mt5_trade_tickets.csv")
    exporter.export(ticket)

    print("\n" + "=" * 68)
    print("MT5 TRADE TICKET CREATED (manual execution)")
    print("=" * 68)
    print(f"Symbol:        {ticket.symbol}")
    print(f"Side:          {ticket.side}")
    print(f"Volume (lots): {ticket.volume_lots}")
    print(f"Price snap:    {ticket.price_snapshot:.6f}")
    print(f"Stop Loss:     {ticket.stop_loss if ticket.stop_loss is not None else 'NONE'}")
    print(f"Take Profit:   {ticket.take_profit if ticket.take_profit is not None else 'NONE'}")
    print(f"Reason:        {ticket.reason}")
    print("=" * 68)
    print("Saved to: out/mt5_trade_tickets.csv")
    print("\nMT5 Steps:")
    print("1) Open MT5 → select the same symbol (e.g., EURUSD)")
    print("2) New Order → set Volume to the ticket lots")
    print("3) Choose Market Execution → BUY or SELL")
    print("4) Optional: set SL/TP to the ticket levels")
    print("5) Place the trade\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())