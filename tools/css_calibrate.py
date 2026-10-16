"""Walk-forward calibration of the approved CSS strategies on cached real candles.

Usage:
  python tools/css_calibrate.py --cache data/market_cache --source coinbase_exchange_public \
      --instrument BTC-USD --asset-class CRYPTO --granularity 3600 --out artifacts/calibration

Writes one artifact per strategy with its OOS metrics and gate verdict. An artifact is NOT
routable until two distinct SUPER_USERs approve it (backend.signals.producer.CalibrationApprovals).
Exit code 0 always reports; the gate verdict is in the JSON and on stdout.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.signals.calibration import GateThresholds, build_artifact, walk_forward  # noqa: E402
from backend.signals.candles import CsvCandleStore, validate  # noqa: E402
from backend.signals.research import APPROVED_STRATEGIES, DEFAULT_COSTS, BarrierParams, label_events  # noqa: E402


def code_revision() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def calibrate(series, *, asset_class: str, train_frac: float = 0.4, folds: int = 6,
              gates: GateThresholds = GateThresholds(), barrier: BarrierParams = BarrierParams()) -> list[dict]:
    costs = DEFAULT_COSTS[asset_class]
    events = label_events(series.candles, barrier, costs)
    n = len(series.candles)
    train_bars = int(n * train_frac)
    step = max(1, (n - train_bars) // folds)
    out = []
    for strategy in APPROVED_STRATEGIES:
        evs = [e for e in events if e.strategy == strategy]
        oos = walk_forward(evs, n_bars=n, train_bars=train_bars, step_bars=step)
        out.append(build_artifact(strategy=strategy, instrument=series.instrument, asset_class=asset_class,
                                  granularity_s=series.granularity_s, events=evs, oos=oos, gates=gates,
                                  data_digests=[series.digest], barrier=asdict(barrier), costs=asdict(costs),
                                  code_revision=code_revision()))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--asset-class", required=True, choices=sorted(DEFAULT_COSTS))
    ap.add_argument("--granularity", type=int, default=3600)
    ap.add_argument("--out", default="artifacts/calibration")
    args = ap.parse_args(argv)
    series = validate(CsvCandleStore(args.cache).load(args.source, args.instrument, args.asset_class, args.granularity),
                      allow_gaps=10_000)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for art in calibrate(series, asset_class=args.asset_class):
        path = out_dir / f"{art['instrument'].replace('/', '-')}_{art['granularity_s']}_{art['strategy']}.json"
        path.write_text(json.dumps(art, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        o = art["oos"]
        print(f"{art['strategy']:15s} oos_trades={o['trades']} mean_net_bps={o['mean_net_bps']:.1f} "
              f"lb95={o['lower_bound_net_bps']:.1f} brier={o['brier']:.4f}/{o['base_rate_brier']:.4f} "
              f"pos_folds={o['positive_fold_fraction']:.2f} gates={'PASS' if art['gates']['passed'] else 'FAIL'} "
              f"sha256={art['artifact_sha256'][:16]} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
