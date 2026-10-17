"""Shadow paper run: real market data -> approved calibrated signals -> governed paper router.

Usage (on a host with market-data access, e.g. FINANCE):
  python tools/css_signal_shadow.py --artifacts artifacts/calibration --root artifacts/trading_profiles \
      --instrument BTC-USD --source coinbase --granularity 3600 --hours 72 --journal artifacts/shadow/run.jsonl

Paper only: signals enter TradingRouter (consent, personalities, governors, R14F, R7,
ExecutionGate, AntiBleed) and fill in the PaperBook; no broker is contacted. Every cycle writes
a heartbeat and every decision to the journal. Wall-clock only: never simulates elapsed time.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(*, router, bridge, producer, approvals, artifacts, instruments, granularity_s: int, hours: float,
        journal: Path, poll_s: float, clock=time.time, sleep=time.sleep, max_cycles: int | None = None) -> dict:
    journal.parent.mkdir(parents=True, exist_ok=True)
    start = clock()
    cycles = signals = routed = 0
    by_sha = {a["artifact_sha256"]: a for a in artifacts}
    with journal.open("a", encoding="utf-8") as fh:
        def write(rec):
            fh.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
            fh.flush()
        while clock() - start < hours * 3600 and (max_cycles is None or cycles < max_cycles):
            now = datetime.fromtimestamp(clock(), tz=timezone.utc)
            cycles += 1
            write({"type": "HEARTBEAT", "cycle": cycles, "at_utc": now.isoformat()})
            for inst in instruments:
                for produced in producer.produce(inst, granularity_s=granularity_s, now=now):
                    rec = {"type": "PRODUCED", "instrument": inst, "reason": produced.reason,
                           "artifact_sha256": produced.artifact_sha256, "at_utc": now.isoformat(),
                           "data_source": getattr(produced, "data_source", None),
                           "data_classification": getattr(produced, "data_classification", None),
                           "data_digest": getattr(produced, "data_digest", None),
                           "last_bar_ts": getattr(produced, "last_bar_ts", None),
                           "observed_spread_bps": getattr(produced, "observed_spread_bps", None)}
                    if produced.signal is not None:
                        signals += 1
                        result = bridge.publish_real_data(produced, by_sha[produced.artifact_sha256], approvals, now=now)
                        routed += int(result.accepted)
                        rec.update(signal_id=produced.signal.signal_id, routed=result.accepted, route_reason=result.reason,
                                   decisions=[{"user": d.follower_user_id, "outcome": d.outcome, "stage": d.stage,
                                               "reason": d.reason, "notional": d.notional} for d in result.decisions])
                    write(rec)
            sleep(poll_s)
        summary = {"type": "SUMMARY", "cycles": cycles, "signals": signals, "routed": routed,
                   "elapsed_s": round(clock() - start, 1)}
        write(summary)
    return summary


def main(argv=None) -> int:  # pragma: no cover - operational entry point
    from backend.signals.market_data import build_provider
    from backend.signals.producer import CalibrationApprovals, SignalProducer
    from backend.signals.research import DEFAULT_COSTS
    from backend.trading_profiles.engine_bridge import CssEngineSignalBridge
    from dashboard.mobile.mobile_app import _trading_router  # same governed router + fail-closed resolvers

    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--instrument", action="append", required=True)
    ap.add_argument("--source", choices=["coinbase", "alpaca_crypto", "binance", "alpaca_stock", "oanda"], required=True)
    ap.add_argument("--granularity", type=int, default=3600)
    ap.add_argument("--hours", type=float, required=True)
    ap.add_argument("--poll-seconds", type=float, default=60.0)
    ap.add_argument("--journal", required=True)
    args = ap.parse_args(argv)
    artifacts = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(args.artifacts).glob("*.json"))]
    router = _trading_router()
    approvals = CalibrationApprovals(router.engine.root)
    provider = build_provider(args.source)
    producer = SignalProducer(provider, approvals, artifacts, DEFAULT_COSTS)
    summary = run(router=router, bridge=CssEngineSignalBridge(router), producer=producer, approvals=approvals,
                  artifacts=artifacts, instruments=args.instrument, granularity_s=args.granularity, hours=args.hours,
                  journal=Path(args.journal), poll_s=args.poll_seconds)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
