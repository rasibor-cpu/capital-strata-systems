from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.intelligence.feature_builder import FeatureBuilder
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.opportunity_pressure_engine import OpportunityPressureEngine
from backend.intelligence.quant_signal_optimizer import QuantSignalOptimizer
from backend.execution.position_manager import PositionManager


cycle = 0
equity = 1000.0
pnl_total = 0.0
wins = 0
losses = 0
trades = 0


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _extract_close_rows(obj: Any) -> List[Dict[str, Any]]:
    if obj is None:
        return []
    if isinstance(obj, dict):
        return [obj]
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    return []


def _close_probe(pm: PositionManager) -> List[Dict[str, Any]]:
    if hasattr(pm, "check_closes"):
        try:
            return _extract_close_rows(pm.check_closes())
        except Exception as exc:
            print(f"[CLOSE-PROBE-ERROR] check_closes -> {type(exc).__name__}: {exc}")
            return []
    return []


def _rejection_reason(row: Dict[str, Any]) -> str:
    reason = str(row.get("optimizer_reason", "")).lower()
    tier = str(row.get("optimizer_tier", "")).upper()

    if "low_pressure_quality" in reason:
        return "low pressure quality"
    if "exhaustion" in reason:
        return "exhaustion zone"
    if tier == "WATCH":
        return "watchlist"
    if tier == "IGNORE":
        return "below threshold"
    return "filtered"


def print_perf() -> None:
    win_rate = (wins / trades * 100.0) if trades else 0.0
    print("\n===== PERFORMANCE =====")
    print(f"Equity: ${equity:.2f}")
    print(f"PnL: {pnl_total:+.2f}")
    print(f"Trades: {trades} | Wins: {wins} | Losses: {losses} | Win Rate: {win_rate:.1f}%")
    print("=======================\n")


def run() -> None:
    global cycle, equity, pnl_total, wins, losses, trades

    scanner = UnifiedMarketScanner()
    builder = FeatureBuilder()
    scorer = AIOpportunityScorer()
    pressure_engine = OpportunityPressureEngine()
    optimizer = QuantSignalOptimizer()
    pm = PositionManager()

    while True:
        cycle += 1
        print(f"\n--- NEW CYCLE #{cycle} ---")

        try:
            rows = scanner.scan()
            rows = builder.enrich_rows(rows)

            clean_rows: List[Dict[str, Any]] = []
            dropped = 0

            for r in rows:
                if not isinstance(r, dict):
                    dropped += 1
                    continue

                try:
                    s = scorer.score(r)
                    enriched = dict(r)
                    enriched["score"] = s
                    enriched["ai_score"] = s
                    enriched["tscore"] = s
                    clean_rows.append(enriched)
                except Exception as exc:
                    dropped += 1
                    print(f"[SCORE-SKIP] {r.get('symbol', 'UNKNOWN')} -> {type(exc).__name__}: {exc}")

            if dropped:
                print(f"[SCORE] dropped rows: {dropped}")

            if not clean_rows:
                print("[WARN] No valid rows after scoring")
                print_perf()
                time.sleep(5)
                continue

            # 🔥 PRESSURE INTEGRATION
            pressured_rows = pressure_engine.enrich_rows(clean_rows)

            # 🔥 OPTIMIZER
            decisions = optimizer.optimize(pressured_rows)

            accepted: List[Dict[str, Any]] = []
            rejected: List[Dict[str, Any]] = []
            reasons = defaultdict(int)

            for d in decisions:
                sym = d.get("symbol", "UNKNOWN")
                asset = d.get("asset_class", "unknown")

                tscore = _safe_float(d.get("tscore", 0.0))
                pressure_score = _safe_float(d.get("pressure_score", 0.0))
                confluence = _safe_float(d.get("confluence_score", 0.0))

                pressure_type = str(d.get("pressure_type", "NA"))
                pressure_quality = str(d.get("pressure_trade_quality", "NA"))

                tier = str(d.get("optimizer_tier", "IGNORE")).upper()
                opt_score = _safe_float(d.get("optimizer_score", 0.0))
                opt_reason = d.get("optimizer_reason", "")

                print(
                    f"[SCAN] {sym} | {asset} | "
                    f"tscore={tscore:.4f} | "
                    f"pressure={pressure_score:.4f} | "
                    f"confluence={confluence:.4f} | "
                    f"type={pressure_type} | "
                    f"quality={pressure_quality} | "
                    f"tier={tier} | "
                    f"opt_score={opt_score:.4f} | "
                    f"reason={opt_reason}"
                )

                if tier in ("ELITE", "QUALIFIED"):
                    accepted.append(d)
                    print(f"[ACCEPTED] {sym} -> TRADE ({tier})")
                else:
                    rejected.append(d)
                    reason = _rejection_reason(d)
                    reasons[reason] += 1
                    print(f"[REJECTED] {sym} -> {reason}")

            opens = 0
            closes = 0

            for d in accepted:
                sym = d.get("symbol")
                if not sym:
                    continue

                already_open = False
                if hasattr(pm, "is_open"):
                    try:
                        already_open = bool(pm.is_open(sym))
                    except Exception:
                        already_open = False

                if not already_open:
                    try:
                        pm.open_position(d)
                        opens += 1
                    except TypeError:
                        try:
                            pm.open_position(sym)
                            opens += 1
                        except Exception as exc:
                            print(f"[OPEN-ERROR] {sym} -> {type(exc).__name__}: {exc}")
                    except Exception as exc:
                        print(f"[OPEN-ERROR] {sym} -> {type(exc).__name__}: {exc}")

            closed = _close_probe(pm)

            for c in closed:
                closes += 1
                trades += 1

                pnl = _safe_float(
                    c.get("pnl", c.get("realized_pnl", c.get("profit", c.get("net_pnl", 0.0))))
                )
                pnl_total += pnl
                equity += pnl

                if pnl > 0:
                    wins += 1
                else:
                    losses += 1

            open_count = "unknown"
            if hasattr(pm, "positions"):
                try:
                    if isinstance(pm.positions, dict):
                        open_count = len(pm.positions)
                    elif isinstance(pm.positions, list):
                        open_count = len(pm.positions)
                except Exception:
                    open_count = "unknown"

            print("\n===== CYCLE SUMMARY =====")
            print(f"Accepted: {len(accepted)}")
            print(f"Rejected: {len(rejected)}")
            print(f"New Opens: {opens}")
            print(f"New Closes: {closes}")
            print(f"Open Positions: {open_count}")

            if reasons:
                print("\nTop Rejection Reasons:")
                for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
                    print(f"  {reason}: {count}")

            if not hasattr(pm, "check_closes"):
                print("\n[INFO] PositionManager has no check_closes(); close telemetry is temporarily disabled.")

            print("=========================\n")
            print_perf()

        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[CYCLE-ERROR] {type(exc).__name__}: {exc}")

        time.sleep(5)


if __name__ == "__main__":
    run()