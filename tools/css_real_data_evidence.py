"""One real-data producer cycle, recorded as evidence (paper/research only).

Usage (on a host that can reach the public endpoints, e.g. a CI runner or FINANCE):
  python tools/css_real_data_evidence.py --artifacts evidence/calibration --instrument BTC-USD \
      --source coinbase --out evidence/producer_cycle.json

Runs backend.signals.producer.SignalProducer against the real read-only feed with the real
quote/spread check, using an EMPTY approvals ledger in a scratch directory. Approvals are never
created here: by design every artifact is refused at dual control until two distinct
SUPER_USERs approve it on the operator host. The output proves the live path up to that gate
(fresh bars, classification, market quality, provenance) without inventing an approval.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.signals.market_data import CoinbaseQuotes, AlpacaCryptoQuotes, build_provider, resilient_http  # noqa: E402
from backend.signals.producer import CalibrationApprovals, SignalProducer  # noqa: E402
from backend.signals.research import DEFAULT_COSTS  # noqa: E402

QUOTES = {"coinbase": CoinbaseQuotes, "alpaca_crypto": AlpacaCryptoQuotes}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--source", required=True, choices=sorted(QUOTES))
    ap.add_argument("--granularity", type=int, default=3600)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    arts = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(args.artifacts).glob("*.json"))]
    arts = [a for a in arts if a.get("instrument") == args.instrument]
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory() as scratch:
        approvals = CalibrationApprovals(Path(scratch))  # empty ledger: nothing is approved here
        producer = SignalProducer(build_provider(args.source), approvals, arts, DEFAULT_COSTS,
                                  quote_provider=QUOTES[args.source](resilient_http()))
        produced = producer.produce(args.instrument, granularity_s=args.granularity, now=now)
    rows = [{"reason": p.reason, "artifact_sha256": p.artifact_sha256, "signal_emitted": p.signal is not None,
             "data_source": p.data_source, "data_classification": p.data_classification, "data_digest": p.data_digest,
             "last_bar_open_utc": (datetime.fromtimestamp(p.last_bar_ts, tz=timezone.utc).isoformat()
                                   if p.last_bar_ts else None),
             "observed_spread_bps": p.observed_spread_bps,
             "strategy": next((a.get("strategy") for a in arts if a.get("artifact_sha256") == p.artifact_sha256), None),
             "artifact_gates_passed": next((bool((a.get("gates") or {}).get("passed")) for a in arts
                                            if a.get("artifact_sha256") == p.artifact_sha256), None)}
            for p in produced]
    report = {"generated_utc": now.isoformat(), "instrument": args.instrument, "source": args.source,
              "artifacts_considered": len(arts), "approvals_ledger": "empty (approvals are human-only)",
              "produced": rows, "orders_placed": 0, "paper_only": True}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for r in rows:
        print(f"{r['strategy'] or '-':15s} {r['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
