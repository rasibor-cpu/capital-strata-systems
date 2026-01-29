
from __future__ import annotations

"""
MT5 Manual Runner v2 (CSV-driven, registry-wired)

This version is wired to:
- instrument_registry.py for:
  * available instruments list
  * pip size conversion
  * epsilon defaults aligned with Sanity Probe

Flow:
- List instruments from registry
- User selects instrument
- User provides MT5-exported CSV path (bars)
- Compute rolling mean (VWAP proxy) from CSV
- Use last close as price
- Apply epsilon gate (pips -> price via registry)
- Export MT5 trade ticket to out/mt5_trade_tickets.csv

No broker API.
No KYC.
Personal module baseline.
"""

import json
import os
from typing import Any, Dict, Optional

import instrument_registry as ir
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


def vwap_distance_signal(price: float, mean_level: float, epsilon_price: float) -> str:
    """
    Returns: 'buy', 'sell', or ''
    """
    if abs(price - mean_level) < epsilon_price:
        return ""
    return "buy" if price < mean_level else "sell"


def compute_sl_tp(
    side: str,
    price: float,
    symbol: str,
    require_sl_tp: bool,
    sl_pips: int,
    tp_pips: int
) -> tuple[Optional[float], Optional[float]]:
    if not require_sl_tp:
        return None, None

    sl_px = ir.pip_to_price(symbol, float(sl_pips))
    tp_px = ir.pip_to_price(symbol, float(tp_pips))

    if side == "buy":
        sl = price - sl_px
        tp = price + tp_px
    else:
        sl = price + sl_px
        tp = price - tp_px
    return sl, tp


# -------------------------
# Main
# -------------------------

def main() -> int:
    cfg = load_config("config.json")

    # --- Locked defaults (registry) ---
    lookback = int(cfg["strategy"].get("lookback_points", ir.DEFAULT_LOOKBACK_BARS))
    mode = (cfg["strategy"].get("accuracy_mode", ir.DEFAULT_ACCURACY_MODE) or "").strip().lower()

    # Instruments: show registry list (user-extensible)
    instruments = ir.list_instruments()
    if not instruments:
        print("No instruments in instrument_registry.py")
        return 0

    print("\nRegistry instruments (enabled):")
    for i, sym in enumerate(instruments, start=1):
        print(f" {i}) {sym}")

    sel = input("\nSelect instrument number (e.g., 1): ").strip()
    if not sel.isdigit():
        print("Invalid selection.")
        return 1

    idx = int(sel) - 1
    if idx < 0 or idx >= len(instruments):
        print("Selection out of range.")
        return 1

    symbol = instruments[idx]

    # Derive epsilon in PRICE units from registry (pips -> price)
    eps_price = ir.epsilon_price(symbol, mode=mode)

    print("\nExport bars from MT5 for the SAME symbol/timeframe (M5 recommended).")
    print(r"Example: C:\Users\rasib\Downloads\EURUSD_M5.csv")
    csv_path = input(f"\nEnter MT5 CSV path for {symbol}: ").strip().strip('"')

    try:
        res = compute_rolling_mean_from_mt5_csv(csv_path, lookback=lookback)
    except Exception as e:
        print(f"CSV processing failed: {e}")
        return 1

    price = float(res.last_close)
    mean_level = float(res.mean_level)

    side = vwap_distance_signal(price, mean_level, eps_price)
    if not side:
        print("\nNo signal generated (inside epsilon gate).")
        print(f"symbol={symbol} price={price:.6f} mean={mean_level:.6f} eps_price={eps_price:.6f} bars_used={res.bars_used}")
        return 0

    # Units -> lots conversion happens inside exporter (units come from config)
    units = int(cfg["risk"]["default_units"])
    units = min(units, int(cfg["risk"]["max_units"]))

    sl, tp = compute_sl_tp(
        side=side,
        price=price,
        symbol=symbol,
        require_sl_tp=bool(cfg["risk"].get("require_sl_tp", False)),
        sl_pips=int(cfg["risk"]["default_sl_pips"]),
        tp_pips=int(cfg["risk"]["default_tp_pips"]),
    )

    ticket = make_mt5_ticket(
        instrument=symbol,   # exporter converts EURUSD -> EURUSD, no underscores
        side=side,
        units=units,
        price_snapshot=price,
        stop_loss=sl,
        take_profit=tp,
        reason=f"MT5 v2 registry-wired | rolling-mean | mode={mode} | eps_pips={ir.EPSILON_PIPS.get(mode)} | lookback={lookback}"
    )

    exporter = MT5TicketExporter("out/mt5_trade_tickets.csv")
    exporter.export(ticket)

    print("\n" + "=" * 72)
    print("MT5 TRADE TICKET CREATED (manual execution)")
    print("=" * 72)
    print(f"Symbol:        {ticket.symbol}")
    print(f"Side:          {ticket.side}")
    print(f"Volume (lots): {ticket.volume_lots}")
    print(f"Price (close): {ticket.price_snapshot:.6f}")
    print(f"Mean level:    {mean_level:.6f}")
    print(f"Epsilon (px):  {eps_price:.6f}  (mode={mode})")
    print(f"Stop Loss:     {ticket.stop_loss if ticket.stop_loss is not None else 'NONE'}")
    print(f"Take Profit:   {ticket.take_profit if ticket.take_profit is not None else 'NONE'}")
    print("=" * 72)
    print("Saved to: out/mt5_trade_tickets.csv\n")

    print("MT5 Steps:")
    print("1) Open MT5 → select the same symbol")
    print("2) New Order → set Volume to the ticket lots")
    print("3) Market Execution → BUY or SELL")
    print("4) Optional: set SL/TP to the ticket levels")
    print("5) Place trade\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())