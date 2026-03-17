from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.execution.position_manager import PositionManager
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.market_regime_engine import MarketRegimeEngine

# Reuse the known-good Laptop 1 dashboard environment
from scripts.css_live_dashboard_HEAD1 import (
    scanner,
    fetch_assets,
    safe_float,
    choose_engine_mode,
    ENGINE_PROFILES,
)

REFRESH_SECONDS = 30
MAX_SYMBOLS_PER_CYCLE = 25
MAX_TRADES_PER_CYCLE = 2
TRADE_NOTIONAL_USD = 10.0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    feature_builder = FeatureBuilder()
    regime_engine = MarketRegimeEngine()
    scorer = AIOpportunityScorer()
    position_manager = PositionManager()

    engine_mode = choose_engine_mode()
    active_profile = ENGINE_PROFILES[engine_mode]

    print("[CSS] Starting live dashboard (stable HEAD1-aligned)...")
    print(f"[CSS] Engine mode: {engine_mode}")
    print(f"[CSS] Active profile loaded: {bool(active_profile)}")

    cycle = 0

    while True:
        cycle += 1

        try:
            discovered = scanner.scan()

            symbols = [
                str(r["symbol"]).upper()
                for r in discovered
                if str(r.get("venue", "")).upper() == "COINBASE"
            ][:MAX_SYMBOLS_PER_CYCLE]

            print(f"\n===== CSS DASHBOARD =====")
            print(f"Cycle: {cycle}")
            print(f"[SCAN] selected Coinbase symbols ({len(symbols)}): {symbols}")

            rows = fetch_assets(symbols)

            if not rows:
                print("Waiting for valid market rows...")
                time.sleep(REFRESH_SECONDS)
                continue

            latest_prices: Dict[str, float] = {
                str(r["symbol"]).upper(): safe_float(r.get("price"), 0.0)
                for r in rows
            }

            features = feature_builder.enrich_rows(rows, {})
            regime_rows = regime_engine.detect(features)

            ranked = []
            for r in regime_rows:
                symbol = str(r.get("symbol", "")).upper()
                base_score = safe_float(r.get("score"), 0.0)

                opportunity = dict(r)
                ai_score = safe_float(
                    scorer.score_opportunity(opportunity),
                    base_score,
                )

                ranked.append(
                    {
                        "symbol": symbol,
                        "score": ai_score,
                        "base_score": base_score,
                        "confluence": safe_float(r.get("confluence_score"), 0.0),
                        "pressure": safe_float(r.get("pressure_score"), 0.0),
                        "accel": safe_float(r.get("pressure_acceleration"), 0.0),
                        "spread_bps": safe_float(r.get("spread_bps"), 0.0),
                        "vwap_dev": safe_float(r.get("vwap_dev_abs"), 0.0),
                        "rwin": safe_float(r.get("reversion_window_score"), 0.0),
                        "elas": safe_float(r.get("elasticity_score"), 0.0),
                        "regime": str(r.get("regime", "NEUTRAL")).upper(),
                        "raw": r,
                    }
                )

            ranked.sort(key=lambda x: x["score"], reverse=True)

            print(f"Rows loaded: {len(rows)}")
            print(f"Features loaded: {len(features)}")
            print(f"Regime rows: {len(regime_rows)}")
            print(f"Ranked candidates: {len(ranked)}")

            execution_candidates = []
            for r in ranked:
                if len(execution_candidates) >= MAX_TRADES_PER_CYCLE:
                    break
                if r["score"] < 0.30:
                    continue
                execution_candidates.append(r)

            print(f"Candidates selected for execution review: {len(execution_candidates)}")

            for r in ranked[:10]:
                print(
                    f"[CANDIDATE] {r['symbol']} | base={r['base_score']:.6f} | "
                    f"score={r['score']:.6f} | confluence={r['confluence']:.2f} | "
                    f"pressure={r['pressure']:.2f} | accel={r['accel']:.2f} | "
                    f"spread={r['spread_bps']:.2f} | regime={r['regime']}"
                )

            opened_this_cycle = 0

            for r in execution_candidates:
                symbol = r["symbol"]
                price = safe_float(latest_prices.get(symbol), 0.0)

                if price <= 0:
                    print(f"[SKIP] {symbol} invalid_price")
                    continue

                if position_manager.has_open_position(symbol):
                    print(f"[SKIP] {symbol} already_open")
                    continue

                qty = TRADE_NOTIONAL_USD / price

                position_manager.open_long_position(
                    symbol=symbol,
                    quantity=qty,
                    entry_price=price,
                    cycle_no=cycle,
                    opened_at_utc=now(),
                )

                opened_this_cycle += 1

                print(
                    f"[OPEN] {symbol} | price={price:.6f} | qty={qty:.8f} | "
                    f"trade={r['score']:.2f} | vwap_dev={r['vwap_dev']:.4f} | "
                    f"rwin={r['rwin']:.2f} | elas={r['elas']:.2f} | "
                    f"confluence={r['confluence']:.2f} | pressure={r['pressure']:.2f} | "
                    f"accel={r['accel']:.2f}"
                )

            closed_positions = position_manager.update_positions(
                latest_prices=latest_prices,
                cycle_no=cycle,
            )

            if closed_positions:
                for trade in closed_positions:
                    print(f"[CLOSE] {trade}")

            print(f"Opened this cycle: {opened_this_cycle}")

        except Exception as e:
            print(f"CSS ERROR: {e}")

        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    main()