from __future__ import annotations

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

# Dynamic per-cycle open capacity
BASE_MAX_TRADES_PER_CYCLE = 3
MAX_TRADES_PER_CYCLE = 10

# Asset-class concurrent open-position caps
MAX_OPEN_FX = 4
MAX_OPEN_CRYPTO = 2
MAX_OPEN_FUTURES = 2

GLOBAL_TAKE_PROFIT_PCT = 0.014
GLOBAL_STOP_LOSS_PCT = 0.012
GLOBAL_MAX_HOLD_CYCLES = 5

BASE_TRADE_NOTIONAL_USD = 10.0

ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)

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
                out.append(c)
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


def classify_asset(symbol: str) -> str:
    s = str(symbol).upper().strip()

    # Futures / perpetuals
    futures_markers = ("PERP", "FUT", "FUTURES")
    if any(marker in s for marker in futures_markers):
        return "FUTURES"

    # FX pairs like EUR_CHF, GBP_USD, USDJPY-style fallback
    if "_" in s:
        parts = s.split("_")
        if len(parts) == 2 and len(parts[0]) == 3 and len(parts[1]) == 3:
            return "FX"

    if len(s) == 6 and s.isalpha():
        return "FX"

    # Crypto pairs
    crypto_quotes = (
        "-USD",
        "-USDT",
        "-USDC",
        "-BTC",
        "-ETH",
        "/USD",
        "/USDT",
        "/USDC",
    )
    if any(q in s for q in crypto_quotes):
        return "CRYPTO"

    # Conservative fallback:
    # if it has a dash and is not clearly futures, treat as crypto-style market symbol
    if "-" in s or "/" in s:
        return "CRYPTO"

    return "OTHER"


def get_open_position_counts() -> Dict[str, int]:
    counts = {
        "FX": 0,
        "CRYPTO": 0,
        "FUTURES": 0,
        "OTHER": 0,
    }
    for symbol in position_manager.get_open_positions().keys():
        asset_class = classify_asset(symbol)
        counts[asset_class] = counts.get(asset_class, 0) + 1
    return counts


def can_open_new_position(symbol: str) -> bool:
    if position_manager.has_open_position(symbol):
        return False

    asset_class = classify_asset(symbol)
    counts = get_open_position_counts()

    if asset_class == "FX":
        return counts.get("FX", 0) < MAX_OPEN_FX
    if asset_class == "CRYPTO":
        return counts.get("CRYPTO", 0) < MAX_OPEN_CRYPTO
    if asset_class == "FUTURES":
        return counts.get("FUTURES", 0) < MAX_OPEN_FUTURES

    # For uncategorized symbols, block by default to avoid accidental governance drift
    return False


def allowed_trade_slots_remaining() -> int:
    counts = get_open_position_counts()
    fx_remaining = max(0, MAX_OPEN_FX - counts.get("FX", 0))
    crypto_remaining = max(0, MAX_OPEN_CRYPTO - counts.get("CRYPTO", 0))
    futures_remaining = max(0, MAX_OPEN_FUTURES - counts.get("FUTURES", 0))
    return fx_remaining + crypto_remaining + futures_remaining


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
                    "venue": raw.get("venue", "UNKNOWN"),
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

                rows.append(
                    {
                        "symbol": s["symbol"],
                        "price": safe_float(payload.get("price")),
                        "vwap": safe_float(payload.get("vwap")),
                        "candles": candles,
                        "volume": safe_float(payload.get("volume")),
                        "avg_volume_24h": safe_float(payload.get("avg_volume_24h")),
                        "volatility": safe_float(payload.get("volatility")),
                        "price_compression": safe_float(payload.get("price_compression")),
                        "spread_bps": safe_float(payload.get("spread_bps")),
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

        for r in optimized:
            symbol = r["symbol"]
            candles = next((x["candles"] for x in rows if x["symbol"] == symbol), [])

            decision = orchestrator.evaluate_trade(
                asset=symbol,
                candles=candles,
            )

            decisions[symbol] = decision

            if decision.get("execute_trade"):
                passes += 1

            if decision.get("signal_tier") == "ELITE":
                elite += 1

        # -------- EXECUTION --------

        opened = 0
        remaining_slots = allowed_trade_slots_remaining()

        dynamic_limit = max(
            BASE_MAX_TRADES_PER_CYCLE,
            min(MAX_TRADES_PER_CYCLE, passes, remaining_slots),
        )

        for r in optimized:
            if opened >= dynamic_limit:
                break

            symbol = r["symbol"]
            price = next((x["price"] for x in rows if x["symbol"] == symbol), 0.0)

            if price <= 0:
                continue

            if not decisions.get(symbol, {}).get("execute_trade"):
                continue

            if not can_open_new_position(symbol):
                continue

            qty = BASE_TRADE_NOTIONAL_USD / price

            position_manager.open_long_position(
                symbol=symbol,
                quantity=qty,
                entry_price=price,
                cycle_no=cycle,
                opened_at_utc=now(),
            )

            print("[OPEN]", symbol, price, classify_asset(symbol))
            opened += 1

        closed = position_manager.update_positions(
            {r["symbol"]: r["price"] for r in rows},
            cycle,
            now(),
        )

        for c in closed:
            pnl = safe_float(c.get("realized_pnl_usd"))
            equity += pnl
            print("[CLOSE]", c["symbol"], pnl)

        # -------- DISPLAY --------

        clear()

        open_counts = get_open_position_counts()

        print("===== CSS DASHBOARD =====\n")
        print("Cycle:", cycle)
        print("Equity:", round(equity, 2))
        print("Elite signals:", elite)
        print("Orchestrator passes:", passes)
        print("Opened this cycle:", opened)
        print("Dynamic cycle limit:", dynamic_limit)
        print(
            "Open positions:",
            f"FX={open_counts.get('FX', 0)}/{MAX_OPEN_FX}",
            f"CRYPTO={open_counts.get('CRYPTO', 0)}/{MAX_OPEN_CRYPTO}",
            f"FUTURES={open_counts.get('FUTURES', 0)}/{MAX_OPEN_FUTURES}",
        )

        print("\nTop candidates:")

        for r in optimized[:10]:
            symbol = r["symbol"]
            d = decisions.get(symbol, {})
            print(
                symbol,
                "class", classify_asset(symbol),
                "score", round(safe_float(r.get("score", 0.0)), 3),
                "exec", d.get("execute_trade"),
                "decision", round(safe_float(d.get("decision_score", 0.0)), 3),
                "pressure", round(safe_float(d.get("pressure_score", 0.0)), 3),
                "accel", round(safe_float(d.get("acceleration_score", 0.0)), 3),
                "confluence", round(safe_float(d.get("confluence_score", 0.0)), 3),
                "elasticity", round(safe_float(r.get("elasticity_score", 0.0)), 3),
            )

        time.sleep(REFRESH_SECONDS)

    except KeyboardInterrupt:
        print("Stopped")
        break

    except Exception as e:
        print("ERROR:", e)
        traceback.print_exc()
        time.sleep(REFRESH_SECONDS)