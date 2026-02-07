"""
Trade Ticket – REA Capital Trading Engine (V1)

Adds:
- Unique Transaction Reference Number (UTRN) per trade
- Duplicate trade warning (non-blocking) with override flag
- Canonical ticket fields needed for downstream logging + audit

Notes:
- Duplicate detection is WARN by default; execution can proceed.
- UI button later maps to override_duplicate=True.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from engine.security.duplicate_trade_guard import check_duplicate_trade, DuplicateCheckResult


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_date_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def generate_utrn(prefix: str = "UTRN") -> str:
    """
    Generates a unique transaction reference number.
    Example: UTRN-20260207-1F3A9C2B
    """
    d = datetime.now(timezone.utc).strftime("%Y%m%d")
    rnd = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{d}-{rnd}"


def _ledger_path_for_mode(mode: str) -> str:
    """
    Separate physical ledger files (Option A).
    """
    mode_u = str(mode or "TEST").upper().strip()
    if mode_u == "LIVE":
        return os.getenv("REA_PNL_LEDGER_LIVE_PATH", "reporting_store/pnl_ledger_live.jsonl")
    return os.getenv("REA_PNL_LEDGER_TEST_PATH", "reporting_store/pnl_ledger_test.jsonl")


@dataclass
class TradeTicket:
    # Identity / audit
    utrn: str = field(default_factory=generate_utrn)
    created_utc: str = field(default_factory=_utc_now_iso)
    engine_run_id: str = field(default_factory=lambda: os.getenv("ENGINE_RUN_ID", "NO_ENGINE_RUN_ID"))

    # Trade intent
    mode: str = "TEST"             # TEST or LIVE
    trade_type: str = "SPOT"       # SPOT / FWD / SWAP / OPTION / CRYPTO / EQUITY
    symbol: str = ""
    side: str = ""                # BUY/SELL (or LONG/SHORT)
    currency: str = "USD"
    amount: float = 0.0           # notional in currency
    qty: float = 0.0              # units (optional; may be derived)
    entry_px: float = 0.0         # optional
    requested_px: float = 0.0     # optional

    # Dates
    execution_date: str = field(default_factory=_utc_date_iso)
    value_date: str = field(default_factory=_utc_date_iso)

    # FX info (optional)
    fx_rate: float = 1.0
    exchange_rate_text: str = ""

    # Duplicate warning controls
    override_duplicate: bool = False
    duplicate_check: Optional[Dict[str, Any]] = None  # stored for audit/log display

    # Free-form
    tag: str = ""
    note: str = ""

    def ledger_path(self) -> str:
        return _ledger_path_for_mode(self.mode)

    def run_duplicate_check(self, lookback_days: int = 30, price_tol: float = 1e-6) -> DuplicateCheckResult:
        """
        Runs duplicate detection against the appropriate ledger for this mode.
        Stores results in ticket. Does not block execution.
        """
        res = check_duplicate_trade(
            ledger_path=self.ledger_path(),
            symbol=self.symbol,
            side=self.side,
            trade_type=self.trade_type,
            currency=self.currency,
            amount=self.amount,
            execution_date=self.execution_date,
            entry_px=self.entry_px if self.entry_px > 0 else None,
            price_tol=price_tol,
            lookback_days=lookback_days,
            override_duplicate=self.override_duplicate,
        )
        self.duplicate_check = {
            "decision": res.decision,
            "reason": res.reason,
            "matches": res.matches,
            "sample_match": res.sample_match,
        }
        return res

    def to_dict(self) -> Dict[str, Any]:
        return {
            "utrn": self.utrn,
            "created_utc": self.created_utc,
            "engine_run_id": self.engine_run_id,

            "mode": self.mode,
            "trade_type": self.trade_type,
            "symbol": self.symbol,
            "side": self.side,
            "currency": self.currency,
            "amount": float(self.amount),
            "qty": float(self.qty),
            "entry_px": float(self.entry_px),
            "requested_px": float(self.requested_px),

            "execution_date": self.execution_date,
            "value_date": self.value_date,

            "fx_rate": float(self.fx_rate),
            "exchange_rate_text": self.exchange_rate_text,

            "override_duplicate": bool(self.override_duplicate),
            "duplicate_check": self.duplicate_check,

            "tag": self.tag,
            "note": self.note,
        }
