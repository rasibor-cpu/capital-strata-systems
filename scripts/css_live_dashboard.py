from __future__ import annotations

import json
import os
import sys
import time
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
from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.strategies.vwap_mean_reversion import compute_vwap_from_candles


ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)

SUMMARY_FILE = ARTIFACT_DIR / "css_extended_paper_test_summary.json"
POSITIONS_FILE = ARTIFACT_DIR / "css_open_positions.json"
CLOSED_TRADES_FILE = ARTIFACT_DIR / "css_closed_trades.json"


scanner = UnifiedMarketScanner()

feature_builder = FeatureBuilder()
regime_engine = MarketRegimeEngine()
pressure_engine = OpportunityPressureEngine()
accel_engine = PressureAccelerationEngine()
sweep_engine = LiquiditySweepDetector()
ai = AIOpportunityScorer()
optimizer = QuantSignalOptimizer()

position_manager = PositionManager(
    take_profit_pct=0.025,
    stop_loss_pct=0.012,
    max_hold_cycles=8,
)

starting_capital = 200.0
estimated_equity = starting_capital
cycle = 0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def fetch_assets(symbols: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for symbol in symbols:
        try:
            payload = load_runtime_asset(symbol)
            candles = payload.get("candles", [])

            if len(candles) < 20:
                continue

            price = safe_float(payload.get("price", 0.0), 0.0)
            if price <= 0:
                continue

            vwap = compute_vwap_from_candles(candles, 20)
            vwap = safe_float(vwap, 0.0)

            if vwap <= 0:
                vwap = price

            spread = ((price - vwap) / vwap) * 10000

            rows.append(
                {
                    "symbol": symbol,
                    "price": price,
                    "vwap": vwap,
                    "spread_bps": spread,
                    "candles": candles,
                }
            )

        except Exception:
            continue

    return rows


def persist_state(summary: Dict[str, Any]) -> None:
    try:
        with SUMMARY_FILE.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        with POSITIONS_FILE.open("w", encoding="utf-8") as f:
            json.dump(position_manager.get_open_positions(), f, indent=2)

        with CLOSED_TRADES_FILE.open("w", encoding="utf-8") as f:
            json.dump(position_manager.get_closed_positions(), f, indent=2)

    except Exception as exc:
        print(f"[WARN] Could not persist artifact state: {exc}")


print("[CSS] Starting live dashboard...")

while True:
    cycle += 1

    try:
        discovered = scanner.scan()

        symbols = [
            r["symbol"]
            for r in discovered
            if r.get("venue") == "COINBASE"
        ][:5]

        rows = fetch_assets(symbols)

        if not rows:
            print("Waiting for valid market rows...")
            time.sleep(10)
            continue

        latest_prices: Dict[str, float] = {
            row["symbol"]: safe_float(row["price"], 0.0) for row in rows
        }

        # ----------------------------------------------------
        # Intelligence Pipeline
        # ----------------------------------------------------
        features = feature_builder.enrich_rows(rows, {})
        regime_rows = regime_engine.detect(features)
        pressure_rows = pressure_engine.enrich_rows(regime_rows)
        accel_rows = accel_engine.enrich(pressure_rows)
        sweep_rows = sweep_engine.enrich(accel_rows)
        ranked = ai.rank_opportunities(sweep_rows)

        pressure_map = {r["symbol"]: r for r in sweep_rows}

        merged: List[Dict[str, Any]] = []

        for r in ranked:
            p = pressure_map.get(r["symbol"], {})

            merged.append(
                {
                    "symbol": r["symbol"],
                    "score": safe_float(r.get("score", 0.0), 0.0),
                    "pressure_score": safe_float(p.get("pressure_score", 0.0), 0.0),
                    "pressure_acceleration": safe_float(
                        p.get("pressure_acceleration", 0.0), 0.0
                    ),
                    "spread_bps": safe_float(p.get("spread_bps", 0.0), 0.0),
                    "regime": str(p.get("regime", "NEUTRAL")),
                }
            )

        optimized = optimizer.optimize(merged)

        # ----------------------------------------------------
        # Position opening logic
        # ----------------------------------------------------
        for r in optimized:
            symbol = str(r.get("symbol", "")).upper()
            decision = str(r.get("decision", "IGNORE")).upper()
            trade_score = safe_float(r.get("trade_score", 0.0), 0.0)
            price = latest_prices.get(symbol, 0.0)

            if not symbol or price <= 0:
                continue

            if decision != "TRADE":
                continue

            if position_manager.has_open_position(symbol):
                continue

            allocation_usd = 10.0
            quantity = allocation_usd / price

            try:
                position_manager.open_long_position(
                    symbol=symbol,
                    quantity=quantity,
                    entry_price=price,
                    cycle_no=cycle,
                    opened_at_utc=now(),
                )
                print(
                    f"[OPEN] {symbol} | price={price:.6f} | "
                    f"qty={quantity:.8f} | trade_score={trade_score:.2f}"
                )
            except Exception as exc:
                print(f"[WARN] Could not open position for {symbol}: {exc}")

        # ----------------------------------------------------
        # Position closing logic
        # ----------------------------------------------------
        closed_positions = position_manager.update_positions(
            latest_prices=latest_prices,
            cycle_no=cycle,
            timestamp_utc=now(),
        )

        if closed_positions:
            for trade in closed_positions:
                pnl = safe_float(trade.get("realized_pnl_usd", 0.0), 0.0)
                estimated_equity += pnl

                print(
                    f"[CLOSE] {trade.get('symbol', '')} | "
                    f"reason={trade.get('exit_reason', '')} | "
                    f"pnl={pnl:.4f}"
                )

        pm_summary = position_manager.summary()

        summary: Dict[str, Any] = {
            "timestamp_utc": now(),
            "cycle_no": cycle,
            "starting_capital_usd": round(starting_capital, 4),
            "estimated_equity_usd": round(estimated_equity, 4),
            "open_positions": int(pm_summary.get("open_positions", 0)),
            "closed_trades": int(pm_summary.get("closed_trades", 0)),
            "wins": int(pm_summary.get("wins", 0)),
            "losses": int(pm_summary.get("losses", 0)),
            "win_rate": safe_float(pm_summary.get("win_rate", 0.0), 0.0),
            "gross_profit_usd": safe_float(pm_summary.get("gross_profit_usd", 0.0), 0.0),
            "gross_loss_usd": safe_float(pm_summary.get("gross_loss_usd", 0.0), 0.0),
            "realized_pnl_usd": safe_float(pm_summary.get("realized_pnl_usd", 0.0), 0.0),
            "active_symbols": symbols,
        }

        persist_state(summary)

        clear()

        print("====================================================")
        print("        CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
        print("====================================================\n")

        print(f"Cycle: {cycle} | Starting Capital: ${starting_capital:.2f}")
        print(f"Estimated Equity: ${estimated_equity:.2f}")
        print("Active Symbols:", ", ".join(symbols))
        print("Timestamp:", now())

        print("\nAI OPPORTUNITY SCANNER")
        print("----------------------------------------------------")

        for r in optimized:
            print(
                f"{str(r.get('symbol', '')):10}"
                f" regime={str(r.get('regime', 'NEUTRAL')):14}"
                f" score={safe_float(r.get('score', 0.0), 0.0):.2f}"
                f" pressure={safe_float(r.get('pressure_score', 0.0), 0.0):.2f}"
                f" accel={safe_float(r.get('pressure_acceleration', 0.0), 0.0):.2f}"
                f" trade={safe_float(r.get('trade_score', 0.0), 0.0):.2f}"
                f" decision={str(r.get('decision', 'IGNORE'))}"
            )

        print("\nPOSITION SUMMARY")
        print("----------------------------------------------------")
        print(
            f"Open={summary['open_positions']} | "
            f"Closed={summary['closed_trades']} | "
            f"Wins={summary['wins']} | "
            f"Losses={summary['losses']} | "
            f"WinRate={summary['win_rate']:.2f}"
        )
        print(
            f"GrossProfit=${summary['gross_profit_usd']:.4f} | "
            f"GrossLoss=${summary['gross_loss_usd']:.4f} | "
            f"RealizedPnL=${summary['realized_pnl_usd']:.4f}"
        )

        print("\nOPEN POSITIONS")
        print("----------------------------------------------------")

        open_positions = position_manager.get_open_positions()

        if not open_positions:
            print("None")
        else:
            for pos in open_positions:
                print(
                    f"{str(pos.get('symbol', '')):10} "
                    f"entry={safe_float(pos.get('entry_price', 0.0), 0.0):.6f} "
                    f"tp={safe_float(pos.get('take_profit_price', 0.0), 0.0):.6f} "
                    f"sl={safe_float(pos.get('stop_loss_price', 0.0), 0.0):.6f} "
                    f"hold={int(pos.get('hold_cycles', 0))}/"
                    f"{int(pos.get('max_hold_cycles', 0))}"
                )

        print("\nRefreshing in 10 seconds...\n")

        time.sleep(10)

    except KeyboardInterrupt:
        print("CSS stopped")
        break

    except Exception as e:
        print("CSS ERROR:", e)
        time.sleep(10)