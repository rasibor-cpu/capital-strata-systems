from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.coinbase_historical_downloader import load_runtime_universe
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.signal_confluence_engine import SignalConfluenceEngine
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.pressure_acceleration_engine import PressureAccelerationEngine
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer
from backend.execution.position_manager import PositionManager
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.intelligence.vwap_elasticity_engine import VWAPElasticityEngine


# ============================================================
# CSS LIVE DASHBOARD — REAL DATA BASELINE (NON-REGRESSION)
# ============================================================

PRODUCTS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD",
    "DOGE-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "BCH-USD",
    "EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD",
    "ES", "NQ", "CL", "GC", "ZN"
]

MODE_PROFILES: Dict[str, Dict[str, float]] = {
    "SAFE": {
        "elite": 0.72,
        "qualified": 0.60,
        "watch": 0.50,
        "min_vwap_dev": 0.0055,
        "max_spread": 14.0,
        "min_elasticity_watch": 0.24,
        "min_ai_score": 0.60,
        "min_pressure_score": 0.18,
        "min_confluence_score": 0.18,
        "max_positions": 2,
    },
    "CONSERVATIVE": {
        "elite": 0.68,
        "qualified": 0.56,
        "watch": 0.47,
        "min_vwap_dev": 0.0050,
        "max_spread": 16.0,
        "min_elasticity_watch": 0.22,
        "min_ai_score": 0.56,
        "min_pressure_score": 0.15,
        "min_confluence_score": 0.16,
        "max_positions": 3,
    },
    "BALANCED": {
        "elite": 0.60,
        "qualified": 0.50,
        "watch": 0.42,
        "min_vwap_dev": 0.0040,
        "max_spread": 18.0,
        "min_elasticity_watch": 0.18,
        "min_ai_score": 0.50,
        "min_pressure_score": 0.12,
        "min_confluence_score": 0.12,
        "max_positions": 5,
    },
    "AGGRESSIVE": {
        "elite": 0.56,
        "qualified": 0.46,
        "watch": 0.38,
        "min_vwap_dev": 0.0034,
        "max_spread": 22.0,
        "min_elasticity_watch": 0.15,
        "min_ai_score": 0.44,
        "min_pressure_score": 0.10,
        "min_confluence_score": 0.10,
        "max_positions": 6,
    },
    "EXPANSION": {
        "elite": 0.52,
        "qualified": 0.42,
        "watch": 0.34,
        "min_vwap_dev": 0.0028,
        "max_spread": 26.0,
        "min_elasticity_watch": 0.12,
        "min_ai_score": 0.40,
        "min_pressure_score": 0.08,
        "min_confluence_score": 0.08,
        "max_positions": 8,
    },
}

MAX_WATCH_TRADES = 2
DEFAULT_TOTAL_CAPITAL = 1000.0
DEFAULT_LOOKBACK_DAYS = 3
CYCLE_SLEEP_SECONDS = 5


def select_mode() -> str:
    print("\n=== SELECT ENGINE MODE ===")
    print("1. SAFE")
    print("2. CONSERVATIVE")
    print("3. BALANCED")
    print("4. AGGRESSIVE")
    print("5. EXPANSION")
    raw = input("Select mode [1-5, default=3]: ").strip()

    mapping = {
        "1": "SAFE",
        "2": "CONSERVATIVE",
        "3": "BALANCED",
        "4": "AGGRESSIVE",
        "5": "EXPANSION",
    }
    selected = mapping.get(raw, "BALANCED")
    print(f"[MODE] {selected}")
    return selected


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_symbol(row: Dict[str, Any]) -> str:
    return str(row.get("symbol", "UNKNOWN"))


def call_metric(engine: Any, row: Dict[str, Any]) -> float:
    for name in ("compute", "score", "evaluate", "calculate", "detect"):
        fn = getattr(engine, name, None)
        if callable(fn):
            try:
                result = fn(row)
                if isinstance(result, dict):
                    for key in ("score", "value", "result", "elasticity_score"):
                        if key in result:
                            return safe_float(result[key])
                    return 0.0
                return safe_float(result)
            except Exception:
                continue
    return 0.0


def expected_move_bps(row: Dict[str, Any]) -> float:
    return abs(safe_float(row.get("vwap_dev"))) * 10000.0


def is_profitable(row: Dict[str, Any], edge_buffer_bps: float = 2.0) -> bool:
    spread_bps = safe_float(row.get("spread_bps"))
    move_bps = expected_move_bps(row)
    return move_bps > (spread_bps + edge_buffer_bps)


def get_trade_score(row: Dict[str, Any]) -> float:
    # Prefer existing trade_score if upstream modules already calculate it.
    existing = safe_float(row.get("trade_score"), default=-999.0)
    if existing > -998.0:
        return existing

    ai_score = safe_float(row.get("score"))
    elasticity_score = safe_float(row.get("elasticity_score"))
    pressure_score = safe_float(row.get("pressure_score"))
    confluence_score = safe_float(row.get("confluence_score"))
    acceleration_score = safe_float(row.get("acceleration_score"))
    move_bps = expected_move_bps(row)
    spread_bps = safe_float(row.get("spread_bps"))

    synthetic = (
        ai_score * 0.40
        + elasticity_score * 0.15
        + pressure_score * 0.15
        + confluence_score * 0.15
        + acceleration_score * 0.10
        + min(move_bps / 100.0, 1.0) * 0.10
        - min(spread_bps / 100.0, 1.0) * 0.05
    )
    return synthetic


def summarize_row(row: Dict[str, Any]) -> str:
    symbol = safe_symbol(row)
    score = safe_float(row.get("score"))
    elasticity_score = safe_float(row.get("elasticity_score"))
    pressure_score = safe_float(row.get("pressure_score"))
    confluence_score = safe_float(row.get("confluence_score"))
    acceleration_score = safe_float(row.get("acceleration_score"))
    spread_bps = safe_float(row.get("spread_bps"))
    vwap_dev = safe_float(row.get("vwap_dev"))
    tier = str(row.get("signal_tier", "UNKNOWN"))
    trade_score = get_trade_score(row)

    return (
        f"[{tier}] {symbol} | "
        f"score={score:.4f} | "
        f"trade_score={trade_score:.4f} | "
        f"elasticity={elasticity_score:.4f} | "
        f"pressure={pressure_score:.4f} | "
        f"confluence={confluence_score:.4f} | "
        f"accel={acceleration_score:.4f} | "
        f"vwap_dev={vwap_dev:.5f} | "
        f"spread={spread_bps:.2f}"
    )


def open_trade(pm: PositionManager, trade: Dict[str, Any]) -> bool:
    symbol = safe_symbol(trade)
    capital = safe_float(trade.get("capital"))
    trade_score = get_trade_score(trade)
    print(
        f"[SIMULATED EXECUTION] {symbol} | capital={capital:.2f} | "
        f"trade_score={trade_score:.4f}"
    )
    return True


def get_open_positions_count(pm: PositionManager) -> int:
    try:
        if hasattr(pm, "get_open_positions") and callable(pm.get_open_positions):
            positions = pm.get_open_positions()
            if isinstance(positions, list):
                return len(positions)
        if hasattr(pm, "open_positions"):
            positions = getattr(pm, "open_positions")
            if isinstance(positions, list):
                return len(positions)
            if isinstance(positions, dict):
                return len(positions)
    except Exception:
        pass
    return 0


def enrich_rows(
    rows: List[Dict[str, Any]],
    scorer: AIOpportunityScorer,
    confluence: SignalConfluenceEngine,
    pressure: OpportunityPressureEngine,
    accel: PressureAccelerationEngine,
    elasticity: VWAPElasticityEngine,
    optimizer: QuantSignalOptimizer,
) -> List[Dict[str, Any]]:
    decisions: List[Dict[str, Any]] = []

    for row in rows:
        row["elasticity_score"] = call_metric(elasticity, row)
        row["pressure_score"] = call_metric(pressure, row)
        row["confluence_score"] = call_metric(confluence, row)
        row["acceleration_score"] = call_metric(accel, row)

        try:
            row["score"] = safe_float(scorer.score(row))
        except Exception:
            row["score"] = 0.0

        try:
            row["signal_tier"] = optimizer.classify(row)
        except Exception:
            row["signal_tier"] = "IGNORE"

        row["trade_score"] = get_trade_score(row)

        print(summarize_row(row))
        decisions.append(row)

    return decisions


def select_primary_trades(
    decisions: List[Dict[str, Any]],
    profile: Dict[str, float],
) -> List[Dict[str, Any]]:
    tradable: List[Dict[str, Any]] = []

    for row in decisions:
        tier = str(row.get("signal_tier", "IGNORE"))
        spread_bps = safe_float(row.get("spread_bps"))
        vwap_dev = abs(safe_float(row.get("vwap_dev")))
        ai_score = safe_float(row.get("score"))
        pressure_score = safe_float(row.get("pressure_score"))
        confluence_score = safe_float(row.get("confluence_score"))

        if tier not in ("ELITE", "QUALIFIED"):
            continue
        if spread_bps > profile["max_spread"]:
            continue
        if vwap_dev < profile["min_vwap_dev"]:
            continue
        if ai_score < profile["min_ai_score"]:
            continue
        if pressure_score < profile["min_pressure_score"]:
            continue
        if confluence_score < profile["min_confluence_score"]:
            continue
        if not is_profitable(row):
            continue

        tradable.append(row)

    tradable.sort(
        key=lambda x: (
            get_trade_score(x),
            safe_float(x.get("score")),
            safe_float(x.get("elasticity_score")),
            abs(safe_float(x.get("vwap_dev")))
        ),
        reverse=True
    )
    return tradable


def select_watch_fallback(
    decisions: List[Dict[str, Any]],
    profile: Dict[str, float],
) -> List[Dict[str, Any]]:
    watch = [
        row for row in decisions
        if str(row.get("signal_tier", "IGNORE")) == "WATCH"
        and safe_float(row.get("spread_bps")) <= profile["max_spread"]
        and abs(safe_float(row.get("vwap_dev"))) >= profile["min_vwap_dev"] * 0.60
        and safe_float(row.get("elasticity_score")) >= profile["min_elasticity_watch"]
        and safe_float(row.get("score")) >= max(profile["min_ai_score"] * 0.90, 0.0)
        and is_profitable(row)
    ]

    watch.sort(
        key=lambda x: (
            get_trade_score(x),
            safe_float(x.get("elasticity_score")),
            abs(safe_float(x.get("vwap_dev")))
        ),
        reverse=True
    )
    return watch[:MAX_WATCH_TRADES]


def run_dashboard() -> None:
    print("\n=== CSS REAL DATA ENGINE STARTING ===\n")

    mode = select_mode()
    profile = MODE_PROFILES[mode]

    scorer = AIOpportunityScorer()
    confluence = SignalConfluenceEngine()
    pressure = OpportunityPressureEngine()
    accel = PressureAccelerationEngine()
    elasticity = VWAPElasticityEngine()
    optimizer = QuantSignalOptimizer(profile=profile)
    allocator = CapitalAllocator(
        total_capital=DEFAULT_TOTAL_CAPITAL,
        max_positions=int(profile["max_positions"]),
    )
    pm = PositionManager()

    cycle = 0

    while True:
        try:
            cycle += 1
            print("\n================================================")
            print(f"--- NEW CYCLE #{cycle} (REAL DATA | MODE={mode}) ---")
            print("================================================")

            open_positions = get_open_positions_count(pm)
            max_positions = int(profile["max_positions"])
            remaining_capacity = max(max_positions - open_positions, 0)

            print(f"[POSITIONS] open={open_positions} | max={max_positions} | remaining={remaining_capacity}")

            if remaining_capacity <= 0:
                print("[LIMIT] No remaining position capacity this cycle.")
                time.sleep(CYCLE_SLEEP_SECONDS)
                continue

            rows = load_runtime_universe(PRODUCTS, days=DEFAULT_LOOKBACK_DAYS)
            print(f"[DATA] Loaded assets: {len(rows)}")

            if not rows:
                print("[WARN] No rows returned from load_runtime_universe().")
                time.sleep(CYCLE_SLEEP_SECONDS)
                continue

            decisions = enrich_rows(
                rows=rows,
                scorer=scorer,
                confluence=confluence,
                pressure=pressure,
                accel=accel,
                elasticity=elasticity,
                optimizer=optimizer,
            )

            tradable = select_primary_trades(decisions, profile)

            if not tradable:
                print("[FALLBACK] No ELITE/QUALIFIED tradable rows. Checking WATCH candidates...")
                tradable = select_watch_fallback(decisions, profile)

            tradable = tradable[:remaining_capacity]

            print(f"[FILTER] Tradable after gating: {len(tradable)}")

            if tradable:
                for idx, row in enumerate(tradable, start=1):
                    print(
                        f"[TRADABLE {idx}] {safe_symbol(row)} | "
                        f"tier={row.get('signal_tier')} | "
                        f"trade_score={get_trade_score(row):.4f} | "
                        f"spread={safe_float(row.get('spread_bps')):.2f} | "
                        f"vwap_dev={safe_float(row.get('vwap_dev')):.5f}"
                    )

            allocations = allocator.allocate(tradable, rows)
            print(f"[ALLOCATOR] Allocated: {len(allocations)}")

            opened = 0
            for trade in allocations[:remaining_capacity]:
                if open_trade(pm, trade):
                    opened += 1

            print(f"[RESULT] Opened this cycle: {opened}")
            print("[STATUS] Cycle complete.\n")

            time.sleep(CYCLE_SLEEP_SECONDS)

        except KeyboardInterrupt:
            print("\nStopping dashboard...")
            break
        except Exception as exc:
            print(f"ERROR: {exc}")
            traceback.print_exc()
            time.sleep(2)


if __name__ == "__main__":
    run_dashboard()