"""
run_paper_simulation.py — REA Capital Trading Engine (V1 Freeze)

Purpose (V1):
- Single, reliable paper-simulation entrypoint that:
  1) Builds a TradeTicket (UTRN)
  2) Runs duplicate warning (non-blocking)
  3) Routes trade close through PaperBroker (auto-ledger logging to TEST/LIVE file)
  4) Prints the UTRN and result

Notes:
- Does NOT require redoing broker API keys.
- V1 uses deterministic fill unless you explicitly supply --fill.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path when running as a script
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trade_ticket import TradeTicket  # noqa: E402
from engine.execution.paper_broker import PaperBroker  # noqa: E402


def _float_or_none(x: Optional[str]) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _pick_default_entry(symbol: str) -> float:
    sym = symbol.upper()
    if sym == "EURUSD":
        return 1.0900
    if sym == "GBPUSD":
        return 1.2700
    return 100.0


def _compute_fill(entry_px: float, fill_px: Optional[float], bump_bps: float) -> float:
    """
    If fill_px is supplied, use it.
    Otherwise compute a small move from entry using bump_bps basis points.
    Example: bump_bps=50 => 0.50% move.
    """
    if fill_px is not None:
        return float(fill_px)
    return entry_px * (1.0 + (bump_bps / 10000.0))


def _print_banner() -> None:
    print("\n=== PAPER SIMULATION (V1) ===")
    print("Auto-ledger: ON  |  Duplicate warn: ON  |  UTRN: ON")
    print("Ledgers: TEST -> pnl_ledger_test.jsonl, LIVE -> pnl_ledger_live.jsonl\n")


def main() -> int:
    p = argparse.ArgumentParser()

    # Mode / broker selection
    p.add_argument(
        "--mode",
        choices=["TEST", "LIVE"],
        default=os.getenv("REA_ENGINE_MODE", "TEST").upper(),
    )
    p.add_argument(
        "--broker",
        default=os.getenv("REA_PAPER_BROKER", "alpaca"),
        help="Paper broker adapter label (alpaca|binance|ibkr|oanda). V1 routes close via central PaperBroker.",
    )

    # Trade fields
    p.add_argument("--symbol", default="EURUSD")
    p.add_argument("--side", default="BUY", choices=["BUY", "SELL", "LONG", "SHORT"])
    p.add_argument("--trade-type", default="SPOT")
    p.add_argument("--currency", default="USD")
    p.add_argument("--amount", default="5000.0", help="Notional amount in currency")
    p.add_argument("--entry", default=None, help="Entry price (float). If omitted, deterministic default used.")
    p.add_argument("--fill", default=None, help="Exit/fill price (float). If omitted, computed from entry + bump.")
    p.add_argument(
        "--bump-bps",
        default="50",
        help="If --fill omitted: move from entry by bump in basis points (default 50 = 0.50 move).",
    )
    p.add_argument("--fees", default="1.25")

    # Dates / override
    p.add_argument("--execution-date", default=None, help="YYYY-MM-DD (UTC). Default: today.")
    p.add_argument("--value-date", default=None, help="YYYY-MM-DD (UTC). Default: today.")
    p.add_argument("--override-duplicate", action="store_true", help="Override duplicate warning (still logs match count).")

    # Repeat
    p.add_argument("--repeat", default="1", help="Number of trades to run (int).")

    args = p.parse_args()

    _print_banner()

    mode = str(args.mode).upper().strip()
    broker_label = str(args.broker).lower().strip()

    symbol = str(args.symbol).upper().strip()
    side = str(args.side).upper().strip()
    trade_type = str(args.trade_type).upper().strip()
    currency = str(args.currency).upper().strip()

    try:
        amount = float(args.amount)
        fees = float(args.fees)
        bump_bps = float(args.bump_bps)
        repeat = int(args.repeat)
    except Exception:
        print("FATAL: invalid numeric argument (amount/fees/bump-bps/repeat).")
        return 2

    entry_px = _float_or_none(args.entry)
    if entry_px is None:
        entry_px = _pick_default_entry(symbol)

    fill_px = _float_or_none(args.fill)
    exit_px = _compute_fill(entry_px, fill_px, bump_bps)

    broker = PaperBroker()

    print(f"Broker label: {broker_label} (adapter intact; V1 uses central PaperBroker close)")
    print(f"Mode: {mode}")
    print(f"Trade: {trade_type} {symbol} {side} amount={amount} {currency}")
    print(f"Entry: {entry_px}  -> Fill/Exit: {exit_px}  Fees: {fees}\n")

    for i in range(1, repeat + 1):
        ticket = TradeTicket(
            mode=mode,
            trade_type=trade_type,
            symbol=symbol,
            side=side,
            currency=currency,
            amount=amount,
            entry_px=float(entry_px),
            requested_px=float(entry_px),
            fx_rate=1.0,
            exchange_rate_text=f"{symbol[:3]}/{symbol[3:]} {entry_px:.4f}" if len(symbol) == 6 else "",
            override_duplicate=bool(args.override_duplicate),
            tag=f"paper_sim:{broker_label}",
            note="run_paper_simulation.py",
        )

        if args.execution_date:
            ticket.execution_date = args.execution_date
        if args.value_date:
            ticket.value_date = args.value_date

        # Early duplicate warning (PaperBroker will also run it; harmless redundancy for visibility)
        dup = ticket.run_duplicate_check()
        if dup.decision == "WARN":
            print(f"WARNING | DUPLICATE_TRADE | {dup.reason}")
            print(f"WARNING | UTRN={ticket.utrn}")
            if ticket.override_duplicate:
                print("INFO    | override_duplicate=True (proceeding)\n")
            else:
                print("INFO    | proceed allowed (warn-only)\n")

        result = broker.execute_and_close(ticket, fill_price=float(exit_px), fees=float(fees))
        print(
            f"[{i}/{repeat}] OK | UTRN={result.utrn} | exit_px={result.exit_px:.6f} | pnl={result.pnl:.2f} | ts={result.timestamp_utc}"
        )

    print("\nNext checks:")
    print(f"  python -m tools.pnl_check --period today --mode {mode} --details")
    print("  python -m tools.pnl_check --period wtd --mode TEST")
    print("  python -m tools.pnl_check --period mtd --mode TEST")
    print("  python -m tools.pnl_check --period ytd --mode TEST\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
