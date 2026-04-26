# ===== CSS DASHBOARD V2 (FULL RECOVERY BUILD) =====
# PCNRASS COMPLIANT — NO REGRESSION — FULL INTEGRATION

from __future__ import annotations
import sys, time, random, json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ===== EXISTING SYSTEM MODULES (UNCHANGED) =====
from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.execution.position_manager import PositionManager

# ===== REAL PNL ENGINE (FIXED PATH) =====
from backend.app.accounting.pnl_engine import (
    Position,
    InstrumentSpec,
    ExecutionCost,
    compute_portfolio_snapshot,
)

# ===== UNIFIED BROKER =====
from backend.app.brokers.broker_bootstrap import initialize_broker

# ===== GLOBAL STATE =====
CSS_POSITIONS = []
CSS_CLOSED = []
CSS_STARTING_EQUITY = 100000.0

BROKER_ADAPTER = None
def route_execution(asset_class, symbol, signal_score, eff):
    global BROKER_ADAPTER

    entry_price = eff

    # ===== REAL BROKER EXECUTION =====
    if BROKER_ADAPTER is not None:
        try:
            result = BROKER_ADAPTER.place_order(
                symbol=symbol,
                units=1,
                side="BUY",
                order_type="MARKET"
            )

            print(f"[BROKER EXECUTED] {symbol}")

            executed = True

        except Exception as e:
            print(f"[BROKER ERROR] {e}")
            executed = False
    else:
        print("[PAPER ROUTE] Using internal execution")
        executed = True

    # ===== REAL POSITION CREATION =====
    if executed:
        pos = Position(
            symbol=symbol,
            side="LONG",
            entry_price=entry_price,
            current_price=entry_price,
            quantity=1.0,
            instrument_spec=InstrumentSpec(
                symbol=symbol,
                asset_class=asset_class,
                multiplier=1.0
            ),
            entry_cost=ExecutionCost(),
            estimated_exit_cost=ExecutionCost(),
        )

        CSS_POSITIONS.append(pos)

    return executed
def compute_real_snapshot():
    return compute_portfolio_snapshot(
        CSS_POSITIONS + CSS_CLOSED,
        CSS_STARTING_EQUITY
    )
snapshot = compute_real_snapshot()

print("\n--- LIVE EXECUTION SUMMARY ---")
print(f"TOTAL PNL: {snapshot.total_net_realized + snapshot.total_net_unrealized:+.4f}")
print(f"REALIZED PNL: {snapshot.total_net_realized:+.4f}")
print(f"UNREALIZED PNL: {snapshot.total_net_unrealized:+.4f}")
print(f"OPEN POSITIONS: {snapshot.open_positions}")
print(f"CLOSED POSITIONS: {snapshot.closed_positions}")