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

from backend.data.coinbase_historical_downloader import (
    Candle,
    load_runtime_asset,
    compute_vwap_from_candles,
)
from backend.scanner.unified_market_scanner import UnifiedMarketScanner

from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.market_regime_engine import MarketRegimeEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.opportunity_pressure_map_engine import (
    OpportunityPressureMapEngine,
)
from backend.intelligence.liquidity_sweep_detector import LiquiditySweepDetector
from backend.intelligence.opportunity_momentum_window_engine import (
    OpportunityMomentumWindowEngine,
)
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer


SCAN_INTERVAL_SECONDS = 20
SEED_COUNT = 20
MAX_OPEN_POSITIONS = 5

STARTING_CAPITAL = 200.0

TAKE_PROFIT_PCT = 0.012
STOP_LOSS_PCT = 0.009
MAX_HOLD_CYCLES = 20

MIN_TRADE_SCORE = 0.52
MIN_PRESSURE_SCORE = 0.60
MIN_PRESSURE_ACCEL = 0.10

SUMMARY_PATH = PROJECT_ROOT / "artifacts/css_extended_paper_test_summary.json"
SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

scanner = UnifiedMarketScanner()

feature_builder = FeatureBuilder()
regime_engine = MarketRegimeEngine()
pressure_engine = OpportunityPressureEngine()
accel_engine = PressureAccelerationEngine()
pressure_map_engine = OpportunityPressureMapEngine()
sweep_engine = LiquiditySweepDetector()
momentum_engine = OpportunityMomentumWindowEngine()

ai = AIOpportunityScorer()
optimizer = QuantSignalOptimizer()

cycle_no = 0
open_positions: Dict[str, Dict[str, Any]] = {}
closed_trades: List[Dict[str, Any]] = []
realized_pnl = 0.0


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _save_summary() -> None:
    wins = sum(1 for t in closed_trades if t["pnl"] > 0)
    losses = sum(1 for t in closed_trades if t["pnl"] <= 0)

    summary = {
        "timestamp_utc": now_utc(),
        "cycle_no": cycle_no,
        "open_positions": len(open_positions),
        "closed_trades": len(closed_trades),
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / len(closed_trades)) if closed_trades else 0.0,
        "realized_pnl_usd": realized_pnl,
        "starting_capital_usd": STARTING_CAPITAL,
        "estimated_equity_usd": STARTING_CAPITAL + realized_pnl,
        "config": {
            "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
            "seed_count": SEED_COUNT,
            "max_open_positions": MAX_OPEN_POSITIONS,
            "take_profit_pct": TAKE_PROFIT_PCT,
            "stop_loss_pct": STOP_LOSS_PCT,
            "max_hold_cycles": MAX_HOLD_CYCLES,
            "min_trade_score": MIN_TRADE_SCORE,
            "min_pressure_score": MIN_PRESSURE_SCORE,
            "min_pressure_accel": MIN_PRESSURE_ACCEL,
            "css_min_signal_strength_env": os.getenv("CSS_MIN_SIGNAL_STRENGTH", ""),
        },
    }

    with SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def print_status() -> None:
    print("\n==============================")
    print("CSS EXTENDED PAPER TEST")
    print("==============================")
    print("Cycle:", cycle_no)
    print("Open positions:", len(open_positions))
    print("Closed trades:", len(closed_trades))
    print("PnL:", round(realized_pnl, 4))
    print("==============================\n")


def discover_symbols() -> List[str]:
    results = scanner.scan()

    symbols: List[str] = []
    seen = set()

    for r in results:
        if r.get("venue") != "COINBASE":
            continue

        s = r.get("symbol")
        if not s or s in seen:
            continue

        symbols.append(s)
        seen.add(s)

    return symbols[:SEED_COUNT]


def candle_to_dict(c: Candle) -> Dict[str, float]:
    return {
        "ts": float(c.ts),
        "open": float(c.open),
        "high": float(c.high),
        "low": float(c.low),
        "close": float(c.close),
        "volume": float(c.volume),
    }


def fetch_assets(symbols: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for s in symbols:
        try:
            payload = load_runtime_asset(s)
            candles_raw: List[Candle] = payload.get("candles", [])

            if len(candles_raw) < 10:
                continue

            raw_price = payload.get("price")
            if raw_price is None:
                price = float(candles_raw[-1].close)
            else:
                price = float(raw_price)

            if price <= 0:
                continue

            vwap = compute_vwap_from_candles(candles_raw)
            if vwap is None or vwap <= 0:
                continue

            candles = [candle_to_dict(c) for c in candles_raw]

            row = dict(payload)
            row["symbol"] = s
            row["price"] = price
            row["vwap"] = float(vwap)
            row["candles"] = candles

            rows.append(row)

        except Exception as e:
            print(f"[FETCH ERROR] {s}: {e}")
            continue

    return rows


def build_signals(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = feature_builder.enrich_rows(rows, {})
    rows = regime_engine.detect(rows)

    # Current OpportunityPressureEngine interface in repo uses scan_market()
    rows = pressure_engine.scan_market(rows)

    rows = accel_engine.enrich(rows)
    rows = pressure_map_engine.enrich(rows)
    rows = sweep_engine.enrich(rows)
    rows = momentum_engine.enrich(rows)

    rows = ai.rank_opportunities(rows)
    rows = optimizer.optimize(rows)

    return rows


def allow_trade(row: Dict[str, Any]) -> bool:
    decision = row.get("decision")
    trade_score = _safe_float(row.get("trade_score"))
    pressure_score = _safe_float(row.get("pressure_score"))
    pressure_accel = _safe_float(row.get("pressure_acceleration"))

    if decision != "TRADE":
        return False

    if trade_score < MIN_TRADE_SCORE:
        return False

    if pressure_score < MIN_PRESSURE_SCORE:
        return False

    if pressure_accel < MIN_PRESSURE_ACCEL:
        return False

    return True


def open_new_positions(rows: List[Dict[str, Any]]) -> None:
    global open_positions

    available = MAX_OPEN_POSITIONS - len(open_positions)
    if available <= 0:
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
            "cycles": 0,
        }

        print("OPEN:", symbol)

        if len(open_positions) >= MAX_OPEN_POSITIONS:
            break


def manage_positions(rows_map: Dict[str, Dict[str, Any]]) -> None:
    global realized_pnl

    to_close = []

    for symbol, pos in open_positions.items():
        row = rows_map.get(symbol)
        if not row:
            continue

        price = float(row["price"])
        entry = pos["entry_price"]
        pnl_pct = (price - entry) / entry

        pos["cycles"] += 1

        if pnl_pct >= TAKE_PROFIT_PCT:
            to_close.append((symbol, price, "TP"))
        elif pnl_pct <= -STOP_LOSS_PCT:
            to_close.append((symbol, price, "SL"))
        elif pos["cycles"] >= MAX_HOLD_CYCLES:
            to_close.append((symbol, price, "TIME"))

    for symbol, exit_price, reason in to_close:
        pos = open_positions.pop(symbol)

        entry_price = pos["entry_price"]
        size = pos["size_usd"]
        qty = size / entry_price

        pnl = (exit_price - entry_price) * qty
        realized_pnl += pnl

        closed_trades.append(
            {
                "symbol": symbol,
                "pnl": pnl,
                "reason": reason,
            }
        )

        print("CLOSE:", symbol, "PNL:", round(pnl, 4))


print("CSS EXTENDED PAPER TEST STARTED")

while True:
    cycle_no += 1

    try:
        symbols = discover_symbols()
        rows = fetch_assets(symbols)

        print("VALID ASSETS AFTER FILTER:", len(rows))

        rows_map = {r["symbol"]: r for r in rows}
        manage_positions(rows_map)

        if rows:
            signals = build_signals(rows)

            print("\n--- TOP SIGNALS ---")
            for r in signals[:10]:
                print(
                    r.get("symbol"),
                    "decision=", r.get("decision"),
                    "trade_score=", round(_safe_float(r.get("trade_score")), 4),
                    "pressure=", round(_safe_float(r.get("pressure_score")), 4),
                    "accel=", round(_safe_float(r.get("pressure_acceleration")), 4),
                )
            print("-------------------\n")

            open_new_positions(signals)

        _save_summary()
        print_status()

        time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("CSS extended paper test stopped.")
        break

    except Exception as e:
        print("ENGINE ERROR:", e)
        time.sleep(10)