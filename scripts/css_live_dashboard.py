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
# HELPERS
# =========================

def safe(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_signal_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    row["pressure_score"] = safe(row.get("pressure_score") or row.get("pressure"))
    row["confluence_score"] = safe(row.get("confluence_score") or row.get("confluence"))
    row["pressure_acceleration"] = safe(
        row.get("pressure_acceleration") or row.get("accel") or row.get("acceleration_score")
    )

    row["pressure"] = row["pressure_score"]
    row["confluence"] = row["confluence_score"]
    row["accel"] = row["pressure_acceleration"]

    return row


# =========================
# SCANNER
# =========================

def _scan_worker(out_q: mp.Queue):
    try:
        scanner = UnifiedMarketScanner()
        result = scanner.scan() or []
        out_q.put(result)
    except Exception:
        out_q.put([])


def timed_scan(timeout=20):
    q = mp.Queue()
    p = mp.Process(target=_scan_worker, args=(q,))
    p.start()
    p.join(timeout)

    if p.is_alive():
        p.terminate()
        print("[WARN] scanner timeout -> fallback")
        return []

    try:
        return q.get_nowait()
    except Exception:
        return []


# =========================
# MAIN
# =========================

def main():
    mode = "BALANCED"

    MAX_SYMBOLS = 10
    REFRESH = 10

    fallback = [
        "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
        "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD",
        "LTC-USD", "BCH-USD"
    ]

    fb = FeatureBuilder()
    re = MarketRegimeEngine()
    pe = OpportunityPressureEngine()
    ae = PressureAccelerationEngine()
    ce = SignalConfluenceEngine()
    se = LiquiditySweepDetector()

    ai = AIOpportunityScorer()
    opt = QuantSignalOptimizer()
    alloc = CapitalAllocator(total_capital=50, max_positions=5)
    orch = TradeDecisionOrchestrator()

    pm = PositionManager()
    tl = TradeLogger()

    cycle = 0

    while True:
        cycle += 1
        print(f"\n[CYCLE] {cycle} starting")

        discovered = timed_scan()
        symbols = list({x["symbol"] for x in discovered if isinstance(x, dict) and x.get("symbol")})[:MAX_SYMBOLS]

        if not symbols:
            print("[FALLBACK] using static symbols")
            symbols = fallback

        rows = []

        for s in symbols:
            data = load_runtime_asset(s) or {}
            candles = data.get("candles") or []
            print(f"[LOAD] {s} candles={len(candles)}")

            rows.append({"symbol": s, **data})

        if not rows:
            time.sleep(REFRESH)
            continue

        f = fb.enrich_rows(rows, {})
        r = re.detect(f)
        p = pe.enrich_rows(r)
        a = ae.enrich_rows(p)
        c = ce.enrich_rows(a)
        s_rows = se.enrich_rows(c)

        # normalize BEFORE ranking
        s_rows = [normalize_signal_fields(dict(x)) for x in s_rows]

        ranked = ai.rank_opportunities(s_rows)

        # normalize AGAIN after ranking
        ranked = [normalize_signal_fields(dict(x)) for x in ranked]

        optimized = opt.optimize(ranked)

        # 🔥 CRITICAL FIX: use enriched rows
        full_map = {row["symbol"]: dict(row) for row in s_rows}

        final_rows = []
        for row in optimized:
            sym = row.get("symbol")
            merged = {**full_map.get(sym, {}), **row}
            merged = normalize_signal_fields(merged)

            try:
                orch_out = orch.evaluate_trade(sym, merged.get("candles", []))
            except Exception:
                orch_out = {"decision_score": 0.0, "execute_trade": False}

            merged["orch"] = safe(orch_out.get("decision_score"))

            final_rows.append(merged)

        print("\n--- SIGNAL SNAPSHOT ---")
        for r in final_rows[:5]:
            print(
                r["symbol"],
                "pressure=", round(r["pressure_score"], 3),
                "accel=", round(r["pressure_acceleration"], 3),
                "conf=", round(r["confluence_score"], 3),
                "orch=", round(r["orch"], 3),
            )

        print("\n===== CSS DASHBOARD =====")
        print(f"Cycle: {cycle}")

        time.sleep(REFRESH)


if __name__ == "__main__":
    mp.freeze_support()
    main()