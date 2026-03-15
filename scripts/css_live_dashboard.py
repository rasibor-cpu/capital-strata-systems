from __future__ import annotations

import json
import os
import sys
import time
import traceback
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

MAX_SYMBOLS_PER_CYCLE = 25
REFRESH_SECONDS = 10

ENGINE_PROFILES: Dict[str, Dict[str, float]] = {
    "safe/test": {
        "min_confluence_to_reach_optimizer": 0.90,
        "min_pressure_to_reach_optimizer": 0.30,
        "min_accel_to_reach_optimizer": 0.15,
        "min_abs_spread_bps_to_reach_optimizer": 20.0,
        "min_trade_score_to_execute": 0.62,
        "min_confluence_to_execute": 0.90,
        "min_pressure_to_execute": 0.30,
        "min_accel_or_pressure_boost": 0.15,
    },
    "conservative": {
        "min_confluence_to_reach_optimizer": 0.84,
        "min_pressure_to_reach_optimizer": 0.24,
        "min_accel_to_reach_optimizer": 0.10,
        "min_abs_spread_bps_to_reach_optimizer": 16.0,
        "min_trade_score_to_execute": 0.58,
        "min_confluence_to_execute": 0.84,
        "min_pressure_to_execute": 0.24,
        "min_accel_or_pressure_boost": 0.10,
    },
    "balanced": {
        "min_confluence_to_reach_optimizer": 0.78,
        "min_pressure_to_reach_optimizer": 0.20,
        "min_accel_to_reach_optimizer": 0.08,
        "min_abs_spread_bps_to_reach_optimizer": 12.0,
        "min_trade_score_to_execute": 0.54,
        "min_confluence_to_execute": 0.78,
        "min_pressure_to_execute": 0.20,
        "min_accel_or_pressure_boost": 0.08,
    },
    "aggressive": {
        "min_confluence_to_reach_optimizer": 0.70,
        "min_pressure_to_reach_optimizer": 0.16,
        "min_accel_to_reach_optimizer": 0.06,
        "min_abs_spread_bps_to_reach_optimizer": 10.0,
        "min_trade_score_to_execute": 0.48,
        "min_confluence_to_execute": 0.70,
        "min_pressure_to_execute": 0.16,
        "min_accel_or_pressure_boost": 0.06,
    },
    "opportunistic/expansion": {
        "min_confluence_to_reach_optimizer": 0.62,
        "min_pressure_to_reach_optimizer": 0.12,
        "min_accel_to_reach_optimizer": 0.04,
        "min_abs_spread_bps_to_reach_optimizer": 8.0,
        "min_trade_score_to_execute": 0.42,
        "min_confluence_to_execute": 0.62,
        "min_pressure_to_execute": 0.12,
        "min_accel_or_pressure_boost": 0.04,
    },
}

ALLOWED_EXECUTION_REGIMES = {
    "MEAN_REVERSION",
    "TREND",
    "VOLATILE",
    "BREAKOUT",
    "NEUTRAL",
    "RANGE",
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


def choose_engine_mode() -> str:
    print("\nSelect CSS Engine Mode for this session:\n")
    print("1. safe/test")
    print("2. conservative")
    print("3. balanced")
    print("4. aggressive")
    print("5. opportunistic/expansion\n")

    choice = input("Enter choice (1-5): ").strip()

    mapping = {
        "1": "safe/test",
        "2": "conservative",
        "3": "balanced",
        "4": "aggressive",
        "5": "opportunistic/expansion",
    }

    mode = mapping.get(choice, "balanced")
    print(f"\n[CSS] Engine mode locked for this session: {mode.upper()}\n")
    return mode


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
    if r in {"NEUTRAL", "RANGE"}:
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
            if not isinstance(raw_candles, list) or len(raw_candles) < 20:
                print(f"[ROW-SKIP] {symbol}: insufficient candles")
                continue

            candles = normalize_candles(raw_candles)

            if not _debug_payload_logged:
                print(f"[DEBUG] sample payload keys for {symbol}: {list(payload.keys())}")
                if raw_candles:
                    print(f"[DEBUG] sample candle type for {symbol}: {type(raw_candles[-1]).__name__}")
                    print(f"[DEBUG] sample candle value for {symbol}: {raw_candles[-1]}")
                _debug_payload_logged = True

            price = safe_float(payload.get("price"), 0.0)
            vwap = safe_float(payload.get("vwap"), 0.0)
            spread_bps = safe_float(payload.get("spread_bps"), 0.0)

            if price <= 0.0:
                print(f"[ROW-SKIP] {symbol}: invalid price")
                continue

            if vwap <= 0.0:
                vwap = price

            row = dict(payload)
            row["symbol"] = str(payload.get("symbol", symbol)).upper()
            row["price"] = price
            row["vwap"] = vwap
            row["spread_bps"] = spread_bps
            row["candles"] = candles

            rows.append(row)

            print(
                f"[ROW-OK] {symbol}: "
                f"price={price:.6f}, "
                f"vwap={vwap:.6f}, "
                f"spread_bps={spread_bps:.2f}, "
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


def passes_optimizer_gate(row: Dict[str, Any], profile: Dict[str, float]) -> bool:
    confluence_score = safe_float(row.get("confluence_score"), 0.0)
    pressure_score = safe_float(row.get("pressure_score"), 0.0)
    pressure_acceleration = safe_float(row.get("pressure_acceleration"), 0.0)
    spread_bps_abs = abs(safe_float(row.get("spread_bps"), 0.0))
    regime = str(row.get("regime", "NEUTRAL")).upper()

    if regime not in ALLOWED_EXECUTION_REGIMES:
        return False

    if confluence_score < profile["min_confluence_to_reach_optimizer"]:
        return False

    if spread_bps_abs < profile["min_abs_spread_bps_to_reach_optimizer"]:
        return False

    if (
        pressure_score < profile["min_pressure_to_reach_optimizer"]
        and pressure_acceleration < profile["min_accel_to_reach_optimizer"]
    ):
        return False

    return True


def passes_execution_gate(row: Dict[str, Any], profile: Dict[str, float]) -> bool:
    trade_score = safe_float(row.get("trade_score"), 0.0)
    confluence_score = safe_float(row.get("confluence_score"), 0.0)
    pressure_score = safe_float(row.get("pressure_score"), 0.0)
    pressure_acceleration = safe_float(row.get("pressure_acceleration"), 0.0)
    regime = str(row.get("regime", "NEUTRAL")).upper()
    tier = str(row.get("signal_tier", "WATCH")).upper()

    if regime not in ALLOWED_EXECUTION_REGIMES:
        return False

    if tier == "ELITE":
        return confluence_score >= max(0.80, profile["min_confluence_to_execute"])

    if tier == "QUALIFIED":
        if trade_score < profile["min_trade_score_to_execute"]:
            return False

        if confluence_score < profile["min_confluence_to_execute"]:
            return False

        if pressure_score >= profile["min_pressure_to_execute"]:
            return True

        if pressure_acceleration >= profile["min_accel_or_pressure_boost"]:
            return True

        return False

    return False


ENGINE_MODE = choose_engine_mode()
ACTIVE_PROFILE = ENGINE_PROFILES[ENGINE_MODE]

print("[CSS] Starting live dashboard...")

while True:
    cycle += 1

    try:
        discovered = scanner.scan()

        symbols = [
            str(r["symbol"]).upper()
            for r in discovered
            if str(r.get("venue", "")).upper() == "COINBASE"
        ][:MAX_SYMBOLS_PER_CYCLE]

        print(f"[SCAN] selected Coinbase symbols ({len(symbols)}): {symbols}")

        rows = fetch_assets(symbols)

        if not rows:
            print("Waiting for valid market rows...")
            time.sleep(REFRESH_SECONDS)
            continue

        latest_prices: Dict[str, float] = {
            str(r["symbol"]).upper(): safe_float(r.get("price"), 0.0)
            for r in rows
        }

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
            if row.get("confluence_allow_trade", False) and passes_optimizer_gate(row, ACTIVE_PROFILE)
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
            if str(r.get("decision", "")).upper() == "TRADE"
            and passes_execution_gate(r, ACTIVE_PROFILE)
        ]

        for r in passing_execution_gate:
            symbol = str(r["symbol"]).upper()
            price = safe_float(latest_prices.get(symbol, 0.0), 0.0)
            trade_score = safe_float(r.get("trade_score"), 0.0)

            if price <= 0.0:
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
                f"trade={trade_score:.2f} | tier={str(r.get('signal_tier', 'WATCH')).upper()} | "
                f"base_ai={safe_float(r.get('base_ai_score'), 0.0):.2f} | "
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
            "engine_mode": ENGINE_MODE,
            "engine_profile": ACTIVE_PROFILE,
            "starting_capital_usd": starting_capital,
            "estimated_equity_usd": estimated_equity,
            "symbols_scanned": len(symbols),
            "signals_scanned": len(merged),
            "signals_passed_confluence": sum(
                1 for x in merged if x.get("confluence_allow_trade", False)
            ),
            "signals_passed_optimizer_gate": len(
                [x for x in merged if x.get("confluence_allow_trade", False) and passes_optimizer_gate(x, ACTIVE_PROFILE)]
            ),
            "signals_passed_execution_gate": len(passing_execution_gate),
            "max_symbols_per_cycle": MAX_SYMBOLS_PER_CYCLE,
            **pm_summary,
        }

        persist_state(summary)

        clear()

        print("======================================")
        print("   CAPITAL STRATA SYSTEMS DASHBOARD")
        print("======================================\n")

        print("Cycle:", cycle)
        print("Equity:", round(estimated_equity, 2))
        print("Engine mode:", ENGINE_MODE.upper())
        print("Symbols scanned:", len(symbols), f"(cap={MAX_SYMBOLS_PER_CYCLE})")
        print("Execution style: CONDITION-DRIVEN / SESSION-LOCKED POLICY")
        print("Trades this cycle: all signals above active execution conditions")
        print("Symbols:", symbols)

        print("\nAI SIGNAL SCANNER\n")

        if not optimized:
            print("No optimized rows available this cycle.")
        else:
            for r in optimized[:15]:
                exec_gate = "PASS" if passes_execution_gate(r, ACTIVE_PROFILE) else "HOLD"
                print(
                    f"{r['symbol']:10}"
                    f" regime={str(r.get('regime', 'NEUTRAL')):12}"
                    f" tier={str(r.get('signal_tier', 'WATCH')).upper():10}"
                    f" base={safe_float(r.get('base_ai_score', 0.0)):.2f}"
                    f" score={safe_float(r.get('score'), 0.0):.2f}"
                    f" pressure={safe_float(r.get('pressure_score'), 0.0):.2f}"
                    f" accel={safe_float(r.get('pressure_acceleration'), 0.0):.2f}"
                    f" confluence={safe_float(r.get('confluence_score'), 0.0):.2f}"
                    f" trade={safe_float(r.get('trade_score'), 0.0):.2f}"
                    f" decision={str(r.get('decision', 'WATCH')).upper()}"
                    f" gate={exec_gate}"
                )

        print(f"\nRefreshing in {REFRESH_SECONDS} seconds...\n")
        time.sleep(REFRESH_SECONDS)

    except KeyboardInterrupt:
        print("CSS stopped")
        break

    except Exception as e:
        print("CSS ERROR:", e)
        traceback.print_exc()
        time.sleep(REFRESH_SECONDS)