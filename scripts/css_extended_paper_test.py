from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.scanner.unified_market_scanner import UnifiedMarketScanner

from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.market_regime_engine import MarketRegimeEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.liquidity_sweep_detector import LiquiditySweepDetector
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer

from backend.strategies.vwap_mean_reversion import compute_vwap_from_candles


# ---------------------------------------------------------
# CONFIG (Research Mode)
# ---------------------------------------------------------

SCAN_INTERVAL_SECONDS = int(os.getenv("CSS_TEST_SCAN_INTERVAL_SECONDS", "30"))

# Increase sampling so we can test strategy faster
SEED_COUNT = int(os.getenv("CSS_TEST_SEED_COUNT", "20"))
MAX_OPEN_POSITIONS = int(os.getenv("CSS_TEST_MAX_OPEN_POSITIONS", "5"))

STARTING_CAPITAL = float(os.getenv("CSS_TEST_STARTING_CAPITAL", "200.0"))

# More realistic intraday targets
TAKE_PROFIT_PCT = float(os.getenv("CSS_TEST_TP_PCT", "0.012"))
STOP_LOSS_PCT = float(os.getenv("CSS_TEST_SL_PCT", "0.009"))

# Longer holding window
MAX_HOLD_CYCLES = int(os.getenv("CSS_TEST_MAX_HOLD_CYCLES", "20"))

TRADE_LOG_PATH = PROJECT_ROOT / "artifacts" / "css_extended_paper_test_trades.jsonl"
SUMMARY_PATH = PROJECT_ROOT / "artifacts" / "css_extended_paper_test_summary.json"


# ---------------------------------------------------------
# ENGINES
# ---------------------------------------------------------

scanner = UnifiedMarketScanner()
feature_builder = FeatureBuilder()
regime_engine = MarketRegimeEngine()
pressure_engine = OpportunityPressureEngine()
accel_engine = PressureAccelerationEngine()
sweep_engine = LiquiditySweepDetector()
ai = AIOpportunityScorer()
optimizer = QuantSignalOptimizer()


# ---------------------------------------------------------
# STATE
# ---------------------------------------------------------

open_positions: Dict[str, Dict[str, Any]] = {}
closed_trades: List[Dict[str, Any]] = []

cycle_no = 0
realized_pnl = 0.0

SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _write_jsonl(path: Path, row: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------
# SUMMARY REPORT
# ---------------------------------------------------------

def _save_summary() -> None:
    wins = sum(1 for t in closed_trades if _safe_float(t.get("pnl_usd")) > 0)
    losses = sum(1 for t in closed_trades if _safe_float(t.get("pnl_usd")) < 0)

    total = len(closed_trades)
    win_rate = (wins / total) if total > 0 else 0.0

    gross_profit = sum(_safe_float(t.get("pnl_usd")) for t in closed_trades if _safe_float(t.get("pnl_usd")) > 0)
    gross_loss = abs(sum(_safe_float(t.get("pnl_usd")) for t in closed_trades if _safe_float(t.get("pnl_usd")) < 0))

    summary = {
        "timestamp_utc": now_utc(),
        "cycle_no": cycle_no,
        "open_positions": len(open_positions),
        "closed_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4),
        "realized_pnl_usd": round(realized_pnl, 2),
        "gross_profit_usd": round(gross_profit, 2),
        "gross_loss_usd": round(gross_loss, 2),
        "starting_capital_usd": STARTING_CAPITAL,
        "estimated_equity_usd": round(STARTING_CAPITAL + realized_pnl, 2),
    }

    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")


# ---------------------------------------------------------
# POSITION MANAGEMENT
# ---------------------------------------------------------

def mark_to_market_and_close(current_rows: Dict[str, Dict[str, Any]]) -> None:

    global realized_pnl

    to_close: List[str] = []

    for symbol, pos in open_positions.items():

        row = current_rows.get(symbol)

        if row is None:
            pos["cycles_held"] += 1

            if pos["cycles_held"] >= MAX_HOLD_CYCLES:
                pos["exit_reason"] = "MAX_HOLD_CYCLES"
                to_close.append(symbol)

            continue

        current_price = _safe_float(row.get("price"))
        entry_price = _safe_float(pos.get("entry_price"))

        pnl_pct = (current_price - entry_price) / entry_price

        pos["last_price"] = current_price
        pos["cycles_held"] += 1

        if pnl_pct >= TAKE_PROFIT_PCT:
            pos["exit_reason"] = "TAKE_PROFIT"
            to_close.append(symbol)

        elif pnl_pct <= -STOP_LOSS_PCT:
            pos["exit_reason"] = "STOP_LOSS"
            to_close.append(symbol)

        elif pos["cycles_held"] >= MAX_HOLD_CYCLES:
            pos["exit_reason"] = "MAX_HOLD_CYCLES"
            to_close.append(symbol)

    for symbol in to_close:

        pos = open_positions.pop(symbol)

        exit_price = _safe_float(pos.get("last_price", pos.get("entry_price")))
        entry_price = _safe_float(pos.get("entry_price"))

        size_usd = _safe_float(pos.get("size_usd"))

        qty = size_usd / entry_price
        pnl_usd = (exit_price - entry_price) * qty

        realized_pnl += pnl_usd

        trade = {
            "event": "CLOSE",
            "timestamp_utc": now_utc(),
            "symbol": symbol,
            "entry_price": round(entry_price, 8),
            "exit_price": round(exit_price, 8),
            "size_usd": round(size_usd, 2),
            "qty": round(qty, 8),
            "pnl_usd": round(pnl_usd, 2),
            "cycles_held": pos.get("cycles_held", 0),
            "exit_reason": pos.get("exit_reason", "UNKNOWN"),
            "entry_cycle": pos.get("entry_cycle"),
            "exit_cycle": cycle_no,
        }

        closed_trades.append(trade)

        _write_jsonl(TRADE_LOG_PATH, trade)


# ---------------------------------------------------------
# ENGINE START
# ---------------------------------------------------------

print("[CSS] Starting extended paper test...", flush=True)

while True:

    cycle_no += 1

    try:

        symbols = scanner.scan()
        rows = []

        for r in symbols[:SEED_COUNT]:
            payload = load_runtime_asset(r["symbol"])

            if payload:
                rows.append(payload)

        current_map = {str(r.get("symbol", "")): r for r in rows}

        mark_to_market_and_close(current_map)

        _save_summary()

        print(
            f"Cycle {cycle_no} | "
            f"Open {len(open_positions)} | "
            f"Closed {len(closed_trades)} | "
            f"PnL ${realized_pnl:.2f}"
        )

        time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:

        _save_summary()
        print("CSS extended paper test stopped.")
        break

    except Exception as exc:

        print(f"[CSS TEST ERROR] {exc}")
        time.sleep(SCAN_INTERVAL_SECONDS)