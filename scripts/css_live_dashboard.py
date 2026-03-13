from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

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


scanner = UnifiedMarketScanner()

feature_builder = FeatureBuilder()
regime_engine = MarketRegimeEngine()
pressure_engine = OpportunityPressureEngine()
accel_engine = PressureAccelerationEngine()
sweep_engine = LiquiditySweepDetector()
ai = AIOpportunityScorer()
optimizer = QuantSignalOptimizer()

capital = 200
cycle = 0


def now():
    return datetime.now(timezone.utc).isoformat()


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def fetch_assets(symbols):

    rows = []

    for symbol in symbols:

        try:

            payload = load_runtime_asset(symbol)

            candles = payload.get("candles", [])

            if len(candles) < 10:
                continue

            price = float(payload.get("price", 0))

            vwap = compute_vwap_from_candles(candles, 20)

            if vwap == 0:
                vwap = price

            spread = ((price - vwap) / vwap) * 10000

            rows.append(
                {
                    "symbol": symbol,
                    "price": price,
                    "vwap": vwap,
                    "spread_bps": abs(spread),
                    "candles": candles,
                }
            )

        except Exception:
            continue

    return rows


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

        # ----- Intelligence Pipeline -----

        features = feature_builder.enrich_rows(rows, {})

        regime_rows = regime_engine.detect(features)

        pressure_rows = pressure_engine.enrich_rows(regime_rows)

        accel_rows = accel_engine.enrich(pressure_rows)

        sweep_rows = sweep_engine.enrich(accel_rows)

        ranked = ai.rank_opportunities(sweep_rows)

        pressure_map = {r["symbol"]: r for r in sweep_rows}

        merged = []

        for r in ranked:

            p = pressure_map.get(r["symbol"], {})

            merged.append(
                {
                    "symbol": r["symbol"],
                    "score": r.get("score", 0),
                    "pressure_score": p.get("pressure_score", 0),
                    "pressure_acceleration": p.get(
                        "pressure_acceleration", 0
                    ),
                    "spread_bps": p.get("spread_bps", 0),
                    "regime": p.get("regime", "NEUTRAL"),
                }
            )

        optimized = optimizer.optimize(merged)

        clear()

        print("====================================================")
        print("        CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
        print("====================================================\n")

        print(f"Cycle: {cycle} | Capital: ${capital:.2f}")
        print("Active Symbols:", ", ".join(symbols))
        print("Timestamp:", now())

        print("\nAI OPPORTUNITY SCANNER")
        print("----------------------------------------------------")

        for r in optimized:

            print(
                f"{r['symbol']:10}"
                f" regime={r['regime']:14}"
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