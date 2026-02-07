"""
P&L Ledger (Append-Only) – Extended Transaction Schema
REA Capital Trading Engine

Writes one immutable JSON line per closed trade.

Now supports transaction summary fields:
- trade_type (SPOT/FWD/SWAP/OPTION/CRYPTO/EQUITY/etc)
- currency (PnL currency / settlement currency)
- amount (notional amount in currency)
- fx_rate (rate used for conversion, if any)
- execution_date (when executed)
- value_date (when it settles / value date)
- exchange_rate_text (optional human-friendly string e.g. "EUR/USD 1.0925")

Backward compatible: reporter tolerates older schema lines.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional


DEFAULT_LEDGER_PATH = os.getenv(
    "REA_PNL_LEDGER_PATH",
    "reporting_store/pnl_ledger.jsonl"
)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_date_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@dataclass(frozen=True)
class PnlEvent:
    # Core
    ts_utc: str
    engine_run_id: str
    mode: str
    symbol: str
    side: str

    # Transaction summary (requested)
    trade_type: str               # SPOT / FWD / SWAP / OPTION / CRYPTO / EQUITY
    execution_date: str           # YYYY-MM-DD
    value_date: str               # YYYY-MM-DD
    currency: str                 # settlement / pnl currency
    amount: float                 # notional amount in currency
    fx_rate: float                # conversion rate used (1.0 if none)
    exchange_rate_text: str = ""  # e.g. "EUR/USD 1.0925"

    # Pricing + results
    qty: float = 0.0
    entry_px: float = 0.0
    exit_px: float = 0.0
    fees: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0

    # Optional tags
    tag: str = ""
    trade_id: str = ""


def append_pnl_event(
    *,
    mode: str,
    symbol: str,
    side: str,
    qty: float,
    entry_px: float,
    exit_px: float,
    fees: float,

    # New transaction summary fields
    trade_type: str = "SPOT",
    execution_date: Optional[str] = None,
    value_date: Optional[str] = None,
    currency: str = "USD",
    amount: Optional[float] = None,
    fx_rate: float = 1.0,
    exchange_rate_text: str = "",

    # Optional
    tag: str = "",
    trade_id: str = "",
    ledger_path: str = DEFAULT_LEDGER_PATH,
    engine_run_id: Optional[str] = None,
) -> PnlEvent:
    """
    Appends a PnlEvent to JSONL ledger.

    Notes:
    - amount defaults to abs(entry_px * qty) if not provided (notional estimate).
    - execution_date/value_date default to today's UTC date if not provided.
    - pnl is stored in `currency` terms; fx_rate is informational unless you choose otherwise.
    """

    if engine_run_id is None:
        engine_run_id = os.getenv("ENGINE_RUN_ID", "NO_ENGINE_RUN_ID")

    if execution_date is None:
        execution_date = _utc_date_iso()
    if value_date is None:
        value_date = _utc_date_iso()

    # Basic P&L calc (can be refined per asset class later)
    if side.upper() in ("BUY", "LONG"):
        gross = (exit_px - entry_px) * qty
    else:
        gross = (entry_px - exit_px) * qty

    net = gross - float(fees)

    if amount is None:
        amount = max(abs(entry_px * qty), 0.0)

    notional = max(abs(entry_px * qty), 1e-9)
    pnl_pct = net / notional

    evt = PnlEvent(
        ts_utc=_utc_iso(),
        engine_run_id=str(engine_run_id),
        mode=str(mode).upper(),
        symbol=str(symbol).upper(),
        side=str(side).upper(),

        trade_type=str(trade_type).upper(),
        execution_date=str(execution_date),
        value_date=str(value_date),
        currency=str(currency).upper(),
        amount=float(amount),
        fx_rate=float(fx_rate),
        exchange_rate_text=str(exchange_rate_text),

        qty=float(qty),
        entry_px=float(entry_px),
        exit_px=float(exit_px),
        fees=float(fees),
        pnl=float(net),
        pnl_pct=float(pnl_pct),

        tag=str(tag),
        trade_id=str(trade_id),
    )

    os.makedirs(os.path.dirname(ledger_path) or ".", exist_ok=True)
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(evt), ensure_ascii=False) + "\n")

    return evt
