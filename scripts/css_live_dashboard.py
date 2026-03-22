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
from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator
from backend.intelligence.vwap_elasticity_engine import VWAPElasticityEngine
from backend.scanner.spread_normalizer import normalize_snapshot_spread
from backend.scanner.unified_market_scanner import UnifiedMarketScanner

# ---------------- CONFIG ----------------

MAX_SYMBOLS_PER_CYCLE = 25
REFRESH_SECONDS = 10
MAX_TRADES_PER_CYCLE = 3

GLOBAL_TAKE_PROFIT_PCT = 0.014
GLOBAL_STOP_LOSS_PCT = 0.012
GLOBAL_MAX_HOLD_CYCLES = 5

BASE_TRADE_NOTIONAL_USD = 10.0

ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)

SUMMARY_FILE = ARTIFACT_DIR / "css_extended_paper_test_summary.json"

# ---------------- ENGINES ----------------

scanner = UnifiedMarketScanner()
feature_builder = FeatureBuilder()
regime_engine = MarketRegimeEngine()
pressure_engine = OpportunityPressureEngine()
accel_engine = PressureAccelerationEngine()
confluence_engine = SignalConfluenceEngine()
elasticity_engine = VWAPElasticityEngine()
sweep_engine = LiquiditySweepDetector()
ai = AIOpportunityScorer()
optimizer = QuantSignalOptimizer()
orchestrator = TradeDecisionOrchestrator()

position_manager = PositionManager(
    take_profit_pct=GLOBAL_TAKE_PROFIT_PCT,
    stop_loss_pct=GLOBAL_STOP_LOSS_PCT,
    max_hold_cycles=GLOBAL_MAX_HOLD_CYCLES,
)

# ---------------- HELPERS ----------------

def now():
    return datetime.now(timezone.utc).isoformat()

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def safe_float(v, d=0.0):
    try:
        return float(v)
    except:
        return d

def normalize_candles(candles):
    out = []
    for c in candles:
        try:
            if isinstance(c, dict):
                out.append(c)
            else:
                out.append({
                    "open": getattr(c, "open", None),
                    "high": getattr(c, "high", None),
                    "low": getattr(c, "low", None),
                    "close": getattr(c, "close", None),
                    "volume": getattr(c, "volume", None),
                })
        except:
            out.append({})
    return out

# ---------------- MAIN ----------------

cycle = 0
equity = 200

print("[CSS] dashboard starting...")

while True:

    cycle += 1

    try:

        discovered = scanner.scan()

        selected = []
        seen = set()

        for raw in discovered:
            sym = str(raw.get("symbol", "")).upper()
            if not sym or sym in seen:
                continue
            selected.append({
                "symbol": sym,
                "venue": raw.get("venue", "UNKNOWN"),
            })
            seen.add(sym)

        selected = selected[:MAX_SYMBOLS_PER_CYCLE]

        rows = []

        for s in selected:
            try:
                payload = load_runtime_asset(s["symbol"])
                payload = normalize_snapshot_spread(payload)

                candles = normalize_candles(payload.get("candles", []))

                if len(candles) < 20:
                    continue

                rows.append({
                    "symbol": s["symbol"],
                    "price": safe_float(payload.get("price")),
                    "vwap": safe_float(payload.get("vwap")),
                    "candles": candles
                })

            except Exception as e:
                print("[FETCH ERROR]", s["symbol"], e)

        if not rows:
            time.sleep(REFRESH_SECONDS)
            continue

        # -------- PIPELINE --------

        features = feature_builder.enrich_rows(rows, {})
        regimes = regime_engine.detect(features)
        pressure = pressure_engine.enrich_rows(regimes)
        accel = accel_engine.enrich_rows(pressure)
        confluence = confluence_engine.enrich_rows(accel)
        elasticity = elasticity_engine.enrich_rows(confluence)
        sweeps = sweep_engine.enrich_rows(elasticity)

        ranked = ai.rank_opportunities(sweeps)
        optimized = optimizer.optimize(ranked)

        # -------- ORCHESTRATOR --------

        decisions = {}
        elite = 0
        passes = 0

        for r in optimized:
            symbol = r["symbol"]
            candles = next((x["candles"] for x in rows if x["symbol"] == symbol), [])

            decision = orchestrator.evaluate_trade(
                asset=symbol,
                candles=candles
            )

            decisions[symbol] = decision

            if decision.get("execute_trade"):
                passes += 1

            if decision.get("signal_tier") == "ELITE":
                elite += 1

        # -------- EXECUTION --------

        opened = 0

        for r in optimized:

            if opened >= MAX_TRADES_PER_CYCLE:
                break

            symbol = r["symbol"]
            price = next((x["price"] for x in rows if x["symbol"] == symbol), 0)

            if price <= 0:
                continue

            if not decisions.get(symbol, {}).get("execute_trade"):
                continue

            qty = BASE_TRADE_NOTIONAL_USD / price

            position_manager.open_long_position(
                symbol=symbol,
                quantity=qty,
                entry_price=price,
                cycle_no=cycle,
                opened_at_utc=now()
            )

            print("[OPEN]", symbol, price)
            opened += 1

        closed = position_manager.update_positions(
            {r["symbol"]: r["price"] for r in rows},
            cycle,
            now()
        )

        for c in closed:
            pnl = safe_float(c.get("realized_pnl_usd"))
            equity += pnl
            print("[CLOSE]", c["symbol"], pnl)

        # -------- DISPLAY --------

        clear()

        print("===== CSS DASHBOARD =====\n")
        print("Cycle:", cycle)
        print("Equity:", round(equity, 2))
        print("Elite signals:", elite)
        print("Orchestrator passes:", passes)
        print("Opened:", opened)

        print("\nTop candidates:")

        for r in optimized[:10]:
            d = decisions.get(r["symbol"], {})
            print(
                r["symbol"],
                "score", round(safe_float(r.get("score", 0)), 3),
                "exec", d.get("execute_trade"),
                "tier", d.get("signal_tier"),
                "decision", round(safe_float(d.get("decision_score")), 3),
                "elasticity", round(safe_float(d.get("elasticity_score")), 3)
            )

        time.sleep(REFRESH_SECONDS)

    except KeyboardInterrupt:
        print("Stopped")
        break

    except Exception as e:
        print("ERROR:", e)
        traceback.print_exc()
        time.sleep(REFRESH_SECONDS)