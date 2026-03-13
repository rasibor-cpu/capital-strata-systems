from __future__ import annotations

import json
import sys
import time
import traceback
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
from backend.intelligence.opportunity_pressure_map_engine import OpportunityPressureMapEngine
from backend.intelligence.liquidity_sweep_detector import LiquiditySweepDetector
from backend.intelligence.opportunity_momentum_window_engine import OpportunityMomentumWindowEngine
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer


# ---------------------------------------------------------
# ACCELERATED PAPER-TEST CONFIG
# ---------------------------------------------------------

SCAN_INTERVAL_SECONDS = 12
SEED_COUNT = 40
MAX_OPEN_POSITIONS = 8

STARTING_CAPITAL = 200.0

TAKE_PROFIT_PCT = 0.009
STOP_LOSS_PCT = 0.008
MAX_HOLD_CYCLES = 12

# Relaxed for paper-test discovery
MIN_TRADE_SCORE = 0.24
MIN_PRESSURE_SCORE = 0.20
MIN_PRESSURE_ACCEL = 0.00

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


def infer_direction(price: float, vwap: float) -> str:
    if price < vwap:
        return "LONG"
    return "SHORT"


def enforce_direction(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for r in rows:
        price = _safe_float(r.get("price"))
        vwap = _safe_float(r.get("vwap"))

        if price > 0 and vwap > 0:
            d = infer_direction(price, vwap)
        else:
            d = str(r.get("direction", "LONG")).upper()

        r["direction"] = d
        r["side"] = d
        r["signal_direction"] = d

    return rows


def save_summary() -> None:
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
        },
    }

    with SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


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

        seen.add(s)
        symbols.append(s)

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
            if not vwap or vwap <= 0:
                continue

            candles = [candle_to_dict(c) for c in candles_raw]

            row = dict(payload)
            row["symbol"] = s
            row["price"] = float(price)
            row["vwap"] = float(vwap)
            row["candles"] = candles

            d = infer_direction(float(price), float(vwap))
            row["direction"] = d
            row["side"] = d
            row["signal_direction"] = d

            rows.append(row)

        except Exception as e:
            print("[FETCH ERROR]", s, e)

    return rows


def build_signals(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = enforce_direction(rows)

    rows = feature_builder.enrich_rows(rows, {})
    rows = enforce_direction(rows)

    rows = regime_engine.detect(rows)
    rows = enforce_direction(rows)

    rows = pressure_engine.scan_market(rows)
    rows = enforce_direction(rows)

    rows = accel_engine.enrich(rows)
    rows = enforce_direction(rows)

    rows = pressure_map_engine.enrich(rows)
    rows = enforce_direction(rows)

    rows = sweep_engine.enrich(rows)
    rows = enforce_direction(rows)

    rows = momentum_engine.enrich(rows)
    rows = enforce_direction(rows)

    rows = ai.rank_opportunities(rows)
    rows = enforce_direction(rows)

    rows = optimizer.optimize(rows)
    rows = enforce_direction(rows)

    rows.sort(key=lambda x: _safe_float(x.get("trade_score")), reverse=True)
    return rows


def allow_trade(row: Dict[str, Any]) -> bool:
    decision = str(row.get("decision", "")).upper()
    trade_score = _safe_float(row.get("trade_score"))
    pressure = _safe_float(row.get("pressure_score"))
    accel = _safe_float(row.get("pressure_acceleration"))

    # Primary path
    if decision == "TRADE" and trade_score >= MIN_TRADE_SCORE:
        return True

    # Fallback path for paper-test activation
    if trade_score >= 0.24 and pressure >= 0.20:
        return True

    # Pressure-led reversal path
    if pressure >= 0.30 and accel >= 0.00:
        return True

    return False


def open_positions_if_allowed(rows: List[Dict[str, Any]]) -> None:
    global open_positions

    available = MAX_OPEN_POSITIONS - len(open_positions)
    if available <= 0:
        return

    for r in rows:
        if not allow_trade(r):
            continue

        symbol = r["symbol"]
        if symbol in open_positions:
            continue

        entry = float(r["price"])
        size = STARTING_CAPITAL / MAX_OPEN_POSITIONS

        open_positions[symbol] = {
            "entry": entry,
            "size": size,
            "cycles": 0,
            "direction": r.get("direction", "LONG"),
            "score": _safe_float(r.get("trade_score")),
        }

        print(
            "OPEN:",
            symbol,
            "direction=",
            r.get("direction"),
            "score=",
            round(_safe_float(r.get("trade_score")), 4),
            "pressure=",
            round(_safe_float(r.get("pressure_score")), 4),
            "accel=",
            round(_safe_float(r.get("pressure_acceleration")), 4),
        )

        if len(open_positions) >= MAX_OPEN_POSITIONS:
            break


def manage_positions(rows_map: Dict[str, Dict[str, Any]]) -> None:
    global realized_pnl

    closes = []

    for s, p in open_positions.items():
        r = rows_map.get(s)
        if not r:
            continue

        price = float(r["price"])
        entry = p["entry"]

        pnl_pct = (price - entry) / entry
        p["cycles"] += 1

        if pnl_pct >= TAKE_PROFIT_PCT:
            closes.append((s, price, "TP"))
        elif pnl_pct <= -STOP_LOSS_PCT:
            closes.append((s, price, "SL"))
        elif p["cycles"] >= MAX_HOLD_CYCLES:
            closes.append((s, price, "TIME"))

    for s, price, reason in closes:
        pos = open_positions.pop(s)

        entry = pos["entry"]
        size = pos["size"]
        qty = size / entry

        pnl = (price - entry) * qty
        realized_pnl += pnl

        closed_trades.append(
            {
                "symbol": s,
                "pnl": pnl,
                "reason": reason,
            }
        )

        print("CLOSE:", s, "reason=", reason, "PNL=", round(pnl, 4))


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
                    "decision=",
                    r.get("decision"),
                    "direction=",
                    r.get("direction"),
                    "score=",
                    round(_safe_float(r.get("trade_score")), 4),
                    "pressure=",
                    round(_safe_float(r.get("pressure_score")), 4),
                    "accel=",
                    round(_safe_float(r.get("pressure_acceleration")), 4),
                )
            print("-------------------\n")

            open_positions_if_allowed(signals)

        save_summary()
        time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("Stopped.")
        break

    except Exception as e:
        print("ENGINE ERROR:", e)
        traceback.print_exc()
        time.sleep(5)