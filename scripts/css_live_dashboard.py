# =========================
# CSS DASHBOARD (NON-REGRESSION SAFE)
# - Full baseline preserved
# - Scanner process timeout preserved
# - Fallback universe preserved
# - Pipeline preserved
# - Position lifecycle preserved
# - FIX: signal field normalization (pressure/confluence/accel)
# =========================

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

FALLBACK_SYMBOLS = [
    "BTC-USD","ETH-USD","SOL-USD","XRP-USD","ADA-USD",
    "DOGE-USD","AVAX-USD","LINK-USD","LTC-USD","BCH-USD"
]

# =========================
# ENGINES
# =========================

scanner = UnifiedMarketScanner()
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

# =========================
# HELPERS
# =========================

def safe(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_asset(symbol: str) -> str:
    if "_" in symbol: return "FX"
    if "-" in symbol: return "CRYPTO"
    return "OTHER"


def get_open_counts():
    counts = {"FX": 0, "CRYPTO": 0}
    try:
        for s in position_manager.get_open_positions():
            cls = classify_asset(str(s))
            if cls in counts: counts[cls] += 1
    except: pass
    return counts


def can_open(symbol: str):
    counts = get_open_counts()
    cls = classify_asset(symbol)
    if cls == "FX": return counts["FX"] < MAX_OPEN_FX
    if cls == "CRYPTO": return counts["CRYPTO"] < MAX_OPEN_CRYPTO
    return True

# =========================
# SCANNER PROCESS WRAPPER
# =========================

def _scan_worker(q):
    try:
        s = UnifiedMarketScanner()
        q.put(("ok", s.scan() or []))
    except Exception as e:
        q.put(("err", str(e)))

def timed_scan():
    print(f"[STARTUP] scanner.scan() timeout={SCAN_TIMEOUT_SECONDS}s")
    q = mp.Queue()
    p = mp.Process(target=_scan_worker, args=(q,), daemon=True)
    p.start()
    p.join(SCAN_TIMEOUT_SECONDS)

    if p.is_alive():
        p.terminate()
        print("[WARN] scanner timeout → fallback")
        return []

    try:
        status, data = q.get_nowait()
        if status == "ok":
            print(f"[STARTUP] scan OK → {len(data)}")
            return data
    except:
        pass

    print("[WARN] scan failed → fallback")
    return []

def resolve_symbols(discovered):
    syms = list({x["symbol"] for x in discovered if x.get("symbol")})[:MAX_SYMBOLS_PER_CYCLE]
    if syms: return syms
    print("[FALLBACK] using static symbols")
    return FALLBACK_SYMBOLS[:MAX_SYMBOLS_PER_CYCLE]

# =========================
# MAIN LOOP
# =========================

print("[BOOT] CSS dashboard initializing")
print(f"[BOOT] Mode={ENGINE_MODE}")

cycle = 0

while True:
    cycle += 1
    print(f"\n[CYCLE] {cycle}")

    try:
        discovered = timed_scan()
        symbols = resolve_symbols(discovered)

        rows = []
        for s in symbols:
            try:
                raw = load_runtime_asset(s) or {}
                if raw:
                    rows.append({"symbol": s, **raw})
                    print(f"[LOAD-OK] {s}")
            except Exception as e:
                print(f"[LOAD-FAIL] {s}: {e}")

        if not rows:
            time.sleep(REFRESH_SECONDS)
            continue

        # ===== PIPELINE =====
        f = feature_builder.enrich_rows(rows, {})
        r = regime_engine.detect(f)
        p = pressure_engine.enrich_rows(r)
        a = accel_engine.enrich_rows(p)
        c = confluence_engine.enrich_rows(a)
        s = sweep_engine.enrich_rows(c)

        # ===== 🔥 FIX: FIELD NORMALIZATION =====
        for row in s:
            if "pressure" in row:
                row["pressure_score"] = row["pressure"]
            if "confluence" in row:
                row["confluence_score"] = row["confluence"]
            if "accel" in row:
                row["pressure_acceleration"] = row["accel"]

        ranked = ai.rank_opportunities(s)
        optimized = optimizer.optimize(ranked)

        final_rows = []
        for row in optimized:
            sym = row.get("symbol")
            if not sym: continue

            try:
                orch = orchestrator.evaluate_trade(sym, row.get("candles", []))
            except:
                orch = {}

            row["orchestrator_score"] = safe(orch.get("decision_score"))
            row["execute_trade"] = bool(orch.get("execute_trade"))

            final_rows.append(row)

        print("\n--- SIGNAL SNAPSHOT ---")
        for row in final_rows[:5]:
            print(
                row["symbol"],
                "pressure=", round(safe(row.get("pressure_score")),3),
                "accel=", round(safe(row.get("pressure_acceleration")),3),
                "conf=", round(safe(row.get("confluence_score")),3),
                "orch=", round(safe(row.get("orchestrator_score")),3),
            )

        # ===== EXECUTION =====
        opened = 0
        for row in final_rows:
            if opened >= MAX_TRADES_PER_CYCLE: break

            sym = row["symbol"]
            price = safe(row.get("price"))
            orch = safe(row.get("orchestrator_score"))

            if price <= 0 or not can_open(sym): continue

            if not (row.get("execute_trade") or orch >= MODE["score"]):
                continue

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

            trade_logger.log_open(symbol=sym, entry_price=price, quantity=qty)

            print(f"[OPEN] {sym} score={orch:.3f}")
            opened += 1

        closed = position_manager.update_positions(
            latest_prices={r["symbol"]: safe(r.get("price")) for r in final_rows},
            cycle_no=cycle,
            now=now(),
            intelligence_by_symbol={}
        )

        for t in closed:
            print(f"[CLOSE] {t['symbol']}")

        summary = position_manager.summary()
        print("===== CSS DASHBOARD =====")
        print("Cycle:", cycle, "| Open:", summary.get("open_positions_count", 0))

        time.sleep(REFRESH_SECONDS)

    except KeyboardInterrupt:
        print("Stopped")
        break
    except Exception:
        traceback.print_exc()
        time.sleep(5)