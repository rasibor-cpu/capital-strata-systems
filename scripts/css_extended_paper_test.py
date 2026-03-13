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

# Data
from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.scanner.unified_market_scanner import UnifiedMarketScanner

# Intelligence engines
from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.market_regime_engine import MarketRegimeEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.liquidity_sweep_detector import LiquiditySweepDetector
from backend.intelligence.opportunity_momentum_window_engine import OpportunityMomentumWindowEngine
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer

# Strategy
from backend.strategies.vwap_mean_reversion import compute_vwap_from_candles

# Logging
from backend.execution.trade_logger import TradeLogger


# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

SCAN_INTERVAL_SECONDS = int(os.getenv("CSS_TEST_SCAN_INTERVAL_SECONDS", "20"))
SEED_COUNT = int(os.getenv("CSS_TEST_SEED_COUNT", "20"))
MAX_OPEN_POSITIONS = int(os.getenv("CSS_TEST_MAX_OPEN_POSITIONS", "5"))
STARTING_CAPITAL = float(os.getenv("CSS_TEST_STARTING_CAPITAL", "200.0"))

TAKE_PROFIT_PCT = float(os.getenv("CSS_TEST_TP_PCT", "0.012"))
STOP_LOSS_PCT = float(os.getenv("CSS_TEST_SL_PCT", "0.009"))
MAX_HOLD_CYCLES = int(os.getenv("CSS_TEST_MAX_HOLD_CYCLES", "20"))

MIN_TRADE_SCORE = float(os.getenv("CSS_TEST_MIN_TRADE_SCORE", "0.52"))
MIN_PRESSURE_SCORE = float(os.getenv("CSS_TEST_MIN_PRESSURE_SCORE", "0.60"))
MIN_PRESSURE_ACCEL = float(os.getenv("CSS_TEST_MIN_PRESSURE_ACCEL", "0.10"))

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
momentum_engine = OpportunityMomentumWindowEngine()

ai = AIOpportunityScorer()
optimizer = QuantSignalOptimizer()

trade_logger = TradeLogger()


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
        f.write(json.dumps(row) + "\n")


# ---------------------------------------------------------
# DISCOVERY
# ---------------------------------------------------------

def discover_coinbase_symbols() -> List[str]:

    try:
        discovered = scanner.scan()
    except Exception:
        discovered = []

    symbols: List[str] = []
    seen = set()

    for item in discovered:

        venue = str(item.get("venue", "")).upper()
        symbol = str(item.get("symbol", "")).upper()

        if venue != "COINBASE":
            continue

        if symbol in seen:
            continue

        symbols.append(symbol)
        seen.add(symbol)

    return symbols[:SEED_COUNT]


# ---------------------------------------------------------
# FETCH ASSETS
# ---------------------------------------------------------

def fetch_assets(symbols: List[str]) -> List[Dict[str, Any]]:

    rows: List[Dict[str, Any]] = []

    for symbol in symbols:

        try:

            payload = load_runtime_asset(symbol)

            candles = payload.get("candles", [])

            if len(candles) < 10:
                continue

            price = float(payload.get("price", 0))
            if price <= 0:
                continue

            vwap = compute_vwap_from_candles(candles, 20)

            row = dict(payload)

            row["symbol"] = symbol
            row["price"] = price
            row["vwap"] = vwap
            row["candles"] = candles

            rows.append(row)

        except Exception:
            continue

    return rows


# ---------------------------------------------------------
# SIGNAL PIPELINE
# ---------------------------------------------------------

def build_signal_pipeline(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

    features = feature_builder.enrich_rows(rows, {})

    regime_rows = regime_engine.detect(features)

    pressure_rows = pressure_engine.enrich_rows(regime_rows)

    accel_rows = accel_engine.enrich(pressure_rows)

    sweep_rows = sweep_engine.enrich(accel_rows)

    momentum_rows = momentum_engine.enrich(sweep_rows)

    ranked = ai.rank_opportunities(momentum_rows)

    optimized = optimizer.optimize(ranked)

    return optimized


# ---------------------------------------------------------
# TRADE GATE
# ---------------------------------------------------------

def allow_trade(row: Dict[str, Any]) -> bool:

    if row.get("decision") != "TRADE":
        return False

    if _safe_float(row.get("trade_score")) < MIN_TRADE_SCORE:
        return False

    if _safe_float(row.get("pressure_score")) < MIN_PRESSURE_SCORE:
        return False

    if _safe_float(row.get("pressure_acceleration")) < MIN_PRESSURE_ACCEL:
        return False

    return True


# ---------------------------------------------------------
# POSITION OPEN
# ---------------------------------------------------------

def open_new_positions(rows: List[Dict[str, Any]]) -> None:

    global open_positions

    available_slots = MAX_OPEN_POSITIONS - len(open_positions)

    if available_slots <= 0:
        return

    for row in rows:

        if not allow_trade(row):
            continue

        symbol = row["symbol"]

        if symbol in open_positions:
            continue

        entry_price = float(row["price"])

        size_usd = STARTING_CAPITAL / MAX_OPEN_POSITIONS

        open_positions[symbol] = {
            "symbol": symbol,
            "entry_price": entry_price,
            "size_usd": size_usd,
            "cycles_held": 0,
        }

        trade_logger.log_open(
            symbol=symbol,
            entry_price=entry_price,
            quantity=size_usd / entry_price,
            score=row.get("trade_score"),
            signal="BUY",
            regime=row.get("regime"),
            vwap=row.get("vwap"),
            spread_pct=0,
        )

        print(f"OPEN TRADE: {symbol}")

        if len(open_positions) >= MAX_OPEN_POSITIONS:
            break


# ---------------------------------------------------------
# POSITION CLOSE
# ---------------------------------------------------------

def mark_to_market_and_close(current_rows: Dict[str, Dict[str, Any]]):

    global realized_pnl

    to_close = []

    for symbol, pos in open_positions.items():

        row = current_rows.get(symbol)

        if not row:
            continue

        price = float(row.get("price", 0))

        entry = pos["entry_price"]

        pnl_pct = (price - entry) / entry

        pos["cycles_held"] += 1

        if pnl_pct >= TAKE_PROFIT_PCT:
            reason = "TAKE_PROFIT"
            to_close.append((symbol, price, reason))

        elif pnl_pct <= -STOP_LOSS_PCT:
            reason = "STOP_LOSS"
            to_close.append((symbol, price, reason))

        elif pos["cycles_held"] >= MAX_HOLD_CYCLES:
            reason = "MAX_HOLD_CYCLES"
            to_close.append((symbol, price, reason))

    for symbol, exit_price, reason in to_close:

        pos = open_positions.pop(symbol)

        entry_price = pos["entry_price"]

        size_usd = pos["size_usd"]

        qty = size_usd / entry_price

        pnl = (exit_price - entry_price) * qty

        realized_pnl += pnl

        trade_logger.log_close(
            symbol=symbol,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=qty,
            reason=reason,
            hold_minutes=pos["cycles_held"],
        )

        print(f"CLOSE TRADE: {symbol} reason={reason} pnl={pnl:.4f}")


# ---------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------

print("CSS EXTENDED PAPER TEST STARTED")

while True:

    cycle_no += 1

    try:

        symbols = discover_coinbase_symbols()

        rows = fetch_assets(symbols)

        current_map = {r["symbol"]: r for r in rows}

        mark_to_market_and_close(current_map)

        if rows:

            optimized_rows = build_signal_pipeline(rows)

            open_new_positions(optimized_rows)

        time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:

        print("CSS PAPER TEST STOPPED")

        break

    except Exception as e:

        print(f"ENGINE ERROR: {e}")

        time.sleep(SCAN_INTERVAL_SECONDS)