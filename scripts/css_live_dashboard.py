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

MAX_SYMBOLS_PER_CYCLE = 25
REFRESH_SECONDS = 10

MIN_CONFLUENCE_TO_REACH_OPTIMIZER = 0.72
MIN_PRESSURE_TO_REACH_OPTIMIZER = 0.18
MIN_ACCEL_TO_REACH_OPTIMIZER = 0.05
MIN_ABS_SPREAD_BPS_TO_REACH_OPTIMIZER = 12.0

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
    if value < 0:
        return 0
    if value > 1:
        return 1
    return value


def regime_alignment_score(regime: str) -> float:

    r = regime.upper()

    if r == "MEAN_REVERSION":
        return 1.0
    if r == "TREND":
        return 0.9
    if r == "BREAKOUT":
        return 0.88
    if r == "VOLATILE":
        return 0.82
    if r == "NEUTRAL":
        return 0.72

    return 0.4


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


# -------------------------------------------------------
# NEW TIER-AWARE EXECUTION GATE
# -------------------------------------------------------
def passes_execution_gate(row: Dict[str, Any]) -> bool:

    trade_score = safe_float(row.get("trade_score"), 0.0)
    confluence_score = safe_float(row.get("confluence_score"), 0.0)
    pressure_score = safe_float(row.get("pressure_score"), 0.0)
    pressure_acceleration = safe_float(row.get("pressure_acceleration"), 0.0)

    regime = str(row.get("regime", "NEUTRAL")).upper()
    tier = str(row.get("signal_tier", "WATCH")).upper()

    if regime not in ALLOWED_EXECUTION_REGIMES:
        return False

    # ELITE signals
    if tier == "ELITE":

        if confluence_score >= 0.80:
            return True

        return False

    # QUALIFIED signals
    if tier == "QUALIFIED":

        if trade_score < MIN_TRADE_SCORE_TO_EXECUTE:
            return False

        if confluence_score < MIN_CONFLUENCE_TO_EXECUTE:
            return False

        if pressure_score >= MIN_PRESSURE_TO_EXECUTE:
            return True

        if pressure_acceleration >= MIN_ACCEL_OR_PRESSURE_BOOST:
            return True

        return False

    return False


def persist_state(summary: Dict[str, Any]) -> None:

    with SUMMARY_FILE.open("w") as f:
        json.dump(summary, f, indent=2)

    with POSITIONS_FILE.open("w") as f:
        json.dump(position_manager.get_open_positions(), f, indent=2)

    with CLOSED_TRADES_FILE.open("w") as f:
        json.dump(position_manager.get_closed_positions(), f, indent=2)


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

        rows = []

        for symbol in symbols:

            try:

                payload = load_runtime_asset(symbol)

                candles = payload.get("candles", [])

                if len(candles) < 20:
                    continue

                price = safe_float(payload.get("price"), 0)

                if price <= 0:
                    price = safe_float(candles[-1]["close"], 0)

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

            except Exception:
                continue

        if not rows:
            time.sleep(REFRESH_SECONDS)
            continue

        latest_prices = {r["symbol"]: r["price"] for r in rows}

        features = feature_builder.enrich_rows(rows, {})
        regime_rows = regime_engine.detect(features)
        pressure_rows = pressure_engine.enrich_rows(regime_rows)
        accel_rows = accel_engine.enrich_rows(pressure_rows)
        confluence_rows = confluence_engine.enrich_rows(accel_rows)
        sweep_rows = sweep_engine.detect(confluence_rows)

        ranked = ai.rank_opportunities(sweep_rows)

        merged = []

        signal_map = {r["symbol"]: r for r in sweep_rows}

        for r in ranked:

            symbol = r["symbol"]

            p = signal_map.get(symbol, {})

            regime = p.get("regime", "NEUTRAL")

            base_ai_score = safe_float(r.get("score"))

            pressure_score = safe_float(p.get("pressure_score"))
            pressure_acceleration = safe_float(p.get("pressure_acceleration"))
            confluence_score = safe_float(p.get("confluence_score"))

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
                    "spread_bps": safe_float(p.get("spread_bps")),
                    "regime": regime,
                }
            )

        optimizer_input = [
            row for row in merged
            if row["confluence_score"] >= MIN_CONFLUENCE_TO_REACH_OPTIMIZER
        ]

        optimized = optimizer.optimize(optimizer_input)

        passing_execution_gate = [
            r for r in optimized
            if r.get("decision") == "TRADE" and passes_execution_gate(r)
        ]

        for r in passing_execution_gate:

            symbol = r["symbol"]

            price = latest_prices.get(symbol)

            if position_manager.has_open_position(symbol):
                continue

            qty = 10 / price

            position_manager.open_long_position(
                symbol=symbol,
                quantity=qty,
                entry_price=price,
                cycle_no=cycle,
                opened_at_utc=now(),
            )

            print("[OPEN]", symbol, price)

        closed_positions = position_manager.update_positions(
            latest_prices=latest_prices,
            cycle_no=cycle,
            timestamp_utc=now(),
        )

        for trade in closed_positions:

            pnl = safe_float(trade.get("realized_pnl_usd"))

            estimated_equity += pnl

        pm_summary = position_manager.summary()

        summary = {
            "cycle": cycle,
            "equity": estimated_equity,
            **pm_summary,
        }

        persist_state(summary)

        clear()

        print("======================================")
        print("   CAPITAL STRATA SYSTEMS DASHBOARD")
        print("======================================\n")

        print("Cycle:", cycle)
        print("Equity:", round(estimated_equity, 2))

        print("\nAI SIGNAL SCANNER\n")

        for r in optimized[:15]:

            exec_gate = "PASS" if passes_execution_gate(r) else "HOLD"

            print(
                f"{r['symbol']:10}"
                f" regime={r.get('regime','')}"
                f" score={safe_float(r.get('score')):.2f}"
                f" pressure={safe_float(r.get('pressure_score')):.2f}"
                f" accel={safe_float(r.get('pressure_acceleration')):.2f}"
                f" confluence={safe_float(r.get('confluence_score')):.2f}"
                f" trade={safe_float(r.get('trade_score')):.2f}"
                f" tier={r.get('signal_tier','WATCH')}"
                f" decision={r.get('decision','WATCH')}"
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