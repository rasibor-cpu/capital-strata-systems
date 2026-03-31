# === CSS LIVE DASHBOARD – PROFITABILITY UPGRADE (NON-REGRESSION SAFE) ===

from __future__ import annotations

import multiprocessing as mp
import queue
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
from backend.execution.trade_logger import TradeLogger
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.liquidity_sweep_detector import LiquiditySweepDetector
from backend.intelligence.market_regime_engine import MarketRegimeEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine
from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator
from backend.scanner.unified_market_scanner import UnifiedMarketScanner

from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_position_manager import FuturesPositionManager


FUTURES_SYMBOLS = {"ES", "NQ", "CL", "GC", "ZN"}
FUTURES_ENABLED = True


# =========================
# HELPERS
# =========================

def safe(v, d=0.0):
    try:
        return float(v)
    except:
        return d


def now():
    return datetime.now(timezone.utc).isoformat()


def classify_asset(symbol: str):
    if symbol in FUTURES_SYMBOLS:
        return "FUTURES"
    if "_" in symbol:
        return "FX"
    if "-" in symbol:
        return "CRYPTO"
    return "OTHER"


def normalize_candles(candles):
    out = []
    for c in candles or []:
        if isinstance(c, dict):
            out.append(c)
        else:
            out.append({
                "open": getattr(c, "open", 0),
                "high": getattr(c, "high", 0),
                "low": getattr(c, "low", 0),
                "close": getattr(c, "close", 0),
                "volume": getattr(c, "volume", 0),
            })
    return out


# =========================
# 🔥 IMPROVED TRADE FILTER
# =========================

def should_trade(row, orch_score, mode_threshold):

    pressure = safe(row.get("pressure_score"))
    confluence = safe(row.get("confluence_score"))
    accel = safe(row.get("pressure_acceleration"))
    spread = safe(row.get("spread_bps"))
    momentum = safe(row.get("momentum"))

    # ELITE gating
    signal_tier = str(row.get("signal_tier", "WATCH")).upper()
    if signal_tier != "ELITE":
        return False

    # strict filters
    if pressure < 0.30:
        return False

    if confluence < 0.20:
        return False

    if accel <= 0:
        return False

    if spread > 50:
        return False

    if abs(momentum) < 0.002:
        return False

    if orch_score < mode_threshold:
        return False

    return True


# =========================
# MAIN
# =========================

def main():

    print("\n=== SELECT ENGINE MODE ===")
    print("1 SAFE")
    print("2 CONSERVATIVE")
    print("3 BALANCED")
    print("4 AGGRESSIVE")
    print("5 EXPANSION")

    try:
        choice = input("Select: ").strip()
    except:
        choice = "3"

    ENGINE_MODE = {
        "1": "SAFE",
        "2": "CONSERVATIVE",
        "3": "BALANCED",
        "4": "AGGRESSIVE",
        "5": "EXPANSION",
    }.get(choice, "BALANCED")

    MODE = {
        "SAFE": dict(symbols=5, trades=2, score=0.30, capital=5),
        "CONSERVATIVE": dict(symbols=7, trades=3, score=0.24, capital=7),
        "BALANCED": dict(symbols=10, trades=5, score=0.18, capital=10),
        "AGGRESSIVE": dict(symbols=12, trades=6, score=0.15, capital=12),
        "EXPANSION": dict(symbols=15, trades=8, score=0.12, capital=15),
    }[ENGINE_MODE]

    feature_builder = FeatureBuilder()
    regime_engine = MarketRegimeEngine()
    pressure_engine = OpportunityPressureEngine()
    accel_engine = PressureAccelerationEngine()
    confluence_engine = SignalConfluenceEngine()
    sweep_engine = LiquiditySweepDetector()

    ai = AIOpportunityScorer()
    optimizer = QuantSignalOptimizer()
    allocator = CapitalAllocator(total_capital=50, max_positions=5)
    orchestrator = TradeDecisionOrchestrator()

    position_manager = PositionManager()
    trade_logger = TradeLogger()

    futures_adapter = FuturesSimAdapter()
    futures_manager = FuturesPositionManager(futures_adapter)

    cycle = 0
    equity = 200.0

    while True:
        cycle += 1
        print(f"\n[CYCLE] {cycle}")

        try:
            scanner = UnifiedMarketScanner()
            discovered = scanner.scan()

            symbols = [x["symbol"] for x in discovered][:MODE["symbols"]]

            rows = []
            for sym in symbols:
                raw = load_runtime_asset(sym)
                if raw:
                    rows.append(raw)

            enriched = feature_builder.enrich_rows(rows, {})
            enriched = regime_engine.detect(enriched)
            enriched = pressure_engine.enrich_rows(enriched)
            enriched = accel_engine.enrich_rows(enriched)
            enriched = confluence_engine.enrich_rows(enriched)
            enriched = sweep_engine.enrich_rows(enriched)

            ranked = ai.rank_opportunities(enriched)
            optimized = optimizer.optimize(ranked)

            opened = 0

            for row in optimized:

                sym = row["symbol"]
                price = safe(row.get("price"))

                candles = normalize_candles(row.get("candles"))
                decision = orchestrator.evaluate_trade(sym, candles)

                orch_score = safe(decision.get("decision_score"))

                if not should_trade(row, orch_score, MODE["score"]):
                    continue

                if classify_asset(sym) == "FUTURES":

                    # 🔥 dynamic sizing
                    risk_budget = equity * 0.005
                    stop_distance = price * 0.01

                    point_value = {
                        "ES": 50,
                        "NQ": 20,
                        "CL": 1000,
                        "GC": 100,
                        "ZN": 1000,
                    }.get(sym, 50)

                    risk_per_contract = stop_distance * point_value
                    contracts = max(1, int(risk_budget / (risk_per_contract + 1e-9)))

                    result = futures_manager.open_position(
                        symbol=sym,
                        entry_price=price,
                        stop_price=price * 0.99,
                        contracts=contracts,
                        current_equity=equity,
                        state=row,
                    )

                    print("[FUTURES]", sym, result)
                    continue

                # standard execution
                if position_manager.has_open_position(sym):
                    continue

                qty = MODE["capital"] / price

                position_manager.open_long_position(
                    symbol=sym,
                    quantity=qty,
                    entry_price=price,
                    cycle_no=cycle,
                    opened_at_utc=now(),
                    asset_class=classify_asset(sym),
                )

                print(f"[OPEN] {sym} score={round(orch_score,3)}")

                opened += 1
                if opened >= MODE["trades"]:
                    break

            time.sleep(10)

        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    mp.freeze_support()
    main()