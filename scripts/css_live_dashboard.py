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

def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def safe_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def normalize_candles(candles: List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    for c in candles:
        try:
            if isinstance(c, dict):
                out.append(
                    {
                        "open": c.get("open"),
                        "high": c.get("high"),
                        "low": c.get("low"),
                        "close": c.get("close"),
                        "volume": c.get("volume"),
                    }
                )
            else:
                out.append(
                    {
                        "open": getattr(c, "open", None),
                        "high": getattr(c, "high", None),
                        "low": getattr(c, "low", None),
                        "close": getattr(c, "close", None),
                        "volume": getattr(c, "volume", None),
                    }
                )
        except Exception:
            out.append({})

    return out


def persist_summary(payload: Dict[str, Any]) -> None:
    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def get_open_positions_count() -> int:
    try:
        positions = position_manager.get_open_positions()
        if isinstance(positions, dict):
            return len(positions)
        if isinstance(positions, list):
            return len(positions)
        return 0
    except Exception:
        return 0


def has_open_position(symbol: str) -> bool:
    try:
        if hasattr(position_manager, "has_open_position"):
            return bool(position_manager.has_open_position(symbol))
    except Exception:
        pass

    try:
        positions = position_manager.get_open_positions()
        if isinstance(positions, dict):
            return symbol in positions
        if isinstance(positions, list):
            for p in positions:
                if str(p.get("symbol", "")).upper() == symbol.upper():
                    return True
    except Exception:
        pass

    return False


def safe_open_position(symbol: str, price: float, cycle_no: int) -> bool:
    qty = BASE_TRADE_NOTIONAL_USD / price if price > 0 else 0.0
    if qty <= 0:
        return False

    open_attempts = [
        lambda: position_manager.open_long_position(
            symbol=symbol,
            quantity=qty,
            entry_price=price,
            cycle_no=cycle_no,
            opened_at_utc=now(),
        ),
        lambda: position_manager.open_long_position(
            symbol=symbol,
            quantity=qty,
            entry_price=price,
        ),
        lambda: position_manager.open_position(
            symbol=symbol,
            quantity=qty,
            entry_price=price,
            cycle_no=cycle_no,
            opened_at_utc=now(),
        ),
        lambda: position_manager.open_position(
            symbol=symbol,
            quantity=qty,
            entry_price=price,
        ),
    ]

    for attempt in open_attempts:
        try:
            attempt()
            return True
        except TypeError:
            continue
        except Exception:
            traceback.print_exc()
            return False

    return False


def safe_update_positions(latest_prices: Dict[str, float], cycle_no: int) -> List[Dict[str, Any]]:
    update_attempts = [
        lambda: position_manager.update_positions(latest_prices, cycle_no, now()),
        lambda: position_manager.update_positions(latest_prices, cycle_no),
        lambda: position_manager.update_positions(latest_prices),
        lambda: position_manager.update_positions(),
    ]

    raw_result: Any = []

    for attempt in update_attempts:
        try:
            raw_result = attempt()
            break
        except TypeError:
            continue
        except Exception:
            traceback.print_exc()
            return []

    if raw_result is None:
        return []

    if isinstance(raw_result, list):
        return [x for x in raw_result if isinstance(x, dict)]

    if isinstance(raw_result, dict):
        if isinstance(raw_result.get("closed"), list):
            return [x for x in raw_result.get("closed", []) if isinstance(x, dict)]
        return [raw_result]

    return []


def print_candidate_table(candidates: List[Dict[str, Any]], decisions: Dict[str, Dict[str, Any]]) -> None:
    print("\nTop candidates:")

    if not candidates:
        print("  none")
        return

    for r in candidates[:10]:
        symbol = str(r.get("symbol", "UNKNOWN"))
        d = decisions.get(symbol, {})
        base_score = safe_float(
            r.get("score", r.get("final_score", r.get("rank_score", 0.0))),
            0.0,
        )
        print(
            f"  {symbol:<12}"
            f"opt={base_score:.3f} "
            f"exec={d.get('execute_trade', False)} "
            f"tier={d.get('signal_tier', 'WATCH')} "
            f"decision={safe_float(d.get('decision_score', 0.0)):.3f} "
            f"elasticity={safe_float(d.get('elasticity_score', 0.0)):.3f} "
            f"regime={d.get('regime', 'NA')}"
        )


# ---------------- MAIN ----------------

cycle = 0
equity = 200.0

print("[CSS] dashboard starting...")

while True:
    cycle += 1

    try:
        discovered = scanner.scan()

        selected: List[Dict[str, Any]] = []
        seen = set()

        for raw in discovered:
            sym = str(raw.get("symbol", "")).upper()
            if not sym or sym in seen:
                continue

            selected.append(
                {
                    "symbol": sym,
                    "venue": str(raw.get("venue", "UNKNOWN")).upper(),
                }
            )
            seen.add(sym)

        selected = selected[:MAX_SYMBOLS_PER_CYCLE]

        rows: List[Dict[str, Any]] = []

        for s in selected:
            try:
                payload = load_runtime_asset(s["symbol"])
                payload = normalize_snapshot_spread(payload)

                candles = normalize_candles(payload.get("candles", []))
                if len(candles) < 20:
                    continue

                price = safe_float(payload.get("price"))
                if price <= 0:
                    continue

                rows.append(
                    {
                        "symbol": s["symbol"],
                        "venue": s["venue"],
                        "price": price,
                        "vwap": safe_float(payload.get("vwap")),
                        "spread_bps": safe_float(payload.get("spread_bps")),
                        "candles": candles,
                    }
                )

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

        decisions: Dict[str, Dict[str, Any]] = {}
        elite = 0
        passes = 0
        rows_by_symbol = {r["symbol"]: r for r in rows}

        for r in optimized:
            symbol = str(r.get("symbol", "")).upper()
            candles = rows_by_symbol.get(symbol, {}).get("candles", [])

            decision = orchestrator.evaluate_trade(
                asset=symbol,
                candles=candles,
            )

            decisions[symbol] = decision

            if decision.get("execute_trade"):
                passes += 1

            if str(decision.get("signal_tier", "WATCH")).upper() == "ELITE":
                elite += 1

        # -------- EXECUTION --------

        opened = 0

        for r in optimized:
            if opened >= MAX_TRADES_PER_CYCLE:
                break

            symbol = str(r.get("symbol", "")).upper()
            price = safe_float(rows_by_symbol.get(symbol, {}).get("price"), 0.0)

            if price <= 0:
                continue

            if has_open_position(symbol):
                continue

            if not decisions.get(symbol, {}).get("execute_trade", False):
                continue

            if safe_open_position(symbol, price, cycle):
                print(
                    "[OPEN]",
                    symbol,
                    "price",
                    price,
                    "tier",
                    decisions.get(symbol, {}).get("signal_tier"),
                    "score",
                    decisions.get(symbol, {}).get("decision_score"),
                )
                opened += 1

        closed = safe_update_positions(
            {r["symbol"]: r["price"] for r in rows},
            cycle,
        )

        for c in closed:
            pnl = safe_float(c.get("realized_pnl_usd", c.get("pnl", 0.0)), 0.0)
            equity += pnl
            print("[CLOSE]", c.get("symbol", "UNKNOWN"), pnl)

        # -------- DISPLAY --------

        summary = {
            "timestamp": now(),
            "cycle": cycle,
            "equity": round(equity, 2),
            "symbols_scanned": len(selected),
            "rows_loaded": len(rows),
            "candidates_after_optimizer": len(optimized),
            "elite_signals": elite,
            "orchestrator_passes": passes,
            "opened_this_cycle": opened,
            "open_positions": get_open_positions_count(),
        }

        persist_summary(summary)

        clear()
        print("===== CSS DASHBOARD =====\n")
        print("Cycle:", cycle)
        print("Equity:", round(equity, 2))
        print("Symbols scanned:", len(selected))
        print("Rows loaded:", len(rows))
        print("Candidates after optimizer:", len(optimized))
        print("Elite signals:", elite)
        print("Orchestrator passes:", passes)
        print("Opened this cycle:", opened)
        print("Open positions:", get_open_positions_count())

        print_candidate_table(optimized, decisions)

        time.sleep(REFRESH_SECONDS)

    except KeyboardInterrupt:
        print("Stopped")
        break

    except Exception as e:
        print("ERROR:", e)
        traceback.print_exc()
        time.sleep(REFRESH_SECONDS)