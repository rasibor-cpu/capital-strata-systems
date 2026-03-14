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
from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.strategies.vwap_mean_reversion import compute_vwap_from_candles


ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)

SUMMARY_FILE = ARTIFACT_DIR / "css_extended_paper_test_summary.json"
POSITIONS_FILE = ARTIFACT_DIR / "css_open_positions.json"
CLOSED_TRADES_FILE = ARTIFACT_DIR / "css_closed_trades.json"


scanner = UnifiedMarketScanner()

feature_builder = FeatureBuilder()
regime_engine = MarketRegimeEngine()
pressure_engine = OpportunityPressureEngine()
accel_engine = PressureAccelerationEngine()
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


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def candle_close(candle: Any) -> float:
    """
    Extract close price safely from candle structures.
    Supports dict and list formats.
    """

    if isinstance(candle, dict):
        for k in ("close", "c", "price"):
            if k in candle:
                return safe_float(candle.get(k))

    if isinstance(candle, (list, tuple)) and len(candle) >= 5:
        return safe_float(candle[4])

    return 0.0


def fetch_assets(symbols: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for symbol in symbols:

        try:
            payload = load_runtime_asset(symbol)
            candles = payload.get("candles", [])

            if len(candles) < 20:
                continue

            # ---------------------------
            # Determine price
            # ---------------------------

            price = safe_float(payload.get("price", 0.0))

            if price <= 0:
                price = candle_close(candles[-1])

            if price <= 0:
                continue

            # ---------------------------
            # VWAP
            # ---------------------------

            vwap = safe_float(compute_vwap_from_candles(candles, 20))

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

        except Exception:
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


print("[CSS] Starting live dashboard...")


while True:

    cycle += 1

    try:

        discovered = scanner.scan()

        symbols = [
            r["symbol"]
            for r in discovered
            if r.get("venue") == "COINBASE"
        ][:5]

        rows = fetch_assets(symbols)

        if not rows:
            print("Waiting for valid market rows...")
            time.sleep(10)
            continue

        latest_prices = {r["symbol"]: r["price"] for r in rows}

        # ---------------------------
        # Intelligence Pipeline
        # ---------------------------

        features = feature_builder.enrich_rows(rows, {})
        regime_rows = regime_engine.detect(features)
        pressure_rows = pressure_engine.enrich_rows(regime_rows)
        accel_rows = accel_engine.enrich(pressure_rows)
        sweep_rows = sweep_engine.enrich(accel_rows)
        ranked = ai.rank_opportunities(sweep_rows)

        pressure_map = {r["symbol"]: r for r in sweep_rows}

        merged: List[Dict[str, Any]] = []

        for r in ranked:

            p = pressure_map.get(r["symbol"], {})

            merged.append(
                {
                    "symbol": r["symbol"],
                    "score": safe_float(r.get("score")),
                    "pressure_score": safe_float(p.get("pressure_score")),
                    "pressure_acceleration": safe_float(
                        p.get("pressure_acceleration")
                    ),
                    "spread_bps": safe_float(p.get("spread_bps")),
                    "regime": str(p.get("regime", "NEUTRAL")),
                }
            )

        optimized = optimizer.optimize(merged)

        # ---------------------------
        # Open Positions
        # ---------------------------

        for r in optimized:

            symbol = r["symbol"]
            decision = r["decision"]
            trade_score = r["trade_score"]
            price = latest_prices.get(symbol, 0)

            if decision != "TRADE":
                continue

            if position_manager.has_open_position(symbol):
                continue

            allocation = 10.0
            quantity = allocation / price

            position_manager.open_long_position(
                symbol=symbol,
                quantity=quantity,
                entry_price=price,
                cycle_no=cycle,
                opened_at_utc=now(),
            )

            print(
                f"[OPEN] {symbol} | "
                f"price={price:.6f} | "
                f"qty={quantity:.8f} | "
                f"score={trade_score:.2f}"
            )

        # ---------------------------
        # Close Positions
        # ---------------------------

        closed_positions = position_manager.update_positions(
            latest_prices=latest_prices,
            cycle_no=cycle,
            timestamp_utc=now(),
        )

        for trade in closed_positions:

            pnl = safe_float(trade.get("realized_pnl_usd"))

            estimated_equity += pnl

            print(
                f"[CLOSE] {trade['symbol']} | "
                f"reason={trade['exit_reason']} | "
                f"pnl={pnl:.4f}"
            )

        pm_summary = position_manager.summary()

        summary = {
            "timestamp_utc": now(),
            "cycle_no": cycle,
            "starting_capital_usd": starting_capital,
            "estimated_equity_usd": estimated_equity,
            **pm_summary,
        }

        persist_state(summary)

        clear()

        print("======================================")
        print("   CAPITAL STRATA SYSTEMS DASHBOARD")
        print("======================================\n")

        print("Cycle:", cycle)
        print("Equity:", round(estimated_equity, 2))
        print("Symbols:", symbols)

        print("\nAI SIGNAL SCANNER\n")

        for r in optimized:

            print(
                f"{r['symbol']:10}"
                f" regime={r['regime']:10}"
                f" score={r['score']:.2f}"
                f" pressure={r['pressure_score']:.2f}"
                f" accel={r['pressure_acceleration']:.2f}"
                f" trade={r['trade_score']:.2f}"
                f" decision={r['decision']}"
            )

        print("\nRefreshing in 10 seconds...\n")

        time.sleep(10)

    except KeyboardInterrupt:

        print("CSS stopped")
        break

    except Exception as e:

        print("CSS ERROR:", e)
        time.sleep(10)