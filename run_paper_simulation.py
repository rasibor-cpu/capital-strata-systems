from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

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
    if fill_px is not None:
        return float(fill_px)
    return entry_px * (1.0 + (bump_bps / 10000.0))


def _print_banner() -> None:
    print("\n=== PAPER SIMULATION (V1) ===")
    print("Auto-ledger: ON  |  Duplicate warn: ON  |  UTRN: ON")
    print("Ledgers: TEST -> pnl_ledger_test.jsonl, LIVE -> pnl_ledger_live.jsonl\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["TEST", "LIVE"], default=os.getenv("REA_ENGINE_MODE", "TEST").upper())
    p.add_argument("--broker", default=os.getenv("REA_PAPER_BROKER", "alpaca"))
    p.add_argument("--symbol", default="EURUSD")
    p.add_argument("--side", default="BUY", choices=["BUY", "SELL", "LONG", "SHORT"])
    p.add_argument("--trade-type", default="SPOT")
    p.add_argument("--currency", default="USD")
    p.add_argument("--amount", default="5000.0")
    p.add_argument("--entry", default=None)
    p.add_argument("--fill", default=None)
    p.add_argument("--bump-bps", default="50")
    p.add_argument("--fees", default="1.25")
    p.add_argument("--execution-date", default=None)
    p.add_argument("--value-date", default=None)
    p.add_argument("--override-duplicate", action="store_true")
    p.add_argument("--repeat", default="1")
    args = p.parse_args()

    _print_banner()

    try:
        amount = float(args.amount)
        fees = float(args.fees)
        bump_bps = float(args.bump_bps)
        repeat = int(args.repeat)
    except Exception:
        print("FATAL: invalid numeric argument.")
        return 2

    mode = str(args.mode).upper().strip()
    broker_label = str(args.broker).lower().strip()
    symbol = str(args.symbol).upper().strip()
    side = str(args.side).upper().strip()
    trade_type = str(args.trade_type).upper().strip()
    currency = str(args.currency).upper().strip()

    entry_px = _float_or_none(args.entry)
    if entry_px is None:
        entry_px = _pick_default_entry(symbol)

    fill_px = _float_or_none(args.fill)
    exit_px = _compute_fill(entry_px, fill_px, bump_bps)

    broker = PaperBroker()

    # Debug identity (to ensure no shadowing)
    print(f"PaperBroker class: {PaperBroker} | module={PaperBroker.__module__}")
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

        result = broker.execute_and_close(ticket, fill_price=float(exit_px), fees=float(fees))

        if result is None:
            raise RuntimeError("FATAL: PaperBroker.execute_and_close returned None. paper_broker.py must return PaperFillResult.")

        print(f"[{i}/{repeat}] OK | UTRN={result.utrn} | exit_px={result.exit_px:.6f} | pnl={result.pnl:.2f} | ts={result.timestamp_utc}")

    print("\nNext checks:")
    print(f"  python -m tools.pnl_check --period today --mode {mode} --details\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
