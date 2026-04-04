from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

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


# ============================================================
# CSS LIVE DASHBOARD — REAL DATA RECOVERY BASELINE
# ============================================================

PRODUCTS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD",
    "ES", "NQ", "CL", "GC", "ZN"
]

MODE_PROFILES: Dict[str, Dict[str, float]] = {
    "SAFE": {
        "elite": 0.70,
        "qualified": 0.58,
        "watch": 0.48,
        "min_ai": 0.25,
        "min_pressure": 0.03,
        "min_vwap_dev": 0.0008,
        "max_spread": 16.0,
        "min_elasticity_watch": 0.08,
        "max_positions": 2,
        "watch_slots": 1,
    },
    "CONSERVATIVE": {
        "elite": 0.64,
        "qualified": 0.52,
        "watch": 0.42,
        "min_ai": 0.18,
        "min_pressure": 0.02,
        "min_vwap_dev": 0.0006,
        "max_spread": 18.0,
        "min_elasticity_watch": 0.06,
        "max_positions": 3,
        "watch_slots": 1,
    },
    "BALANCED": {
        "elite": 0.58,
        "qualified": 0.46,
        "watch": 0.34,
        "min_ai": 0.10,
        "min_pressure": 0.00,
        "min_vwap_dev": 0.00025,
        "max_spread": 20.0,
        "min_elasticity_watch": 0.03,
        "max_positions": 5,
        "watch_slots": 2,
    },
    "AGGRESSIVE": {
        "elite": 0.52,
        "qualified": 0.40,
        "watch": 0.28,
        "min_ai": 0.07,
        "min_pressure": 0.00,
        "min_vwap_dev": 0.00015,
        "max_spread": 24.0,
        "min_elasticity_watch": 0.02,
        "max_positions": 6,
        "watch_slots": 2,
    },
    "EXPANSION": {
        "elite": 0.48,
        "qualified": 0.34,
        "watch": 0.24,
        "min_ai": 0.05,
        "min_pressure": 0.00,
        "min_vwap_dev": 0.00010,
        "max_spread": 28.0,
        "min_elasticity_watch": 0.01,
        "max_positions": 8,
        "watch_slots": 3,
    },
}

DEFAULT_TOTAL_CAPITAL = 1000.0
DEFAULT_LOOKBACK_DAYS = 3
CYCLE_SLEEP_SECONDS = 5


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def select_mode() -> str:
    print("\n=== SELECT ENGINE MODE ===")
    print("1 SAFE")
    print("2 CONSERVATIVE")
    print("3 BALANCED")
    print("4 AGGRESSIVE")
    print("5 EXPANSION")

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


def ensure_vwap_dev(row: Dict[str, Any]) -> Dict[str, Any]:
    existing = row.get("vwap_dev")
    if existing is not None:
        row["vwap_dev"] = safe_float(existing)
        return row

    price = safe_float(row.get("price"))
    vwap = safe_float(row.get("vwap"))

    if vwap > 0:
        row["vwap_dev"] = (price - vwap) / vwap
    else:
        row["vwap_dev"] = 0.0
    return row


def compute_elasticity(row: Dict[str, Any]) -> float:
    vwap_dev = abs(safe_float(row.get("vwap_dev")))
    momentum = abs(
        safe_float(
            row.get("momentum"),
            safe_float(row.get("price_change"), 0.0)
        )
    )
    denom = momentum if momentum > 1e-6 else 1e-3
    elasticity = vwap_dev / denom
    return min(elasticity, 50.0)


def is_profitable(row: Dict[str, Any], edge_buffer_bps: float = 2.0) -> bool:
    spread_bps = safe_float(row.get("spread_bps"))
    move_bps = abs(safe_float(row.get("vwap_dev"))) * 10000.0
    return move_bps > (spread_bps + edge_buffer_bps)


def call_metric(engine: Any, row: Dict[str, Any]) -> float:
    for name in ("compute", "score", "evaluate", "calculate", "detect"):
        fn = getattr(engine, name, None)
        if callable(fn):
            try:
                result = fn(row)
                if isinstance(result, dict):
                    for key in ("score", "value", "result"):
                        if key in result:
                            return safe_float(result[key])
                    return 0.0
                return safe_float(result)
            except Exception:
                continue
    return 0.0


def derive_trade_score(row: Dict[str, Any]) -> float:
    ai_score = safe_float(row.get("score"))
    pressure_score = safe_float(row.get("pressure_score"))
    confluence_score = safe_float(row.get("confluence_score"))
    acceleration_score = safe_float(row.get("acceleration_score"))
    elasticity_score = safe_float(row.get("elasticity_score"))
    vwap_dev = abs(safe_float(row.get("vwap_dev")))
    spread_bps = safe_float(row.get("spread_bps"))

    move_component = min(vwap_dev * 1000.0, 2.0)
    elasticity_component = min(elasticity_score / 10.0, 1.0)
    spread_penalty = min(spread_bps / 50.0, 1.0)

    score = (
        ai_score * 0.45
        + pressure_score * 0.10
        + confluence_score * 0.10
        + acceleration_score * 0.10
        + elasticity_component * 0.15
        + move_component * 0.15
        - spread_penalty * 0.05
    )
    return score


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


def open_trade(pm: PositionManager, trade: Dict[str, Any]) -> bool:
    symbol = str(trade.get("symbol", "UNKNOWN"))
    capital = safe_float(trade.get("capital"))
    trade_score = safe_float(trade.get("trade_score"))
    tier = str(trade.get("signal_tier", "UNKNOWN"))
    print(
        f"[SIM EXEC] {symbol} | tier={tier} | capital={capital:.2f} | "
        f"trade_score={trade_score:.4f}"
    )
    return True


def enrich_rows(
    rows: List[Dict[str, Any]],
    scorer: AIOpportunityScorer,
    confluence: SignalConfluenceEngine,
    pressure: OpportunityPressureEngine,
    accel: PressureAccelerationEngine,
    optimizer: QuantSignalOptimizer,
) -> List[Dict[str, Any]]:
    decisions: List[Dict[str, Any]] = []

    for row in rows:
        row = ensure_vwap_dev(row)

        row["pressure_score"] = call_metric(pressure, row)
        row["confluence_score"] = call_metric(confluence, row)
        row["acceleration_score"] = call_metric(accel, row)
        row["elasticity_score"] = compute_elasticity(row)

        score = safe_float(scorer.score(row))
        if score < 0.01:
            score *= 100.0
        row["score"] = score

        try:
            row["signal_tier"] = optimizer.classify(row)
        except Exception:
            row["signal_tier"] = "IGNORE"

        row["trade_score"] = derive_trade_score(row)

        print(
            f"[{row['signal_tier']}] {row.get('symbol')} | "
            f"score={row['score']:.4f} | "
            f"elasticity={row['elasticity_score']:.4f} | "
            f"vwap_dev={safe_float(row.get('vwap_dev')):.5f} | "
            f"trade_score={row['trade_score']:.4f} | "
            f"spread={safe_float(row.get('spread_bps')):.2f}"
        )

        decisions.append(row)

    return decisions


def select_primary_trades(
    decisions: List[Dict[str, Any]],
    profile: Dict[str, float],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    tradable: List[Dict[str, Any]] = []
    reject_counts = {
        "tier": 0,
        "spread": 0,
        "vwap": 0,
        "ai": 0,
        "pressure": 0,
        "profit": 0,
    }

    for row in decisions:
        tier = str(row.get("signal_tier", "IGNORE"))
        spread_bps = safe_float(row.get("spread_bps"))
        vwap_dev = abs(safe_float(row.get("vwap_dev")))
        ai_score = safe_float(row.get("score"))
        pressure_score = safe_float(row.get("pressure_score"))

        if tier not in ("ELITE", "QUALIFIED"):
            reject_counts["tier"] += 1
            continue
        if spread_bps > profile["max_spread"]:
            reject_counts["spread"] += 1
            continue
        if vwap_dev < profile["min_vwap_dev"]:
            reject_counts["vwap"] += 1
            continue
        if ai_score < profile["min_ai"]:
            reject_counts["ai"] += 1
            continue
        if pressure_score < profile["min_pressure"]:
            reject_counts["pressure"] += 1
            continue
        if not is_profitable(row):
            reject_counts["profit"] += 1
            continue

        tradable.append(row)

    tradable.sort(
        key=lambda x: (
            safe_float(x.get("trade_score")),
            safe_float(x.get("score")),
            safe_float(x.get("elasticity_score")),
            abs(safe_float(x.get("vwap_dev"))),
        ),
        reverse=True,
    )
    return tradable, reject_counts


def select_watch_fallback(
    decisions: List[Dict[str, Any]],
    profile: Dict[str, float],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    watch: List[Dict[str, Any]] = []
    reject_counts = {
        "tier": 0,
        "spread": 0,
        "vwap": 0,
        "elasticity": 0,
        "ai": 0,
        "profit": 0,
    }

    for row in decisions:
        if str(row.get("signal_tier", "IGNORE")) != "WATCH":
            reject_counts["tier"] += 1
            continue
        if safe_float(row.get("spread_bps")) > profile["max_spread"]:
            reject_counts["spread"] += 1
            continue
        if abs(safe_float(row.get("vwap_dev"))) < profile["min_vwap_dev"] * 0.25:
            reject_counts["vwap"] += 1
            continue
        if safe_float(row.get("elasticity_score")) < profile["min_elasticity_watch"]:
            reject_counts["elasticity"] += 1
            continue
        if safe_float(row.get("score")) < profile["min_ai"] * 0.80:
            reject_counts["ai"] += 1
            continue

        # Recovery mode:
        # allow strong watch setups through if either profitability passes
        # OR trade_score is sufficiently strong.
        profitable = is_profitable(row)
        strong_watch = safe_float(row.get("trade_score")) >= 0.18

        if not (profitable or strong_watch):
            reject_counts["profit"] += 1
            continue

        watch.append(row)

    watch.sort(
        key=lambda x: (
            safe_float(x.get("trade_score")),
            safe_float(x.get("score")),
            safe_float(x.get("elasticity_score")),
            abs(safe_float(x.get("vwap_dev"))),
        ),
        reverse=True,
    )
    return watch[: int(profile.get("watch_slots", 2))], reject_counts


def run_dashboard() -> None:
    print("\n=== CSS REAL DATA ENGINE STARTING ===\n")

    mode = select_mode()
    profile = MODE_PROFILES[mode]

    scorer = AIOpportunityScorer()
    confluence = SignalConfluenceEngine()
    pressure = OpportunityPressureEngine()
    accel = PressureAccelerationEngine()
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
            print("\n--- NEW CYCLE ---")

            open_positions = get_open_positions_count(pm)
            max_positions = int(profile["max_positions"])
            remaining_capacity = max(max_positions - open_positions, 0)

            rows = load_runtime_universe(PRODUCTS, days=DEFAULT_LOOKBACK_DAYS)
            print(f"[DATA] Loaded assets: {len(rows)}")
            print(
                f"[POSITIONS] open={open_positions} | "
                f"max={max_positions} | remaining={remaining_capacity}"
            )

            if not rows:
                print("[WARN] No rows returned.")
                time.sleep(CYCLE_SLEEP_SECONDS)
                continue

            decisions = enrich_rows(
                rows=rows,
                scorer=scorer,
                confluence=confluence,
                pressure=pressure,
                accel=accel,
                optimizer=optimizer,
            )

            tradable, primary_rejects = select_primary_trades(decisions, profile)
            print(f"[PRIMARY REJECTS] {primary_rejects}")

            if not tradable:
                print("Fallback: checking WATCH candidates...")
                tradable, watch_rejects = select_watch_fallback(decisions, profile)
                print(f"[WATCH REJECTS] {watch_rejects}")

            tradable = tradable[:remaining_capacity]

            print(f"Tradable: {len(tradable)}")

            if tradable:
                for idx, row in enumerate(tradable, start=1):
                    print(
                        f"[TRADABLE {idx}] {row.get('symbol')} | "
                        f"tier={row.get('signal_tier')} | "
                        f"score={safe_float(row.get('score')):.4f} | "
                        f"trade_score={safe_float(row.get('trade_score')):.4f} | "
                        f"vwap_dev={safe_float(row.get('vwap_dev')):.5f} | "
                        f"elasticity={safe_float(row.get('elasticity_score')):.4f}"
                    )

            allocations = allocator.allocate(tradable, rows)
            print(f"Allocated: {len(allocations)}")

            opened = 0
            for trade in allocations[:remaining_capacity]:
                trade["trade_score"] = safe_float(trade.get("trade_score"))
                if open_trade(pm, trade):
                    opened += 1

            print(f"Opened: {opened}")
            time.sleep(CYCLE_SLEEP_SECONDS)

        except KeyboardInterrupt:
            print("\nStopping dashboard...")
            break
        except Exception as exc:
            print("ERROR:", exc)
            traceback.print_exc()
            time.sleep(2)


if __name__ == "__main__":
    run_dashboard()