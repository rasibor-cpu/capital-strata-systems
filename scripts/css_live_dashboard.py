# === CSS LIVE DASHBOARD – FULL PIPELINE + FUTURES (NON-REGRESSION SAFE) ===

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

# ✅ FUTURES (ADDITIVE ONLY)
from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_position_manager import FuturesPositionManager

FUTURES_SYMBOLS = {"ES", "NQ", "CL", "GC", "ZN"}
FUTURES_ENABLED = True


# =========================
# MODE CONTROL
# =========================

def choose_engine_mode() -> str:
    print("\n=== SELECT ENGINE MODE ===")
    print("1 SAFE")
    print("2 CONSERVATIVE")
    print("3 BALANCED")
    print("4 AGGRESSIVE")
    print("5 EXPANSION")

    try:
        choice = input("Select: ").strip()
    except Exception:
        choice = "3"

    return {
        "1": "SAFE",
        "2": "CONSERVATIVE",
        "3": "BALANCED",
        "4": "AGGRESSIVE",
        "5": "EXPANSION",
    }.get(choice, "BALANCED")


# =========================
# HELPERS
# =========================

def safe(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
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


# =========================
# MAIN APP
# =========================

def main() -> None:

    ENGINE_MODE = choose_engine_mode()

    MODE = {
        "SAFE": dict(symbols=5, refresh=15, trades=2, score=0.30, capital=5.0, fx=2, crypto=1),
        "CONSERVATIVE": dict(symbols=7, refresh=12, trades=3, score=0.24, capital=7.0, fx=3, crypto=1),
        "BALANCED": dict(symbols=10, refresh=10, trades=5, score=0.18, capital=10.0, fx=4, crypto=2),
        "AGGRESSIVE": dict(symbols=12, refresh=8, trades=6, score=0.15, capital=12.0, fx=5, crypto=3),
        "EXPANSION": dict(symbols=15, refresh=6, trades=8, score=0.12, capital=15.0, fx=6, crypto=4),
    }[ENGINE_MODE]

    MAX_SYMBOLS_PER_CYCLE = int(MODE["symbols"])
    REFRESH_SECONDS = int(MODE["refresh"])
    MAX_TRADES_PER_CYCLE = int(MODE["trades"])
    BASE_TRADE_NOTIONAL_USD = float(MODE["capital"])
    MAX_OPEN_FX = int(MODE["fx"])
    MAX_OPEN_CRYPTO = int(MODE["crypto"])
    SCAN_TIMEOUT_SECONDS = 20

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

    # ✅ FUTURES ENGINE
    futures_adapter = FuturesSimAdapter()
    futures_manager = FuturesPositionManager(futures_adapter)

    print("[BOOT] CSS dashboard initializing")

    cycle = 0
    equity = 200.0

    while True:
        cycle += 1

        try:
            print(f"\n[CYCLE] {cycle} starting")

            scanner = UnifiedMarketScanner()
            discovered = scanner.scan() or []

            symbols = [x["symbol"] for x in discovered][:MAX_SYMBOLS_PER_CYCLE]

            rows = []
            for symbol in symbols:
                raw = load_runtime_asset(symbol) or {}
                if raw:
                    rows.append({**raw, "symbol": symbol})

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
                decision = orchestrator.evaluate_trade(sym, row.get("candles", []))

                if not decision.get("execute_trade"):
                    continue

                if price <= 0:
                    continue

                # =========================
                # 🔥 FUTURES ROUTING
                # =========================
                if sym in FUTURES_SYMBOLS and FUTURES_ENABLED:

                    result = futures_manager.open_position(
                        symbol=sym,
                        entry_price=price,
                        stop_price=price * 0.99,
                        contracts=1,
                        current_equity=equity,
                        state=row,
                    )

                    print("[FUTURES OPEN]", sym, result)
                    continue

                # =========================
                # EXISTING EXECUTION (UNCHANGED)
                # =========================
                if position_manager.has_open_position(sym):
                    continue

                qty = BASE_TRADE_NOTIONAL_USD / price

                position_manager.open_long_position(
                    symbol=sym,
                    quantity=qty,
                    entry_price=price,
                    cycle_no=cycle,
                    opened_at_utc=now(),
                    asset_class=classify_asset(sym),
                )

                trade_logger.log_open(
                    symbol=sym,
                    entry_price=price,
                    quantity=qty,
                    score=safe(row.get("score")),
                    signal=f"MODE_{ENGINE_MODE}",
                    regime=row.get("regime", "NA"),
                )

                print(f"[OPEN] {sym}")
                opened += 1

                if opened >= MAX_TRADES_PER_CYCLE:
                    break

            time.sleep(REFRESH_SECONDS)

        except KeyboardInterrupt:
            print("\n[STOP] Interrupted")
            break
        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    mp.freeze_support()
    main()