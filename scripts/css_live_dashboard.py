# === CSS LIVE DASHBOARD – PROFIT TUNED (STABLE + NON-REGRESSION) ===

from __future__ import annotations

import multiprocessing as mp
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


def choose_engine_mode() -> str:
    print("\n=== SELECT ENGINE MODE ===")
    print("1 SAFE")
    print("2 CONSERVATIVE")
    print("3 BALANCED")
    print("4 AGGRESSIVE")
    print("5 TEST")

    try:
        choice = input("Select: ").strip()
    except Exception:
        choice = "3"

    return {
        "1": "SAFE",
        "2": "CONSERVATIVE",
        "3": "BALANCED",
        "4": "AGGRESSIVE",
        "5": "TEST",
    }.get(choice, "BALANCED")


def safe(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_asset(symbol: str) -> str:
    if symbol in FUTURES_SYMBOLS:
        return "FUTURES"
    if "_" in symbol:
        return "FX"
    if "-" in symbol:
        return "CRYPTO"
    return "OTHER"


def normalize_candles(candles):
    normalized = []
    for c in candles or []:
        try:
            normalized.append({
                "open": float(getattr(c, "open", 0)),
                "high": float(getattr(c, "high", 0)),
                "low": float(getattr(c, "low", 0)),
                "close": float(getattr(c, "close", 0)),
                "volume": float(getattr(c, "volume", 0)),
            })
        except Exception:
            continue
    return normalized


def main() -> None:
    ENGINE_MODE = choose_engine_mode()

    MODE = {
        "SAFE": dict(symbols=5, refresh=15, trades=2, score=0.30, capital=5.0),
        "CONSERVATIVE": dict(symbols=7, refresh=12, trades=3, score=0.28, capital=7.0),
        "BALANCED": dict(symbols=10, refresh=10, trades=3, score=0.32, capital=10.0),
        "AGGRESSIVE": dict(symbols=12, refresh=8, trades=4, score=0.28, capital=12.0),
        "TEST": dict(symbols=15, refresh=6, trades=6, score=0.25, capital=15.0),
    }[ENGINE_MODE]

    feature_builder = FeatureBuilder()
    regime_engine = MarketRegimeEngine()
    pressure_engine = OpportunityPressureEngine()
    accel_engine = PressureAccelerationEngine()
    confluence_engine = SignalConfluenceEngine()
    sweep_engine = LiquiditySweepDetector()

    ai = AIOpportunityScorer()
    optimizer = QuantSignalOptimizer()
    allocator = CapitalAllocator(total_capital=50.0, max_positions=5)
    orchestrator = TradeDecisionOrchestrator()

    position_manager = PositionManager()
    trade_logger = TradeLogger()
    futures_manager = FuturesPositionManager(FuturesSimAdapter())

    cycle = 0
    equity = 200.0

    while True:
        cycle += 1

        try:
            scanner = UnifiedMarketScanner()
            discovered = scanner.scan() or []
            symbols = [x["symbol"] for x in discovered if x.get("symbol")][:MODE["symbols"]]

            rows = []
            for symbol in symbols:
                raw = load_runtime_asset(symbol) or {}
                if raw:
                    rows.append({**raw, "symbol": symbol})

            if not rows:
                time.sleep(MODE["refresh"])
                continue

            f = feature_builder.enrich_rows(rows, {})
            r = regime_engine.detect(f)
            p = pressure_engine.enrich_rows(r)
            a = accel_engine.enrich_rows(p)
            c = confluence_engine.enrich_rows(a)
            s = sweep_engine.enrich_rows(c)

            ranked = ai.rank_opportunities(s)
            optimized = optimizer.optimize(ranked)

            final_rows = []
            for row in optimized:
                sym = row["symbol"]
                normalized = normalize_candles(row.get("candles", []))
                orch = orchestrator.evaluate_trade(sym, normalized)
                row["decision_score"] = safe(orch.get("decision_score"))
                final_rows.append(row)

            opened = 0

            for row in final_rows:

                if opened >= MODE["trades"]:
                    break

                sym = row["symbol"]
                price = safe(row.get("price"))
                score = safe(row.get("decision_score"))

                if price <= 0:
                    continue

                # =========================
                # BALANCED PROFIT FILTER
                # =========================

                if score < MODE["score"]:
                    continue

                if safe(row.get("pressure_score")) < 0.22:
                    continue

                if safe(row.get("pressure_acceleration")) < -0.05:
                    continue

                if safe(row.get("confluence_score")) < 0.12:
                    continue

                # =========================

                qty = MODE["capital"] / price

                if classify_asset(sym) == "FUTURES":
                    result = futures_manager.open_position(
                        symbol=sym,
                        entry_price=price,
                        stop_price=price * 0.995,
                        contracts=1,
                        current_equity=equity,
                        state=row,
                    )
                    print("[FUTURES]", sym, result)
                    continue

                if position_manager.has_open_position(sym):
                    continue

                position_manager.open_long_position(
                    symbol=sym,
                    quantity=qty,
                    entry_price=price,
                    cycle_no=cycle,
                    opened_at_utc=now(),
                    asset_class=classify_asset(sym),
                )

                print("[OPEN]", sym, round(score, 3))
                opened += 1

            time.sleep(MODE["refresh"])

        except KeyboardInterrupt:
            break
        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    mp.freeze_support()
    main()