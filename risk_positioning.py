"""
Task 9.1 — Risk & Position Sizing (DRY-RUN ONLY)

Purpose:
- Compute position sizing and R-metrics from hypothetical signals
- NO trade execution
- NO broker interaction
- Safe to import anywhere

This module is intentionally standalone and side-effect free.
"""

from dataclasses import dataclass
from typing import Optional, Dict
import math


@dataclass
class RiskConfig:
    account_equity: float            # total account size
    risk_per_trade: float            # fraction (e.g. 0.01 = 1%)
    stop_loss_pips: float            # stop distance in pips
    pip_value_per_lot: float          # pip value for 1.0 lot
    max_lot_size: Optional[float] = None  # optional hard cap


@dataclass
class RiskResult:
    risk_amount: float
    lot_size: float
    position_value: float
    r_multiple_per_pip: float
    valid: bool
    reason: str


def compute_position_size(cfg: RiskConfig) -> RiskResult:
    """
    Core risk calculator.

    Returns:
        RiskResult with computed lot size and diagnostics.
    """

    # --- validation ---
    if cfg.account_equity <= 0:
        return _fail("account_equity must be > 0")

    if not (0 < cfg.risk_per_trade < 1):
        return _fail("risk_per_trade must be between 0 and 1")

    if cfg.stop_loss_pips <= 0:
        return _fail("stop_loss_pips must be > 0")

    if cfg.pip_value_per_lot <= 0:
        return _fail("pip_value_per_lot must be > 0")

    # --- calculations ---
    risk_amount = cfg.account_equity * cfg.risk_per_trade
    loss_per_lot = cfg.stop_loss_pips * cfg.pip_value_per_lot

    if loss_per_lot <= 0:
        return _fail("invalid loss_per_lot")

    raw_lot_size = risk_amount / loss_per_lot

    if not math.isfinite(raw_lot_size) or raw_lot_size <= 0:
        return _fail("non-finite or non-positive lot size")

    lot_size = raw_lot_size

    # apply cap if provided
    if cfg.max_lot_size is not None:
        lot_size = min(lot_size, cfg.max_lot_size)

    position_value = lot_size * cfg.pip_value_per_lot * cfg.stop_loss_pips
    r_multiple_per_pip = risk_amount / cfg.stop_loss_pips

    return RiskResult(
        risk_amount=round(risk_amount, 2),
        lot_size=round(lot_size, 4),
        position_value=round(position_value, 2),
        r_multiple_per_pip=round(r_multiple_per_pip, 6),
        valid=True,
        reason="ok",
    )


def summarize_risk(cfg: RiskConfig) -> Dict[str, float]:
    """
    Lightweight helper for logging / counters.
    """
    result = compute_position_size(cfg)
    return {
        "valid": result.valid,
        "risk_amount": result.risk_amount,
        "lot_size": result.lot_size,
        "position_value": result.position_value,
        "r_multiple_per_pip": result.r_multiple_per_pip,
    }


def _fail(reason: str) -> RiskResult:
    return RiskResult(
        risk_amount=0.0,
        lot_size=0.0,
        position_value=0.0,
        r_multiple_per_pip=0.0,
        valid=False,
        reason=reason,
    )


# --- self-test (safe, optional) ---
if __name__ == "__main__":
    cfg = RiskConfig(
        account_equity=10_000,
        risk_per_trade=0.01,
        stop_loss_pips=20,
        pip_value_per_lot=10,
        max_lot_size=5.0,
    )

    res = compute_position_size(cfg)
    print("=== RISK POSITIONING DRY-RUN ===")
    print(res)