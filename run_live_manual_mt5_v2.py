from __future__ import annotations

"""
MT5 Manual Runner v3 — ENGINE-WIRED (LOCKED)

This runner:
- Loads MT5-exported CSV
- Delegates ALL logic to rea_engine_personal.py
- Receives a Decision object
- Exports MT5 ticket if BUY/SELL
- Records NO_TRADE decisions automatically

NO SIGNAL LOGIC LIVES HERE.
"""

import os
import json

import instrument_registry as ir
from mt5_barfeed_csv import compute_rolling_mean_from_mt5_csv
from mt5_ticket_export import MT5TicketExporter, make_mt5_ticket
from execution_simulator import record_no_trade
from rea_engine_personal import REAEngine


# -------------------------
# Config
# -------------------------

def load_config(path: str = "config.json") -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# -------------------------
# Main
# -------------------------

def main() -> int:
    cfg = load_config("config.json")
    engine = REAEngine(cfg)

    instruments = ir.list_instruments()
    print("\nRegistry instruments:")
    for i, sym in enumerate(instruments, start=1):
        print(f" {i}) {sym}")

    sel = input("\nSelect instrument number: ").strip()
    if not sel.isdigit():
        print("Invalid selection.")
        return 1

    symbol = instruments[int(sel) - 1]

    print("\nExport MT5 bars for the SAME symbol/timeframe (M5).")
    csv_path = input(f"Enter MT5 CSV path for {symbol}: ").strip().strip('"')

    try:
        bars = compute_rolling_mean_from_mt5_csv(
            csv_path,
            lookback=engine.lookback_bars
        )
    except Exception as e:
        print(f"CSV error: {e}")
        return 1

    decision = engine.decide(
        symbol=symbol,
        last_price=bars.last_close,
        mean_level=bars.mean_level,
        source_file=os.path.basename(csv_path),
    )

    # -------------------------
    # Handle NO_TRADE
    # -------------------------

    if decision.action == "NO_TRADE":
        print("\nNO TRADE:")
        print(decision.explain())
        record_no_trade(symbol)
        return 0

    # -------------------------
    # Handle BUY / SELL
    # -------------------------

    ticket = make_mt5_ticket(
        instrument=symbol,
        side=decision.action.lower(),
        units=decision.units,
        price_snapshot=decision.price,
        stop_loss=decision.stop_loss,
        take_profit=decision.take_profit,
        reason=decision.reason,
    )

    MT5TicketExporter("out/mt5_trade_tickets.csv").export(ticket)

    print("\n" + "=" * 72)
    print("MT5 TRADE TICKET CREATED (ENGINE-DRIVEN)")
    print("=" * 72)
    print(f"Symbol:        {ticket.symbol}")
    print(f"Side:          {ticket.side}")
    print(f"Volume (lots): {ticket.volume_lots}")
    print(f"Price:         {ticket.price_snapshot:.6f}")
    print(f"Stop Loss:     {ticket.stop_loss}")
    print(f"Take Profit:   {ticket.take_profit}")
    print(f"Reason:        {ticket.reason}")
    print("=" * 72)
    print("Saved to: out/mt5_trade_tickets.csv\n")

    print("MT5 Execution:")
    print("1) Open MT5 → select symbol")
    print("2) New Order → Market")
    print("3) Enter volume, SL, TP")
    print("4) Execute trade")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())