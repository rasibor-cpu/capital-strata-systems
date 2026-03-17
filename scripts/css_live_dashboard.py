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

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

MAX_SYMBOLS_PER_CYCLE = 25
REFRESH_SECONDS = 10
MAX_TRADES_PER_CYCLE = 3

MAX_OPEN_POSITIONS_TOTAL = 5
MAX_OPEN_POSITIONS_FX = 3
MAX_OPEN_POSITIONS_CRYPTO = 2
MAX_OPEN_POSITIONS_OTHER = 1

GLOBAL_TAKE_PROFIT_PCT = 0.014
GLOBAL_STOP_LOSS_PCT = 0.012
GLOBAL_MAX_HOLD_CYCLES = 5

BASE_TRADE_NOTIONAL_USD = 10.0

ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)

SUMMARY_FILE = ARTIFACT_DIR / "css_extended_paper_test_summary.json"
POSITIONS_FILE = ARTIFACT_DIR / "css_open_positions.json"
CLOSED_TRADES_FILE = ARTIFACT_DIR / "css_closed_trades.json"

# ---------------------------------------------------
# ENGINES
# ---------------------------------------------------

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

# ---------------------------------------------------
# UTILITIES
# ---------------------------------------------------

def now():
    return datetime.now(timezone.utc).isoformat()


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def safe_float(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def infer_asset_class(symbol: str, venue: str) -> str:
    symbol = symbol.upper()

    if "_" in symbol:
        return "FX"

    crypto_suffix = (
        "-USD",
        "-USDT",
        "-USDC",
        "-BTC",
        "-ETH",
    )

    if symbol.endswith(crypto_suffix):
        return "CRYPTO"

    if venue in {"COINBASE", "KRAKEN", "BINANCE"}:
        return "CRYPTO"

    return "OTHER"


def summarize_selected_assets(rows):
    fx = 0
    crypto = 0
    other = 0

    for r in rows:
        cls = r["asset_class"]
        if cls == "FX":
            fx += 1
        elif cls == "CRYPTO":
            crypto += 1
        else:
            other += 1

    return f"FX={fx} CRYPTO={crypto} OTHER={other}"


def count_open_positions_by_asset_class():
    counts = {"FX": 0, "CRYPTO": 0, "OTHER": 0}

    try:
        open_positions = position_manager.get_open_positions()
    except Exception:
        return counts

    if isinstance(open_positions, dict):
        iterable = open_positions.values()
    else:
        iterable = open_positions

    for pos in iterable:
        symbol = str(pos.get("symbol", "")).upper()
        venue = str(pos.get("venue", "UNKNOWN")).upper()
        asset_class = infer_asset_class(symbol, venue)
        counts[asset_class] = counts.get(asset_class, 0) + 1

    return counts


def can_open_more_positions(asset_class: str) -> bool:
    try:
        open_positions = position_manager.get_open_positions()
        total_open = len(open_positions)
    except Exception:
        total_open = 0

    if total_open >= MAX_OPEN_POSITIONS_TOTAL:
        return False

    counts = count_open_positions_by_asset_class()

    if asset_class == "FX":
        return counts.get("FX", 0) < MAX_OPEN_POSITIONS_FX
    if asset_class == "CRYPTO":
        return counts.get("CRYPTO", 0) < MAX_OPEN_POSITIONS_CRYPTO
    return counts.get("OTHER", 0) < MAX_OPEN_POSITIONS_OTHER


def print_candidate_table(candidates: List[Dict[str, Any]], decision_map: Dict[str, Dict[str, Any]]):
    if not candidates:
        print("[CANDIDATES] none")
        return

    print("[TOP CANDIDATES]")
    for row in candidates[:10]:
        symbol = str(row.get("symbol", "UNKNOWN"))
        decision = decision_map.get(symbol, {})
        print(
            f"  {symbol:<12} "
            f"opt={safe_float(row.get('score', row.get('final_score', row.get('rank_score', 0.0))), 0.0):.4f} "
            f"exec={decision.get('execute_trade', False)} "
            f"tier={decision.get('signal_tier', 'WATCH')} "
            f"regime={decision.get('regime', 'NA')} "
            f"decision={safe_float(decision.get('decision_score', 0.0), 0.0):.4f} "
            f"elasticity={safe_float(decision.get('elasticity_score', 0.0), 0.0):.4f}"
        )


# ---------------------------------------------------
# FETCH ASSETS
# ---------------------------------------------------

def fetch_assets(selected_rows):
    rows = []

    for s in selected_rows:
        symbol = s["symbol"]
        venue = s["venue"]
        asset_class = s["asset_class"]

        try:
            payload = load_runtime_asset(symbol)
            payload = normalize_snapshot_spread(payload)

            candles = payload.get("candles", [])
            if len(candles) < 20:
                continue

            price = safe_float(payload.get("price"))
            vwap = safe_float(payload.get("vwap"))

            if price <= 0:
                continue

            rows.append(
                {
                    "symbol": symbol,
                    "venue": venue,
                    "asset_class": asset_class,
                    "price": price,
                    "vwap": vwap,
                    "spread_bps": safe_float(payload.get("spread_bps")),
                    "candles": candles,
                }
            )

        except Exception as e:
            print("[FETCH ERROR]", symbol, e)

    return rows


# ---------------------------------------------------
# STATE PERSIST
# ---------------------------------------------------

def persist_state(summary):
    with SUMMARY_FILE.open("w") as f:
        json.dump(summary, f, indent=2)

    with POSITIONS_FILE.open("w") as f:
        json.dump(position_manager.get_open_positions(), f, indent=2)

    with CLOSED_TRADES_FILE.open("w") as f:
        json.dump(position_manager.get_closed_positions(), f, indent=2)


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------

cycle = 0
starting_capital = 200
estimated_equity = 200

print("[CSS] dashboard starting...")

while True:
    cycle += 1

    try:
        discovered = scanner.scan()

        # ------------------------------------------------
        # BALANCED DISCOVERY BUCKETS
        # ------------------------------------------------

        fx_bucket = []
        crypto_bucket = []
        other_bucket = []

        seen = set()

        for raw in discovered:
            symbol = str(raw.get("symbol", "")).upper()
            if not symbol or symbol in seen:
                continue

            venue = str(raw.get("venue", "UNKNOWN")).upper()
            asset_class = infer_asset_class(symbol, venue)

            row = {
                "symbol": symbol,
                "venue": venue,
                "asset_class": asset_class,
            }

            if asset_class == "FX":
                fx_bucket.append(row)
            elif asset_class == "CRYPTO":
                crypto_bucket.append(row)
            else:
                other_bucket.append(row)

            seen.add(symbol)

        selected_rows = []
        selected_rows.extend(fx_bucket[:10])
        selected_rows.extend(crypto_bucket[:10])
        selected_rows.extend(other_bucket[:5])
        selected_rows = selected_rows[:MAX_SYMBOLS_PER_CYCLE]

        symbols = [r["symbol"] for r in selected_rows]

        print("[SCAN] selected symbols:", symbols)
        print("[SCAN] asset mix:", summarize_selected_assets(selected_rows))

        rows = fetch_assets(selected_rows)

        if not rows:
            time.sleep(REFRESH_SECONDS)
            continue

        rows_by_symbol = {r["symbol"]: r for r in rows}

        # ------------------------------------------------
        # PIPELINE
        # ------------------------------------------------

        features = feature_builder.enrich_rows(rows, {})
        regimes = regime_engine.detect(features)
        pressure = pressure_engine.enrich_rows(regimes)
        accel = accel_engine.enrich_rows(pressure)
        confluence = confluence_engine.enrich_rows(accel)
        elasticity = elasticity_engine.enrich_rows(confluence)
        sweeps = sweep_engine.enrich_rows(elasticity)

        ranked = ai.rank_opportunities(sweeps)
        optimized = optimizer.optimize(ranked)

        # ------------------------------------------------
        # FINAL ORCHESTRATOR GATE
        # ------------------------------------------------

        decision_map: Dict[str, Dict[str, Any]] = {}
        orchestrator_pass_count = 0
        elite_count = 0

        for r in optimized:
            symbol = str(r.get("symbol", "")).upper()
            source_row = rows_by_symbol.get(symbol, {})
            candles = source_row.get("candles", [])

            if not candles or len(candles) < 20:
                decision_map[symbol] = {
                    "execute_trade": False,
                    "signal_tier": "WATCH",
                    "decision_score": 0.0,
                    "regime": "UNSTABLE",
                    "elasticity_score": 0.0,
                    "regime_reason": "missing candle history",
                }
                continue

            decision = orchestrator.evaluate_trade(
                asset=symbol,
                candles=candles,
            )

            decision_map[symbol] = decision

            if decision.get("execute_trade"):
                orchestrator_pass_count += 1

            if str(decision.get("signal_tier", "WATCH")).upper() == "ELITE":
                elite_count += 1

        # ------------------------------------------------
        # EXECUTION
        # ------------------------------------------------

        opened = 0
        latest_prices = {r["symbol"]: r["price"] for r in rows}

        for r in optimized:
            if opened >= MAX_TRADES_PER_CYCLE:
                break

            symbol = str(r.get("symbol", "")).upper()
            price = safe_float(latest_prices.get(symbol))
            source_row = rows_by_symbol.get(symbol, {})
            asset_class = str(source_row.get("asset_class", "OTHER")).upper()
            decision = decision_map.get(symbol, {})

            if price <= 0:
                continue

            if position_manager.has_open_position(symbol):
                continue

            if not can_open_more_positions(asset_class):
                continue

            if not decision.get("execute_trade", False):
                continue

            qty = BASE_TRADE_NOTIONAL_USD / price

            position_manager.open_long_position(
                symbol=symbol,
                quantity=qty,
                entry_price=price,
                cycle_no=cycle,
                opened_at_utc=now(),
            )

            print(
                "[OPEN]",
                symbol,
                "price",
                price,
                "tier",
                decision.get("signal_tier"),
                "score",
                decision.get("decision_score"),
                "regime",
                decision.get("regime"),
            )

            opened += 1

        closed = position_manager.update_positions(
            latest_prices,
            cycle,
            now(),
        )

        for c in closed:
            pnl = safe_float(c.get("realized_pnl_usd"))
            estimated_equity += pnl

            print("[CLOSE]", c["symbol"], "pnl", pnl)

        try:
            open_positions_count = len(position_manager.get_open_positions())
        except Exception:
            open_positions_count = 0

        summary = {
            "timestamp": now(),
            "cycle": cycle,
            "starting_capital": starting_capital,
            "equity": estimated_equity,
            "symbols_scanned": len(symbols),
            "candidates_after_optimizer": len(optimized),
            "orchestrator_pass_count": orchestrator_pass_count,
            "elite_signal_count": elite_count,
            "opened": opened,
            "open_positions": open_positions_count,
        }

        persist_state(summary)

        clear()

        print("======================================")
        print(" CAPITAL STRATA SYSTEMS DASHBOARD")
        print("======================================\n")

        print("Cycle:", cycle)
        print("Equity:", round(estimated_equity, 2))
        print("Symbols scanned:", len(symbols))
        print("Candidates after optimizer:", len(optimized))
        print("Elite signals:", elite_count)
        print("Orchestrator passes:", orchestrator_pass_count)
        print("Opened this cycle:", opened)
        print("Open positions:", open_positions_count)
        print()

        print_candidate_table(optimized, decision_map)

        print("\nRefreshing in", REFRESH_SECONDS, "seconds\n")

        time.sleep(REFRESH_SECONDS)

    except KeyboardInterrupt:
        print("CSS stopped")
        break

    except Exception as e:
        print("CSS ERROR:", e)
        traceback.print_exc()
        time.sleep(REFRESH_SECONDS)