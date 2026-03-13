from __future__ import annotations

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
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer

from backend.strategies.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)

SCAN_INTERVAL = 10
SEED_COUNT = 5
MAX_DISPLAY = 5

BASE_ASSETS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "AVAX-USD",
    "LINK-USD",
]

scanner = UnifiedMarketScanner()

feature_builder = FeatureBuilder()
pressure_engine = OpportunityPressureEngine()
accel_engine = PressureAccelerationEngine()
ai = AIOpportunityScorer()
optimizer = QuantSignalOptimizer()

vwap_cfg = VWAPConfig()

capital = 200.0
cycle = 0


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _safe(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def discover_symbols():

    try:
        discovered = scanner.scan()
    except Exception:
        discovered = []

    symbols = []
    seen = set()

    for row in discovered:

        if not isinstance(row, dict):
            continue

        venue = str(row.get("venue", "")).upper()
        symbol = str(row.get("symbol", "")).upper()

        if venue != "COINBASE":
            continue

        if symbol in seen:
            continue

        seen.add(symbol)
        symbols.append(symbol)

    if not symbols:
        return BASE_ASSETS[:SEED_COUNT]

    return symbols[:SEED_COUNT]


def fetch_assets(symbols):

    rows = []

    for symbol in symbols:

        try:

            payload = load_runtime_asset(symbol)

            candles = payload.get("candles", [])

            normalized = []

            for c in candles:

                normalized.append(
                    {
                        "open": _safe(getattr(c, "open", 0)),
                        "high": _safe(getattr(c, "high", 0)),
                        "low": _safe(getattr(c, "low", 0)),
                        "close": _safe(getattr(c, "close", 0)),
                        "volume": _safe(getattr(c, "volume", 0)),
                    }
                )

            payload["candles"] = normalized

            rows.append(payload)

        except Exception:
            continue

    return rows


def build_candidates(rows):

    candidates = []

    for row in rows:

        symbol = str(row.get("symbol"))

        candles = row.get("candles", [])

        if len(candles) < 20:
            continue

        price = _safe(row.get("price"))

        vwap = compute_vwap_from_candles(candles, 20)

        if vwap <= 0:
            continue

        spread_bps = ((price - vwap) / vwap) * 10000

        buy_ok, reason = should_buy_mean_reversion(
            price,
            vwap,
            spread_bps,
            vwap_cfg,
        )

        new_row = dict(row)

        new_row.update(
            {
                "symbol": symbol,
                "price": price,
                "vwap": vwap,
                "spread_bps": abs(spread_bps),
                "signal": "BUY" if buy_ok else "HOLD",
                "reason": reason,
            }
        )

        candidates.append(new_row)

    return candidates


print("[CSS] Starting live dashboard...", flush=True)

while True:

    cycle += 1

    try:

        symbols = discover_symbols()

        raw_rows = fetch_assets(symbols)

        candidates = build_candidates(raw_rows)

        features = feature_builder.enrich_rows(candidates, {})

        pressure = pressure_engine.enrich_rows(features)

        accel = accel_engine.enrich(pressure)

        ranked = ai.rank_opportunities(accel)

        optimized = optimizer.optimize(ranked)

        _clear()

        print("==========================================================")
        print("        CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
        print("==========================================================")

        print(f"Cycle: {cycle} | Capital: ${capital:.2f}")
        print("Active Symbols:", ", ".join(symbols))
        print("Timestamp:", now_utc())

        print("\nAI OPPORTUNITY SCANNER")
        print("----------------------------------------------------------")

        for row in optimized[:MAX_DISPLAY]:

            print(
                f"{row['symbol']:10}"
                f" score={row.get('score',0):.2f}"
                f" pressure={row.get('pressure_score',0):.2f}"
                f" accel={row.get('pressure_acceleration',0):.2f}"
                f" trade={row.get('trade_score',0):.2f}"
                f" decision={row.get('decision')}"
            )

        print("\nRefreshing in 10 seconds...")

        time.sleep(SCAN_INTERVAL)

    except KeyboardInterrupt:

        print("\nCSS stopped.")
        break

    except Exception as e:

        print("[CSS ERROR]", e)
        time.sleep(SCAN_INTERVAL)