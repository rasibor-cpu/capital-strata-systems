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
from backend.execution.position_manager import PositionManager
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.liquidity_sweep_detector import LiquiditySweepDetector
from backend.intelligence.market_regime_engine import MarketRegimeEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine
from backend.scanner.unified_market_scanner import UnifiedMarketScanner

ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)

SUMMARY_FILE = ARTIFACT_DIR / "css_extended_paper_test_summary.json"
POSITIONS_FILE = ARTIFACT_DIR / "css_open_positions.json"
CLOSED_TRADES_FILE = ARTIFACT_DIR / "css_closed_trades.json"

# ------------------------------------------------
# LIVE OPERATING CONTROLS
# ------------------------------------------------
MAX_SYMBOLS_PER_CYCLE = 25
REFRESH_SECONDS = 10

# ------------------------------------------------
# HIGH-QUALITY SELECTION GATES
# ------------------------------------------------
MIN_CONFLUENCE_TO_REACH_OPTIMIZER = 0.72
MIN_PRESSURE_TO_REACH_OPTIMIZER = 0.18
MIN_ACCEL_TO_REACH_OPTIMIZER = 0.05
MIN_ABS_SPREAD_BPS_TO_REACH_OPTIMIZER = 12.0

# ------------------------------------------------
# FINAL EXECUTION GATES
# ------------------------------------------------
MIN_TRADE_SCORE_TO_EXECUTE = 0.34
MIN_CONFLUENCE_TO_EXECUTE = 0.78
MIN_PRESSURE_TO_EXECUTE = 0.22
MIN_ACCEL_OR_PRESSURE_BOOST = 0.10

ALLOWED_EXECUTION_REGIMES = {
    "MEAN_REVERSION",
    "TREND",
    "VOLATILE",
    "BREAKOUT",
    "NEUTRAL",
}

scanner = UnifiedMarketScanner()

feature_builder = FeatureBuilder()
regime_engine = MarketRegimeEngine()
pressure_engine = OpportunityPressureEngine()
accel_engine = PressureAccelerationEngine()
confluence_engine = SignalConfluenceEngine()
sweep_engine = LiquiditySweepDetector()
ai = AIOpportunityScorer()
optimizer = QuantSignalOptimizer()

position_manager = PositionManager(
    take_profit_pct=0.025,
    stop_loss_pct=0.012,
    max_hold_cycles=8,
)

starting_capital = 200.0
estimated_equity = starting_capital
cycle = 0
_debug_payload_logged = False


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def candle_attr(candle: Any, name: str, default: float = 0.0) -> float:
    if hasattr(candle, name):
        return safe_float(getattr(candle, name), default)

    if isinstance(candle, dict):
        return safe_float(candle.get(name, default), default)

    if isinstance(candle, (list, tuple)):
        idx_map = {
            "ts": 0,
            "open": 1,
            "high": 2,
            "low": 3,
            "close": 4,
            "volume": 5,
        }
        idx = idx_map.get(name)
        if idx is not None and len(candle) > idx:
            return safe_float(candle[idx], default)

    return float(default)


def normalize_candle(candle: Any) -> Dict[str, float]:
    return {
        "ts": candle_attr(candle, "ts", 0.0),
        "open": candle_attr(candle, "open", 0.0),
        "high": candle_attr(candle, "high", 0.0),
        "low": candle_attr(candle, "low", 0.0),
        "close": candle_attr(candle, "close", 0.0),
        "volume": candle_attr(candle, "volume", 0.0),
    }


def normalize_candles(candles: List[Any]) -> List[Dict[str, float]]:
    return [normalize_candle(c) for c in candles]


def extract_price_from_payload(payload: Dict[str, Any]) -> float:
    for key in (
        "price",
        "close",
        "last",
        "last_price",
        "mark_price",
        "mid",
        "mid_price",
        "value",
        "c",
        "current_price",
    ):
        if key in payload:
            v = safe_float(payload.get(key), 0.0)
            if v > 0:
                return v

    for nested_key in ("ticker", "quote", "meta", "snapshot", "data"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            for key in (
                "price",
                "close",
                "last",
                "last_price",
                "mark_price",
                "mid",
                "mid_price",
                "value",
                "c",
                "current_price",
            ):
                if key in nested:
                    v = safe_float(nested.get(key), 0.0)
                    if v > 0:
                        return v

    return 0.0


def compute_vwap_robust(candles: List[Dict[str, float]], lookback: int = 20) -> float:
    if not candles:
        return 0.0

    window = candles[-lookback:] if len(candles) >= lookback else candles

    pv_sum = 0.0
    vol_sum = 0.0

    for candle in window:
        high = safe_float(candle.get("high"), 0.0)
        low = safe_float(candle.get("low"), 0.0)
        close = safe_float(candle.get("close"), 0.0)
        volume = safe_float(candle.get("volume"), 0.0)

        if close <= 0:
            continue

        typical_price = close
        if high > 0 and low > 0:
            typical_price = (high + low + close) / 3.0

        if volume <= 0:
            volume = 1.0

        pv_sum += typical_price * volume
        vol_sum += volume

    if vol_sum <= 0:
        return 0.0

    return pv_sum / vol_sum


def call_rows_module(module: Any, rows: List[Dict[str, Any]], label: str) -> List[Dict[str, Any]]:
    if hasattr(module, "enrich_rows"):
        return module.enrich_rows(rows)

    if hasattr(module, "enrich"):
        return module.enrich(rows)

    if hasattr(module, "detect"):
        return module.detect(rows)

    print(f"[PIPELINE-WARN] {label}: no compatible row method found, passing rows through")
    return rows


def fetch_assets(symbols: List[str]) -> List[Dict[str, Any]]:
    global _debug_payload_logged

    rows: List[Dict[str, Any]] = []

    for symbol in symbols:
        try:
            payload = load_runtime_asset(symbol)

            if not isinstance(payload, dict):
                print(f"[ROW-SKIP] {symbol}: payload is not dict")
                continue

            raw_candles = payload.get("candles", [])
            if not isinstance(raw_candles, list):
                print(f"[ROW-SKIP] {symbol}: candles is not list")
                continue

            if not _debug_payload_logged:
                print(f"[DEBUG] sample payload keys for {symbol}: {list(payload.keys())}")
                if raw_candles:
                    print(f"[DEBUG] sample candle type for {symbol}: {type(raw_candles[-1]).__name__}")
                    print(f"[DEBUG] sample candle value for {symbol}: {raw_candles[-1]}")
                _debug_payload_logged = True

            if len(raw_candles) < 20:
                print(f"[ROW-SKIP] {symbol}: insufficient candles ({len(raw_candles)})")
                continue

            candles = normalize_candles(raw_candles)

            price = extract_price_from_payload(payload)
            if price <= 0:
                price = safe_float(candles[-1].get("close"), 0.0)

            if price <= 0:
                print(f"[ROW-SKIP] {symbol}: could not derive price")
                continue

            vwap = compute_vwap_robust(candles, 20)
            if vwap <= 0:
                vwap = price

            spread = ((price - vwap) / vwap) * 10000

            rows.append(
                {
                    "symbol": symbol,
                    "price": price,
                    "vwap": vwap,
                    "spread_bps": spread,
                    "candles": candles,
                }
            )

            print(
                f"[ROW-OK] {symbol}: "
                f"price={price:.6f}, "
                f"vwap={vwap:.6f}, "
                f"spread_bps={spread:.2f}, "
                f"candles={len(candles)}"
            )

        except Exception as exc:
            print(f"[ROW-ERROR] {symbol}: {exc}")
            continue

    return rows


def persist_state(summary: Dict[str, Any]) -> None:
    try:
        with SUMMARY_FILE.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        with POSITIONS_FILE.open("w", encoding="utf-8") as f:
            json.dump(position_manager.get_open_positions(), f, indent=2)

        with CLOSED_TRADES_FILE.open("w", encoding="utf-8") as f:
            json.dump(position_manager.get_closed_positions(), f, indent=2)
    except Exception as exc:
        print(f"[WARN] Could not persist artifact state: {exc}")


def regime_alignment_score(regime: str) -> float:
    r = str(regime).upper()

    if r == "MEAN_REVERSION":
        return 1.00
    if r == "TREND":
        return 0.90
    if r == "BREAKOUT":
        return 0.88
    if r == "VOLATILE":
        return 0.82
    if r == "NEUTRAL":
        return 0.72
    return 0.40


def blended_conviction_score(
    *,
    base_ai_score: float,
    confluence_score: float,
    pressure_score: float,
    pressure_acceleration: float,
    regime: str,
) -> float:
    regime_score = regime_alignment_score(regime)

    score = (
        0.20 * clamp01(base_ai_score)
        + 0.35 * clamp01(confluence_score)
        + 0.25 * clamp01(pressure_score)
        + 0.20 * clamp01(pressure_acceleration)
        + 0.20 * clamp01(regime_score)
    )

    return clamp01(score)


def passes_optimizer_gate(row: Dict[str, Any]) -> bool:
    confluence_score = safe_float(row.get("confluence_score"), 0.0)
    pressure_score = safe_float(row.get("pressure_score"), 0.0)
    pressure_acceleration = safe_float(row.get("pressure_acceleration"), 0.0)
    spread_bps_abs = abs(safe_float(row.get("spread_bps"), 0.0))
    regime = str(row.get("regime", "NEUTRAL")).upper()

    if regime not in ALLOWED_EXECUTION_REGIMES:
        return False

    if confluence_score < MIN_CONFLUENCE_TO_REACH_OPTIMIZER:
        return False

    if spread_bps_abs < MIN_ABS_SPREAD_BPS_TO_REACH_OPTIMIZER:
        return False

    if pressure_score < MIN_PRESSURE_TO_REACH_OPTIMIZER and pressure_acceleration < MIN_ACCEL_TO_REACH_OPTIMIZER:
        return False

    return True


def passes_execution_gate(row: Dict[str, Any]) -> bool:
    trade_score = safe_float(row.get("trade_score"), 0.0)
    confluence_score = safe_float(row.get("confluence_score"), 0.0)
    pressure_score = safe_float(row.get("pressure_score"), 0.0)
    pressure_acceleration = safe_float(row.get("pressure_acceleration"), 0.0)
    regime = str(row.get("regime", "NEUTRAL")).upper()

    if regime not in ALLOWED_EXECUTION_REGIMES:
        return False

    if trade_score < MIN_TRADE_SCORE_TO_EXECUTE:
        return False

    if confluence_score < MIN_CONFLUENCE_TO_EXECUTE:
        return False

    if pressure_score < MIN_PRESSURE_TO_EXECUTE:
        return False

    if pressure_acceleration < MIN_ACCEL_OR_PRESSURE_BOOST and pressure_score < 0.30:
        return False

    return True


print("[CSS] Starting live dashboard...")

while True:
    cycle += 1

    try:
        discovered = scanner.scan()

        symbols = [
            r["symbol"]
            for r in discovered
            if r.get("venue") == "COINBASE"
        ][:MAX_SYMBOLS_PER_CYCLE]

        print(f"[SCAN] selected Coinbase symbols ({len(symbols)}): {symbols}")

        rows = fetch_assets(symbols)

        if not rows:
            print("Waiting for valid market rows...")
            time.sleep(REFRESH_SECONDS)
            continue

        latest_prices: Dict[str, float] = {r["symbol"]: r["price"] for r in rows}

        features = feature_builder.enrich_rows(rows, {})
        regime_rows = regime_engine.detect(features)
        pressure_rows = call_rows_module(pressure_engine, regime_rows, "OpportunityPressureEngine")
        accel_rows = call_rows_module(accel_engine, pressure_rows, "PressureAccelerationEngine")
        confluence_rows = call_rows_module(confluence_engine, accel_rows, "SignalConfluenceEngine")
        sweep_rows = call_rows_module(sweep_engine, confluence_rows, "LiquiditySweepDetector")
        ranked = ai.rank_opportunities(sweep_rows)

        signal_map = {str(r["symbol"]).upper(): r for r in sweep_rows}

        merged: List[Dict[str, Any]] = []
        for r in ranked:
            symbol = str(r.get("symbol", "")).upper()
            p = signal_map.get(symbol, {})
            regime = str(p.get("regime", "NEUTRAL")).upper()

            base_ai_score = safe_float(r.get("score"), 0.0)
            pressure_score = safe_float(p.get("pressure_score"), 0.0)
            pressure_acceleration = safe_float(p.get("pressure_acceleration"), 0.0)
            confluence_score = safe_float(p.get("confluence_score"), 0.0)

            fused_score = blended_conviction_score(
                base_ai_score=base_ai_score,
                confluence_score=confluence_score,
                pressure_score=pressure_score,
                pressure_acceleration=pressure_acceleration,
                regime=regime,
            )

            merged.append(
                {
                    "symbol": symbol,
                    "score": fused_score,
                    "base_ai_score": base_ai_score,
                    "pressure_score": pressure_score,
                    "pressure_acceleration": pressure_acceleration,
                    "confluence_score": confluence_score,
                    "confluence_allow_trade": bool(p.get("confluence_allow_trade", False)),
                    "spread_bps": safe_float(p.get("spread_bps"), 0.0),
                    "regime": regime,
                    "regime_alignment": regime_alignment_score(regime),
                }
            )

        optimizer_input = [
            row for row in merged
            if row.get("confluence_allow_trade", False) and passes_optimizer_gate(row)
        ]

        if not optimizer_input:
            optimizer_input = sorted(
                merged,
                key=lambda x: (
                    safe_float(x.get("confluence_score"), 0.0),
                    safe_float(x.get("pressure_score"), 0.0),
                    safe_float(x.get("pressure_acceleration"), 0.0),
                    safe_float(x.get("score"), 0.0),
                ),
                reverse=True,
            )[:1]

        print(
            f"[PIPELINE] merged_rows={len(merged)} "
            f"confluence_pass={sum(1 for x in merged if x.get('confluence_allow_trade', False))} "
            f"optimizer_rows={len(optimizer_input)}"
        )

        optimized = optimizer.optimize(optimizer_input)

        optimized = sorted(
            optimized,
            key=lambda x: (
                safe_float(x.get("trade_score"), 0.0),
                safe_float(x.get("confluence_score"), 0.0),
                safe_float(x.get("pressure_score"), 0.0),
                safe_float(x.get("pressure_acceleration"), 0.0),
                safe_float(x.get("score"), 0.0),
            ),
            reverse=True,
        )

        passing_execution_gate = [
            r for r in optimized
            if str(r.get("decision", "")).upper() == "TRADE" and passes_execution_gate(r)
        ]

        for r in passing_execution_gate:
            symbol = str(r["symbol"]).upper()
            price = safe_float(latest_prices.get(symbol, 0.0), 0.0)
            trade_score = safe_float(r.get("trade_score"), 0.0)

            if price <= 0:
                continue

            if position_manager.has_open_position(symbol):
                continue

            qty = 10.0 / price

            position_manager.open_long_position(
                symbol=symbol,
                quantity=qty,
                entry_price=price,
                cycle_no=cycle,
                opened_at_utc=now(),
            )

            print(
                f"[OPEN] {symbol} | price={price:.6f} | qty={qty:.8f} | "
                f"trade={trade_score:.2f} | base_ai={safe_float(r.get('base_ai_score'), 0.0):.2f} | "
                f"confluence={safe_float(r.get('confluence_score'), 0.0):.2f} | "
                f"pressure={safe_float(r.get('pressure_score'), 0.0):.2f} | "
                f"accel={safe_float(r.get('pressure_acceleration'), 0.0):.2f}"
            )

        closed_positions = position_manager.update_positions(
            latest_prices=latest_prices,
            cycle_no=cycle,
            timestamp_utc=now(),
        )

        for trade in closed_positions:
            pnl = safe_float(trade.get("realized_pnl_usd"), 0.0)
            estimated_equity += pnl
            print(
                f"[CLOSE] {trade['symbol']} | reason={trade['exit_reason']} | pnl={pnl:.4f}"
            )

        pm_summary = position_manager.summary()

        summary = {
            "timestamp_utc": now(),
            "cycle_no": cycle,
            "starting_capital_usd": starting_capital,
            "estimated_equity_usd": estimated_equity,
            "symbols_scanned": len(symbols),
            "signals_scanned": len(merged),
            "signals_passed_confluence": sum(
                1 for x in merged if x.get("confluence_allow_trade", False)
            ),
            "signals_passed_optimizer_gate": len(
                [x for x in merged if x.get("confluence_allow_trade", False) and passes_optimizer_gate(x)]
            ),
            "signals_passed_execution_gate": len(passing_execution_gate),
            "max_symbols_per_cycle": MAX_SYMBOLS_PER_CYCLE,
            "min_trade_score_to_execute": MIN_TRADE_SCORE_TO_EXECUTE,
            "min_confluence_to_execute": MIN_CONFLUENCE_TO_EXECUTE,
            "min_pressure_to_execute": MIN_PRESSURE_TO_EXECUTE,
            **pm_summary,
        }

        persist_state(summary)

        clear()

        print("======================================")
        print("   CAPITAL STRATA SYSTEMS DASHBOARD")
        print("======================================\n")

        print("Cycle:", cycle)
        print("Equity:", round(estimated_equity, 2))
        print("Symbols scanned:", len(symbols), f"(cap={MAX_SYMBOLS_PER_CYCLE})")
        print("Execution style: THRESHOLD-DRIVEN / HIGH WIN-PROBABILITY BIAS")
        print("Trades this cycle: all signals above execution threshold")
        print("Symbols:", symbols)

        print("\nAI SIGNAL SCANNER\n")

        if not optimized:
            print("No optimized rows available this cycle.")
        else:
            for r in optimized[:15]:
                exec_gate = "PASS" if passes_execution_gate(r) else "HOLD"
                print(
                    f"{r['symbol']:10}"
                    f" regime={str(r.get('regime', 'NEUTRAL')):12}"
                    f" base={safe_float(r.get('base_ai_score', 0.0), 0.0):.2f}"
                    f" score={safe_float(r.get('score'), 0.0):.2f}"
                    f" pressure={safe_float(r.get('pressure_score'), 0.0):.2f}"
                    f" accel={safe_float(r.get('pressure_acceleration'), 0.0):.2f}"
                    f" confluence={safe_float(r.get('confluence_score'), 0.0):.2f}"
                    f" trade={safe_float(r.get('trade_score'), 0.0):.2f}"
                    f" decision={str(r.get('decision', 'WATCH'))}"
                    f" gate={exec_gate}"
                )

        print(f"\nRefreshing in {REFRESH_SECONDS} seconds...\n")
        time.sleep(REFRESH_SECONDS)

    except KeyboardInterrupt:
        print("CSS stopped")
        break

    except Exception as e:
        print("CSS ERROR:", e)
        time.sleep(REFRESH_SECONDS)