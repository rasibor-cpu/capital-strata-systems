"""Deterministic evidence for the owner: AntiBleed's minimum size (50) vs CAD 20 pilot orders.

Read-only with respect to the repository: writes only into a temporary directory and prints a
JSON report (optionally to --out). Nothing is enabled or relaxed; this measures current
behaviour through the real governed router and computes fee economics.

Usage: python tools/antibleed_cad20_evidence.py [--out report.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
SAFE_FLAGS = {"verdict": "SAFE", "fail_closed": False, "execution_allowed": False, "live_trading_blocked": True}
# (symbol, asset_class, expected_move_bps): a deterministic spread of edges around the 25 bps net floor
CASES = [(f"FX{i:02d}/USD", "FX", move) for i, move in enumerate((30, 40, 60, 80, 120, 200))]
FIXED_FEES_CAD = (0.0, 0.01, 0.02, 0.05, 0.10, 0.25)
NOTIONALS_CAD = (10.0, 20.0, 40.0, 50.0, 100.0)
NET_EDGE_FLOOR_BPS = 25.0
VARIABLE_COST_BPS = 4.0  # fee 2 + spread 1 + slippage 1 (the router's synthetic signal costs)


def _router(root: Path):
    from backend.trading_profiles.copy_engine import CopyTradeEngine, SystemContext
    from backend.trading_profiles.manual import ACKNOWLEDGEMENT_SHA256
    from backend.trading_profiles.router import PaperBook, TradingRouter

    engine = CopyTradeEngine(root, key_provider=None)
    c = engine.consent
    change = c.propose_change("pilot-paper", operating_mode="CSS Autonomous Trading", risk_personality="Balanced",
                              now=NOW)
    review = c.open_review("pilot-paper", auth_session_hash="s", change_id=change.change_id, now=NOW)
    for pid in review.pages:
        page = c.present_page("pilot-paper", auth_session_hash="s", review_id=review.review_id, page_id=pid, now=NOW)
        c.mark_reviewed("pilot-paper", auth_session_hash="s", review_id=review.review_id, page_id=pid,
                        method="scroll_bottom", page_sha256=page["sha256"], now=NOW)
    m = c.manual_provider()
    c.accept("pilot-paper", auth_session_hash="s", review_id=review.review_id, acknowledgement_checked=True,
             acknowledgement_sha256=ACKNOWLEDGEMENT_SHA256, manual_version=m.version, manual_sha256=m.sha256,
             policy_hash_shown=change.policy_hash, now=NOW)
    sess = ("s", time.time())
    return TradingRouter(engine, book=PaperBook(root, pilot_envelope=True), role_resolver=lambda u: "TRADER",
                         session_resolver=lambda u: sess,
                         system_provider=lambda: SystemContext("BALANCED", SAFE_FLAGS, {}, {}))


def build_report() -> dict:
    from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, SourceSignal

    outcomes: Counter[str] = Counter()
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        router = _router(Path(tmp))
        for i, (symbol, asset, move) in enumerate(CASES):
            sig = SourceSignal(signal_id=f"ev-{i}", trader_id=AUTONOMOUS_SOURCE_ID, symbol=symbol, asset_class=asset,
                               side="BUY", reference_price=1.0, probability=0.67, signal_score=16.0, confidence=0.75,
                               expected_move_bps=float(move), fee_bps=2.0, spread_bps=1.0, slippage_bps=1.0,
                               stop_distance_pct=2.5, risk_reward=2.4, strategy_score=0.9, replay_confidence=0.9)
            (d,) = router.on_css_engine_signal(sig, now=NOW).decisions
            outcomes[f"{d.stage}:{d.reason}"] += 1
            rows.append({"symbol": symbol, "expected_move_bps": move, "notional": d.notional, "outcome": d.outcome,
                         "stage": d.stage, "reason": d.reason})
    economics = []
    for notional in NOTIONALS_CAD:
        for fee in FIXED_FEES_CAD:
            fixed_bps = fee / notional * 10_000
            economics.append({"notional_cad": notional, "fixed_fee_cad": fee, "fixed_fee_bps": round(fixed_bps, 2),
                              "min_expected_move_bps_to_clear_floor":
                                  round(NET_EDGE_FLOOR_BPS + VARIABLE_COST_BPS + fixed_bps, 2)})
    return {
        "schema": "css.antibleed_cad20_evidence.v1",
        "question": "Can CAD 20 pilot-envelope paper orders pass AntiBleedGuard (minimum size 50)?",
        "router_replay": {"orders": len(rows), "outcomes": dict(outcomes), "rows": rows},
        "fee_economics": economics,
        "findings": [
            "Every pilot-envelope order is sized to at most CAD 20 incl. fees and is rejected by AntiBleedGuard "
            "with trade_size_too_small; no order is filled and nothing is relaxed.",
            "AntiBleed's 25 bps net-edge rule is expressed in bps of notional and does not see fixed per-order "
            "fees; at CAD 20 a CAD 0.05 fixed fee alone costs 25 bps, doubling the required edge.",
            "The minimum size (50) carries no currency in code (live_micro_pilot_governor labels it "
            "UNSPECIFIED); in the governed paper router notionals are in account currency (CAD).",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = build_report()
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
