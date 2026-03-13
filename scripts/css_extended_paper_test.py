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
# CONFIG
# ---------------------------------------------------------

SCAN_INTERVAL_SECONDS = int(os.getenv("CSS_TEST_SCAN_INTERVAL_SECONDS", "30"))
SEED_COUNT = int(os.getenv("CSS_TEST_SEED_COUNT", "5"))
MAX_OPEN_POSITIONS = int(os.getenv("CSS_TEST_MAX_OPEN_POSITIONS", "3"))
STARTING_CAPITAL = float(os.getenv("CSS_TEST_STARTING_CAPITAL", "200.0"))

TAKE_PROFIT_PCT = float(os.getenv("CSS_TEST_TP_PCT", "0.025"))   # 2.5%
STOP_LOSS_PCT = float(os.getenv("CSS_TEST_SL_PCT", "0.012"))     # 1.2%
MAX_HOLD_CYCLES = int(os.getenv("CSS_TEST_MAX_HOLD_CYCLES", "8"))

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
        "config": {
            "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
            "seed_count": SEED_COUNT,
            "max_open_positions": MAX_OPEN_POSITIONS,
            "take_profit_pct": TAKE_PROFIT_PCT,
            "stop_loss_pct": STOP_LOSS_PCT,
            "max_hold_cycles": MAX_HOLD_CYCLES,
        },
    }

    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _normalize_candles(candles: List[Any]) -> List[Dict[str, float]]:
    normalized: List[Dict[str, float]] = []

    for c in candles:
        try:
            normalized.append(
                {
                    "open": _safe_float(getattr(c, "open", 0.0)),
                    "high": _safe_float(getattr(c, "high", 0.0)),
                    "low": _safe_float(getattr(c, "low", 0.0)),
                    "close": _safe_float(getattr(c, "close", 0.0)),
                    "volume": _safe_float(getattr(c, "volume", 0.0)),
                }
            )
        except Exception:
            continue

    return [c for c in normalized if c["close"] > 0.0]


def discover_coinbase_symbols() -> List[str]:
    try:
        discovered = scanner.scan()
    except Exception:
        discovered = []

    symbols: List[str] = []
    seen = set()

    for item in discovered:
        if not isinstance(item, dict):
            continue

        venue = str(item.get("venue", "")).upper().strip()
        symbol = str(item.get("symbol", "")).upper().strip()

        if venue != "COINBASE":
            continue
        if not symbol or symbol in seen:
            continue

        symbols.append(symbol)
        seen.add(symbol)

    return symbols[:SEED_COUNT]


def fetch_assets(symbols: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for symbol in symbols:
        try:
            payload = load_runtime_asset(symbol)
            if not isinstance(payload, dict):
                continue

            candles = _normalize_candles(payload.get("candles", []))
            if len(candles) < 10:
                continue

            price = _safe_float(payload.get("price"))
            if price <= 0:
                continue

            vwap = compute_vwap_from_candles(candles, 20)
            if vwap <= 0:
                vwap = price

            spread_bps = abs(((price - vwap) / vwap) * 10000.0) if vwap > 0 else 0.0

            row = dict(payload)
            row.update(
                {
                    "symbol": symbol,
                    "asset": symbol,
                    "price": price,
                    "current_price": price,
                    "vwap": vwap,
                    "spread_bps": spread_bps,
                    "candles": candles,
                }
            )
            rows.append(row)

        except Exception:
            continue

    return rows


def build_signal_pipeline(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    features = feature_builder.enrich_rows(rows, {})
    regime_rows = regime_engine.detect(features)
    pressure_rows = pressure_engine.enrich_rows(regime_rows)
    accel_rows = accel_engine.enrich(pressure_rows)
    sweep_rows = sweep_engine.enrich(accel_rows)

    ranked = ai.rank_opportunities(sweep_rows)
    sweep_map = {str(r.get("symbol", "")): r for r in sweep_rows}

    merged: List[Dict[str, Any]] = []
    for r in ranked:
        symbol = str(r.get("symbol", ""))
        s = sweep_map.get(symbol, {})
        new_row = {
            "symbol": symbol,
            "score": _safe_float(r.get("score")),
            "decision": str(r.get("decision", "IGNORE")),
            "pressure_score": _safe_float(s.get("pressure_score")),
            "pressure_acceleration": _safe_float(s.get("pressure_acceleration")),
            "spread_bps": _safe_float(s.get("spread_bps")),
            "regime": str(s.get("regime", "NEUTRAL")),
            "price": _safe_float(s.get("price")),
            "vwap": _safe_float(s.get("vwap")),
            "liquidity_sweep_up": bool(s.get("liquidity_sweep_up", False)),
            "liquidity_sweep_down": bool(s.get("liquidity_sweep_down", False)),
        }
        merged.append(new_row)

    optimized = optimizer.optimize(merged)
    return optimized


def mark_to_market_and_close(current_rows: Dict[str, Dict[str, Any]]) -> None:
    global realized_pnl

    to_close: List[str] = []

    for symbol, pos in open_positions.items():
        row = current_rows.get(symbol)
        if row is None:
            pos["cycles_held"] += 1
            if pos["cycles_held"] >= MAX_HOLD_CYCLES:
                to_close.append(symbol)
            continue

        current_price = _safe_float(row.get("price"))
        entry_price = _safe_float(pos.get("entry_price"))

        if current_price <= 0 or entry_price <= 0:
            pos["cycles_held"] += 1
            if pos["cycles_held"] >= MAX_HOLD_CYCLES:
                to_close.append(symbol)
            continue

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
            pos["exit_reason"] = "TIME_EXIT"
            to_close.append(symbol)

    for symbol in to_close:
        pos = open_positions.pop(symbol, None)
        if pos is None:
            continue

        exit_price = _safe_float(pos.get("last_price", pos.get("entry_price")))
        entry_price = _safe_float(pos.get("entry_price"))
        size_usd = _safe_float(pos.get("size_usd"))
        qty = (size_usd / entry_price) if entry_price > 0 else 0.0
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


def open_new_positions(optimized_rows: List[Dict[str, Any]]) -> None:
    available_slots = MAX_OPEN_POSITIONS - len(open_positions)
    if available_slots <= 0:
        return

    candidates = [
        r for r in optimized_rows
        if str(r.get("decision", "IGNORE")).upper() == "TRADE"
        and str(r.get("symbol", "")) not in open_positions
        and _safe_float(r.get("price")) > 0
    ]

    if not candidates:
        return

    candidates = sorted(candidates, key=lambda x: _safe_float(x.get("trade_score")), reverse=True)[:available_slots]

    capital_per_trade = STARTING_CAPITAL / max(MAX_OPEN_POSITIONS, 1)

    for row in candidates:
        symbol = str(row.get("symbol", ""))
        entry_price = _safe_float(row.get("price"))
        if entry_price <= 0:
            continue

        open_positions[symbol] = {
            "symbol": symbol,
            "entry_price": entry_price,
            "last_price": entry_price,
            "size_usd": capital_per_trade,
            "entry_cycle": cycle_no,
            "cycles_held": 0,
            "trade_score": _safe_float(row.get("trade_score")),
            "score": _safe_float(row.get("score")),
            "pressure_score": _safe_float(row.get("pressure_score")),
            "pressure_acceleration": _safe_float(row.get("pressure_acceleration")),
            "regime": str(row.get("regime", "NEUTRAL")),
        }

        _write_jsonl(
            TRADE_LOG_PATH,
            {
                "event": "OPEN",
                "timestamp_utc": now_utc(),
                "symbol": symbol,
                "entry_price": round(entry_price, 8),
                "size_usd": round(capital_per_trade, 2),
                "entry_cycle": cycle_no,
                "trade_score": round(_safe_float(row.get("trade_score")), 4),
                "score": round(_safe_float(row.get("score")), 4),
                "pressure_score": round(_safe_float(row.get("pressure_score")), 4),
                "pressure_acceleration": round(_safe_float(row.get("pressure_acceleration")), 4),
                "regime": str(row.get("regime", "NEUTRAL")),
            },
        )


def print_status(optimized_rows: List[Dict[str, Any]]) -> None:
    wins = sum(1 for t in closed_trades if _safe_float(t.get("pnl_usd")) > 0)
    total = len(closed_trades)
    win_rate = (wins / total) if total > 0 else 0.0

    os.system("cls" if os.name == "nt" else "clear")
    print("==============================================================")
    print("            CSS EXTENDED PAPER TEST HARNESS")
    print("==============================================================")
    print(f"Cycle: {cycle_no}")
    print(f"Timestamp (UTC): {now_utc()}")
    print(f"Open Positions: {len(open_positions)} | Closed Trades: {len(closed_trades)}")
    print(f"Realized PnL: ${realized_pnl:.2f} | Win Rate: {win_rate:.2%}")
    print()
    print("TOP SIGNALS")
    print("--------------------------------------------------------------")

    if not optimized_rows:
        print("No optimized rows this cycle.")
    else:
        for r in optimized_rows[:5]:
            print(
                f"{str(r.get('symbol','')):10} "
                f"regime={str(r.get('regime','NEUTRAL')):14} "
                f"score={_safe_float(r.get('score')):.2f} "
                f"pressure={_safe_float(r.get('pressure_score')):.2f} "
                f"accel={_safe_float(r.get('pressure_acceleration')):.2f} "
                f"trade={_safe_float(r.get('trade_score')):.2f} "
                f"decision={str(r.get('decision','IGNORE'))}"
            )

    print()
    print("OPEN POSITIONS")
    print("--------------------------------------------------------------")
    if not open_positions:
        print("None")
    else:
        for _, pos in open_positions.items():
            print(
                f"{pos['symbol']:10} entry={pos['entry_price']:.6f} "
                f"last={_safe_float(pos.get('last_price')):.6f} "
                f"held={int(pos.get('cycles_held', 0))} cycles"
            )

    print()
    print(f"Trade log: {TRADE_LOG_PATH}")
    print(f"Summary : {SUMMARY_PATH}")
    print()
    print(f"Sleeping {SCAN_INTERVAL_SECONDS}s...")


print("[CSS] Starting extended paper test...", flush=True)

while True:
    cycle_no += 1

    try:
        symbols = discover_coinbase_symbols()
        rows = fetch_assets(symbols)

        current_map = {str(r.get("symbol", "")): r for r in rows}
        mark_to_market_and_close(current_map)

        optimized_rows: List[Dict[str, Any]] = []
        if rows:
            optimized_rows = build_signal_pipeline(rows)
            open_new_positions(optimized_rows)

        _save_summary()
        print_status(optimized_rows)
        time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        _save_summary()
        print("CSS extended paper test stopped.")
        break

    except Exception as exc:
        _save_summary()
        print(f"[CSS TEST ERROR] {exc}")
        time.sleep(SCAN_INTERVAL_SECONDS)